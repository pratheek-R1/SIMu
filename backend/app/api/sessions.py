from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import desc, select

from ..committee import N_PARTNERS
from ..config import settings
from ..deps import CurrentUser, Db, OwnedSession
from ..models import Cohort, Scorecard
from ..models import Session as RunSession
from ..registry import dataset_summary, get_dataset
from ..schemas import ChartViewRequest, ScreenRequest, SessionOut, SessionSummary
from ..scoring import VALID_CHART_IDS
from ..service import assert_can_enter, deliberation_remaining, rail, record_event, set_screen

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _seed_for(db: Db, user: CurrentUser) -> int:
    if user.cohort_id:
        cohort = await db.get(Cohort, user.cohort_id)
        if cohort:
            return cohort.seed
    return settings.default_cohort_seed


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(user: CurrentUser, db: Db) -> RunSession:
    seed = await _seed_for(db, user)
    ds = get_dataset(seed)
    run = RunSession(
        user_id=user.id,
        cohort_id=user.cohort_id,
        seed=seed,
        dataset_fingerprint=ds.fingerprint,
    )
    db.add(run)
    await db.flush()
    return run


@router.get("", response_model=list[SessionSummary])
async def list_sessions(user: CurrentUser, db: Db) -> list[SessionSummary]:
    stmt = (
        select(RunSession, Scorecard)
        .outerjoin(Scorecard, Scorecard.session_id == RunSession.id)
        .where(RunSession.user_id == user.id)
        .order_by(desc(RunSession.created_at))
    )
    rows = (await db.execute(stmt)).all()
    return [
        SessionSummary(
            id=run.id,
            status=run.status,
            current_screen=run.current_screen,
            total_score=card.total if card else None,
            band=card.band if card else None,
            hits=(run.fund_result or {}).get("hits") if run.fund_result else None,
            created_at=run.created_at,
        )
        for run, card in rows
    ]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(run: OwnedSession) -> RunSession:
    return run


@router.get("/{session_id}/state")
async def get_state(run: OwnedSession) -> dict:
    """Everything the client needs to render the shell on any screen."""
    return {
        "session_id": run.id,
        "current_screen": run.current_screen,
        "furthest_screen": run.furthest_screen,
        "rail": rail(run),
        "thesis_locked": run.thesis_locked,
        "thesis_variables": run.thesis_variables,
        "thesis_confidence": run.thesis_confidence,
        "falsification": run.falsification,
        "archive_unlocked": run.archive_unlocked,
        "committee_answered": len(run.committee_answers or []),
        "committee_total": N_PARTNERS,
        "deliberation_remaining": deliberation_remaining(run),
        "model_weights": run.model_weights,
        "picks": run.picks or [],
        "deployed": run.deployed,
        "summary": dataset_summary(
            get_dataset(run.seed), archive_unlocked=run.archive_unlocked
        ),
    }


@router.post("/{session_id}/screen")
async def advance(body: ScreenRequest, run: OwnedSession, db: Db) -> dict:
    assert_can_enter(run, body.screen, N_PARTNERS)
    set_screen(run, body.screen)
    db.add(run)
    return {"current_screen": run.current_screen, "rail": rail(run)}


@router.post("/{session_id}/telemetry/chart", status_code=202)
async def chart_viewed(body: ChartViewRequest, run: OwnedSession, db: Db) -> dict:
    """The one client-reported signal.

    A hover is not observable server-side, so this endpoint exists. It is
    validated against an allowlist and deduplicated at scoring time, which caps
    what a hand-rolled POST can earn at the same 2 points per chart a real
    student gets -- across at most 10 known charts.
    """
    if body.chart_id not in VALID_CHART_IDS:
        return {"recorded": False, "reason": "unknown chart id"}
    await record_event(db, run, "chart_viewed", subject=body.chart_id)
    return {"recorded": True}
