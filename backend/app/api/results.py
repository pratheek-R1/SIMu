from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import Db, OwnedSession
from ..models import Report, Scorecard, TelemetryEvent
from ..registry import continuous_truth, get_dataset, truth_table
from ..report import render as render_report
from ..scoring import build_scorecard
from ..service import now
from ..sim import parameters as P
from ..sim import portfolio as mc
from ..config import settings

router = APIRouter(prefix="/sessions/{session_id}", tags=["results"])

_fund_distribution: dict[int, list[dict]] = {}


def _distribution(seed: int) -> list[dict]:
    """The 20,000-fund comparison. Computed once per seed, then cached.

    This is the evidence for scoring fund P&L at zero: a trap-based strategy
    performs worse than random, and even a sound one blanks sometimes.
    """
    if seed not in _fund_distribution:
        _fund_distribution[seed] = [
            {
                "strategy": r.name,
                "mean_wins": round(r.mean_wins, 2),
                "p_zero_wins": round(r.p_zero_wins * 100, 1),
                "p_three_plus": round(r.p_three_plus * 100, 1),
                "distribution": [round(x * 100, 1) for x in r.distribution],
            }
            for r in mc.run(seed=seed)
        ]
    return _fund_distribution[seed]


def _require_deployed(run) -> None:
    if not run.deployed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Deploy the fund first")


@router.get("/results")
async def results(run: OwnedSession) -> dict:
    _require_deployed(run)
    return run.fund_result or {}


@router.get("/debrief")
async def debrief(run: OwnedSession) -> dict:
    """What you believed, and what was true.

    This is the only endpoint that ever returns the A/B/C/D classification, the
    complete-population failure counts, or the size of the archive withhold.
    """
    _require_deployed(run)
    ds = get_dataset(run.seed)
    truth = truth_table(ds)
    by_key = {t["feature"]: t for t in truth}

    variables = run.thesis_variables or []
    confidence = run.thesis_confidence or {}
    mirror = [
        {**by_key[v], "stated_confidence": confidence.get(v)}
        for v in variables
        if v in by_key
    ]

    causal = sorted(
        (by_key[k] for k in P.CAUSAL_FEATURES), key=lambda r: -r["true_lift"]
    )

    return {
        "mirror": mirror,
        "falsification": run.falsification,
        "causal_variables": causal,
        "continuous_truth": continuous_truth(ds),
        "naive_top5": [
            t for t in sorted(truth, key=lambda r: r["rank_by_frequency"])[:5]
        ],
        "full_truth": truth,
        "fund": run.fund_result,
        "fund_distribution": _distribution(run.seed),
        "portfolio_count": ds.n_winners,
        "archive_visible": ds.n_failures_visible,
        "archive_complete": ds.n_failures_complete,
        "withheld_count": len(ds.withheld_ids),
        "share_of_evidence_seen": round(
            ds.n_winners / (ds.n_winners + ds.n_failures_complete) * 100, 1
        ),
        "withhold_note": (
            "The archive you received was itself incomplete. "
            f"{len(ds.withheld_ids)} companies never filed dissolution paperwork -- "
            "they were acqui-hired or wound down quietly -- and their absence is not "
            "random: companies with tier-one investors and elite-school founders are "
            "over-represented among them. Treating the recovered archive as complete "
            "repeats the original error one level up."
        ),
    }


@router.get("/scorecard")
async def scorecard(run: OwnedSession, db: Db) -> dict:
    _require_deployed(run)
    ds = get_dataset(run.seed)

    events = (
        await db.execute(
            select(TelemetryEvent).where(TelemetryEvent.session_id == run.id)
        )
    ).scalars().all()

    card = build_scorecard(ds, run, events)

    existing = (
        await db.execute(select(Scorecard).where(Scorecard.session_id == run.id))
    ).scalar_one_or_none()
    if existing:
        existing.total = card["total"]
        existing.band = card["band"]
        existing.dimensions = card
        db.add(existing)
    else:
        db.add(
            Scorecard(
                session_id=run.id,
                total=card["total"],
                band=card["band"],
                dimensions=card,
            )
        )

    if run.status != "complete":
        run.status = "complete"
        run.completed_at = now()
        db.add(run)

    return card


@router.post("/report")
async def create_report(run: OwnedSession, db: Db) -> dict:
    _require_deployed(run)

    card = await scorecard(run, db)
    brief = await debrief(run)

    html = render_report(
        user_name=run.user.name if run.user else "Analyst",
        session=run,
        scorecard=card,
        debrief=brief,
        rate=settings.inr_rate,
    )

    # Postgres is the only store. The report is the artefact a facilitator
    # grades from, so it lives with the session it came from rather than in a
    # separate object store that can drift out of sync with it.
    # Databases provisioned before `uq_report_session` existed can already hold
    # duplicates from a repeated POST. Collapse them rather than failing the
    # request -- the student's report is not the place to surface that history.
    rows = (
        await db.execute(
            select(Report)
            .where(Report.session_id == run.id)
            .order_by(Report.created_at.desc())
        )
    ).scalars().all()

    if rows:
        rows[0].content_html = html
        db.add(rows[0])
        for stale in rows[1:]:
            await db.delete(stale)
    else:
        db.add(Report(session_id=run.id, content_html=html))

    return {"html": html, "stored": True}
