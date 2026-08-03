from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..deps import Db, OwnedSession
from ..registry import evidence_board, get_dataset
from ..service import now, record_event

router = APIRouter(prefix="/sessions/{session_id}", tags=["evidence"])


@router.get("/inbox")
async def inbox(run: OwnedSession) -> dict:
    """The in-fiction email that carries the archive. Deliberately understated:
    no modal, no fanfare. The reveal should read as an ordinary Tuesday."""
    ds = get_dataset(run.seed)
    return {
        "from": "Devika Rao",
        "department": "Operations",
        "time": "09:12",
        "subject": "Pre-2019 pipeline records",
        "body": (
            "Found these on the old shared drive. Every company the firm passed on "
            "or wrote off since 2012."
        ),
        "attachment": {
            "filename": "pipeline_archive_2012_2019.csv",
            "records": ds.n_failures_visible,
        },
        "unlocked": run.archive_unlocked,
    }


@router.post("/archive/unlock")
async def unlock(run: OwnedSession, db: Db) -> dict:
    if not run.thesis_locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Lock your thesis first")
    ds = get_dataset(run.seed)
    if not run.archive_unlocked:
        run.archive_unlocked = True
        run.archive_unlocked_at = now()
        db.add(run)
        await record_event(db, run, "archive_unlocked")
    return {
        "unlocked": True,
        "records": ds.n_failures_visible,
        "portfolio": ds.n_winners,
    }


@router.get("/evidence")
async def evidence(run: OwnedSession) -> dict:
    """The student's own claims against the combined record.

    Counts are against the VISIBLE archive. The complete-population figures are
    held back until the debrief, because the gap between them is the second
    lesson and revealing it here would collapse the two into one.
    """
    if not run.archive_unlocked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Open the archive first")

    ds = get_dataset(run.seed)
    variables = run.thesis_variables or []
    rows = evidence_board(ds, variables)

    return {
        "rows": rows,
        "portfolio_count": ds.n_winners,
        "archive_count": ds.n_failures_visible,
        "combined_count": ds.n_winners + ds.n_failures_visible,
        "share_of_evidence_seen": round(
            ds.n_winners / (ds.n_winners + ds.n_failures_visible) * 100, 1
        ),
        "thesis_confidence": run.thesis_confidence or {},
    }
