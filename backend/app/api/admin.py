"""Facilitator endpoints.

Open Issue 6 in the handoff: with no persistence, "the only way to see a
student's result is for them to paste the report text back into a chat". These
endpoints are the reason the backend exists at all -- an instructor can review a
cohort after the fact, and can audit exactly which behaviours earned which
points.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import Db, Facilitator
from ..models import Cohort, Scorecard, Session as RunSession, TelemetryEvent, User
from ..sim import parameters as P
from ..sim.validate import run_gate
from ..registry import get_dataset

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cohorts", status_code=201)
async def create_cohort(name: str, seed: int, _: Facilitator, db: Db) -> dict:
    """Create a cohort with its own dataset seed.

    Reusing a seed across semesters means the reveal is common knowledge before
    the second cohort starts. Give every intake its own.
    """
    existing = (
        await db.execute(select(Cohort).where(Cohort.name == name))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cohort already exists")

    gate = run_gate(seed)
    if not gate.passed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "message": "This seed does not pass the validation gate",
                "failures": gate.failures,
            },
        )

    cohort = Cohort(name=name, seed=seed)
    db.add(cohort)
    await db.flush()
    return {
        "id": cohort.id,
        "name": cohort.name,
        "seed": cohort.seed,
        "gate": {
            "passed": True,
            "traps_in_top5": gate.traps_in_top5,
            "first_causal_rank": gate.first_causal_rank,
        },
    }


@router.get("/cohorts")
async def list_cohorts(_: Facilitator, db: Db) -> list[dict]:
    rows = (await db.execute(select(Cohort))).scalars().all()
    return [
        {"id": c.id, "name": c.name, "seed": c.seed, "is_active": c.is_active}
        for c in rows
    ]


@router.get("/cohorts/{cohort_id}/results")
async def cohort_results(cohort_id: str, _: Facilitator, db: Db) -> dict:
    stmt = (
        select(User, RunSession, Scorecard)
        .join(RunSession, RunSession.user_id == User.id)
        .outerjoin(Scorecard, Scorecard.session_id == RunSession.id)
        .where(RunSession.cohort_id == cohort_id)
        .order_by(User.name)
    )
    rows = (await db.execute(stmt)).all()

    results = []
    for user, run, card in rows:
        results.append(
            {
                "user": {"id": user.id, "name": user.name, "email": user.email},
                "session_id": run.id,
                "status": run.status,
                "furthest_screen": run.furthest_screen,
                "thesis_variables": run.thesis_variables,
                "thesis_classes": [
                    P.feature_class(v) for v in (run.thesis_variables or [])
                ],
                "total": card.total if card else None,
                "band": card.band if card else None,
                "dimensions": (
                    {d["key"]: d["score"] for d in card.dimensions["dimensions"]}
                    if card
                    else None
                ),
                "hits": (run.fund_result or {}).get("hits"),
                "completed_at": run.completed_at,
            }
        )

    completed = [r for r in results if r["total"] is not None]
    trap_theses = sum(
        1 for r in results if r["thesis_classes"] and all(c in ("B", "C") for c in r["thesis_classes"])
    )

    return {
        "cohort_id": cohort_id,
        "results": results,
        "summary": {
            "students": len({r["user"]["id"] for r in results}),
            "sessions": len(results),
            "completed": len(completed),
            "mean_total": (
                round(sum(r["total"] for r in completed) / len(completed), 1)
                if completed
                else None
            ),
            "theses_built_entirely_on_traps": trap_theses,
        },
    }


@router.get("/sessions/{session_id}/audit")
async def audit(session_id: str, _: Facilitator, db: Db) -> dict:
    """The complete behavioural log for one session.

    Every point on a scorecard traces back to a row here.
    """
    run = await db.get(RunSession, session_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    events = (
        await db.execute(
            select(TelemetryEvent)
            .where(TelemetryEvent.session_id == session_id)
            .order_by(TelemetryEvent.created_at)
        )
    ).scalars().all()

    return {
        "session_id": session_id,
        "seed": run.seed,
        "dataset_fingerprint": run.dataset_fingerprint,
        "events": [
            {
                "kind": e.kind,
                "subject": e.subject,
                "screen": e.screen,
                "payload": e.payload,
                "at": e.created_at,
            }
            for e in events
        ],
    }


@router.get("/gate")
async def gate(seed: int, _: Facilitator) -> dict:
    """Run the validation gate against a candidate seed before adopting it."""
    res = run_gate(seed)
    return {
        "seed": seed,
        "passed": res.passed,
        "naive_top5": res.naive_top5,
        "traps_in_top5": res.traps_in_top5,
        "first_causal_rank": res.first_causal_rank,
        "causal_lifts": res.causal_lifts,
        "balance_sheet_ok": res.balance_sheet_ok,
        "burn_multiple": res.burn_multiple,
        "archive": res.archive,
        "failures": res.failures,
    }
