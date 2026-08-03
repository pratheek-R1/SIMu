from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..committee import N_PARTNERS, build as build_committee
from ..deps import Db, OwnedSession
from ..schemas import CommitteeAnswerRequest, ThesisRequest
from ..scoring import analyse_free_text
from ..service import deliberation_remaining, now, record_event
from ..sim import parameters as P

router = APIRouter(prefix="/sessions/{session_id}", tags=["thesis"])


@router.post("/thesis")
async def lock_thesis(body: ThesisRequest, run: OwnedSession, db: Db) -> dict:
    """Lock the thesis. Irreversible.

    Enforced here rather than by hiding the button, because the entire
    measurement depends on the thesis being fixed before the archive arrives. A
    student who can revise after seeing the failures is not taking this test.
    """
    if run.thesis_locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your thesis is already locked")

    unknown = [v for v in body.variables if v not in P.BINARY_FEATURES]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown variables: {unknown}")
    if len(set(body.variables)) != len(body.variables):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate variables")

    missing = [v for v in body.variables if v not in body.confidence]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"State a confidence for: {missing}"
        )

    run.thesis_variables = body.variables
    run.thesis_confidence = {k: body.confidence[k] for k in body.variables}
    run.falsification = body.falsification.strip()
    run.thesis_locked = True
    run.thesis_locked_at = now()
    db.add(run)

    await record_event(
        db,
        run,
        "thesis_locked",
        payload={
            "variables": body.variables,
            "confidence": run.thesis_confidence,
            "falsification_signals": analyse_free_text(run.falsification)["signals"],
        },
    )
    return {"locked": True, "variables": run.thesis_variables}


@router.get("/committee")
async def committee(run: OwnedSession) -> dict:
    if not run.thesis_locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Lock your thesis first")
    answered = run.committee_answers or []
    return {
        "partners": build_committee(run.thesis_variables),
        "answers": answered,
        "current_index": min(len(answered), N_PARTNERS - 1),
        "complete": len(answered) >= N_PARTNERS,
    }


@router.post("/committee/answer")
async def answer(body: CommitteeAnswerRequest, run: OwnedSession, db: Db) -> dict:
    if not run.thesis_locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Lock your thesis first")

    answers = list(run.committee_answers or [])
    if body.partner_index != len(answers):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Answer the partners in order"
        )
    if len(answers) >= N_PARTNERS:
        raise HTTPException(status.HTTP_409_CONFLICT, "The committee is finished")

    partners = build_committee(run.thesis_variables)
    analysis = analyse_free_text(body.answer)

    answers.append(
        {
            "partner_index": body.partner_index,
            "partner": partners[body.partner_index]["name"],
            "question": partners[body.partner_index]["question"],
            "answer": body.answer.strip(),
            "signals": analysis["signals"],
        }
    )
    run.committee_answers = answers
    db.add(run)

    # Open Issue 4: this text is now read. The rubric is deterministic and its
    # matches are reported on the scorecard.
    await record_event(
        db,
        run,
        "committee_answer",
        subject=str(body.partner_index),
        payload={"answer": body.answer.strip(), **analysis},
    )
    if "missing_data" in analysis["signals"]:
        await record_event(db, run, "provenance_query", subject="committee")

    complete = len(answers) >= N_PARTNERS

    # Start deliberation in the same transaction so the frontend never hits a
    # state where all answers are committed but deliberation has not started.
    if complete and run.deliberation_started_at is None:
        run.deliberation_started_at = now()
        db.add(run)

    # Flush so the commit in get_db() sees the full mutation before the
    # response is sent. This prevents a race where a immediately following
    # /deliberation/start request loads the row before the write lands.
    await db.flush()

    return {
        "answered": len(answers),
        "total": N_PARTNERS,
        "complete": complete,
    }


@router.post("/deliberation/start")
async def start_deliberation(run: OwnedSession, db: Db) -> dict:
    if len(run.committee_answers or []) < N_PARTNERS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Answer every partner before withdrawing"
        )
    if run.deliberation_started_at is None:
        run.deliberation_started_at = now()
        db.add(run)
    return {"remaining_seconds": deliberation_remaining(run)}


@router.get("/deliberation")
async def deliberation(run: OwnedSession) -> dict:
    """The wait is deliberately empty.

    It substitutes for the overnight gap between presenting a thesis and
    receiving contradicting evidence -- the interval that makes the reveal land
    as a correction rather than as part of the same exercise.
    """
    remaining = deliberation_remaining(run)
    return {
        "remaining_seconds": remaining,
        "ready": remaining <= 0 and run.deliberation_started_at is not None,
        "reviewing": [
            {"variable": v, "confidence": (run.thesis_confidence or {}).get(v)}
            for v in (run.thesis_variables or [])
        ],
    }
