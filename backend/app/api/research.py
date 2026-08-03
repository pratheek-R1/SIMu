from __future__ import annotations

import re
import statistics

from fastapi import APIRouter, HTTPException, Query, status

from ..deps import Db, OwnedSession
from ..registry import (
    archive_rows,
    company_profile,
    get_dataset,
    ghost_name_index,
    scatter_points,
    variable_evidence,
    winner_rows,
)
from ..schemas import (
    CompareRequest,
    ContradictionFlagRequest,
    ContradictionFlagResponse,
    SearchRequest,
    SearchResponse,
)
from ..service import record_event
from ..sim import parameters as P
from ..sim.generator import FEATURE_INDEX

router = APIRouter(prefix="/sessions/{session_id}", tags=["research"])

# The prototype's meta-query detector, kept verbatim in spirit: a student asking
# in plain language where the data came from or what is missing from it.
META_QUERY = re.compile(
    r"fail|lost|passed|dead|shut|wound|source|where|origin|all compan|complete|"
    r"missing|survivor|denominator|base ?rate|full list|everything",
    re.IGNORECASE,
)


def _rows_for(run, ds):
    """Winners always; failures only once the archive is unlocked."""
    rows = winner_rows(ds)
    if run.archive_unlocked:
        rows = rows + archive_rows(ds)
    return rows


@router.get("/companies")
async def list_companies(
    run: OwnedSession,
    sector: list[str] | None = Query(default=None),
    city: list[str] | None = Query(default=None),
    feature: list[str] | None = Query(default=None),
    arr_min: float | None = None,
    arr_max: float | None = None,
    retention_min: float | None = None,
    retention_max: float | None = None,
    ltv_min: float | None = None,
    ltv_max: float | None = None,
    q: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> dict:
    ds = get_dataset(run.seed)
    rows = _rows_for(run, ds)

    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["name"].lower()
                or needle in r["sector"].lower() or needle in r["city"].lower()]
    if sector:
        rows = [r for r in rows if r["sector"] in set(sector)]
    if city:
        rows = [r for r in rows if r["city"] in set(city)]
    if feature:
        idxs = [FEATURE_INDEX[f] for f in feature if f in FEATURE_INDEX]
        rows = [r for r in rows if all(r["flags"][i] == "1" for i in idxs)]
    if arr_min is not None:
        rows = [r for r in rows if r["arr_usd"] >= arr_min]
    if arr_max is not None:
        rows = [r for r in rows if r["arr_usd"] <= arr_max]
    if retention_min is not None:
        rows = [r for r in rows if r["month6_retention"] * 100 >= retention_min]
    if retention_max is not None:
        rows = [r for r in rows if r["month6_retention"] * 100 <= retention_max]
    if ltv_min is not None:
        rows = [r for r in rows if r["ltv_cac_ratio"] >= ltv_min]
    if ltv_max is not None:
        rows = [r for r in rows if r["ltv_cac_ratio"] <= ltv_max]

    total_pool = len(_rows_for(run, ds))
    stats = {
        "matching": len(rows),
        "share": round(len(rows) / total_pool * 100, 1) if total_pool else 0.0,
        "median_retention": (
            round(statistics.median(r["month6_retention"] for r in rows) * 100, 1)
            if rows else None
        ),
        "median_arr_usd": (
            statistics.median(r["arr_usd"] for r in rows) if rows else None
        ),
    }
    return {"rows": rows[offset : offset + limit], "total": len(rows), "stats": stats}


@router.get("/companies/{company_id}")
async def get_company(company_id: int, run: OwnedSession, db: Db) -> dict:
    ds = get_dataset(run.seed)

    is_winner = company_id in set(ds.winner_ids)
    is_visible_failure = company_id in set(ds.visible_failure_ids)
    if not (is_winner or (is_visible_failure and run.archive_unlocked)):
        # A withheld failure, or an archive record before the reveal. Same 404
        # either way -- the response must not disclose that the id exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such company in your records")

    profile = company_profile(ds, company_id)
    assert profile is not None

    # This IS the telemetry. Opening a profile requires this call, so the count
    # cannot be inflated without actually opening profiles.
    await record_event(db, run, "profile_opened", subject=company_id)
    return profile


@router.get("/companies/{company_id}/board-minutes")
async def board_minutes(company_id: int, run: OwnedSession, db: Db) -> dict:
    ds = get_dataset(run.seed)
    c = ds.by_id(company_id)
    if c is None or company_id in set(ds.withheld_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No minutes on file")
    await record_event(db, run, "board_minutes_opened", subject=company_id)
    return {"company_id": company_id, "board_minutes": c["board_minutes"]}


@router.get("/companies/{company_id}/founder-interview")
async def founder_interview(company_id: int, run: OwnedSession, db: Db) -> dict:
    ds = get_dataset(run.seed)
    c = ds.by_id(company_id)
    if c is None or company_id in set(ds.withheld_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No interview on file")
    await record_event(db, run, "founder_interview_opened", subject=company_id)
    return {"company_id": company_id, "founder_interview": c["founder_interview"]}


@router.post("/companies/{company_id}/flag-contradiction", response_model=ContradictionFlagResponse)
async def flag_contradiction(
    company_id: int, body: ContradictionFlagRequest, run: OwnedSession, db: Db
) -> ContradictionFlagResponse:
    """Claim that the minutes and the interview disagree about a variable.

    This is the Triangulation dimension's actual measurement. A wrong flag is
    recorded too -- an analyst who cries contradiction on every company is not
    triangulating either, and the scorecard reports false flags separately.
    """
    ds = get_dataset(run.seed)
    c = ds.by_id(company_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such company")
    if body.feature not in P.BINARY_FEATURES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown variable")

    correct = c["contradicts_feature"] == body.feature
    await record_event(
        db,
        run,
        "contradiction_flagged",
        subject=company_id,
        payload={"correct": correct, "feature": body.feature},
    )

    if correct:
        return ContradictionFlagResponse(
            correct=True,
            message="Logged. The two accounts do disagree on that point.",
            resolution=c["contradiction_resolution"],
        )
    return ContradictionFlagResponse(
        correct=False,
        message=(
            "Logged, but the two accounts are consistent on that variable. "
            "Re-read both before flagging."
        ),
        resolution=None,
    )


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, run: OwnedSession, db: Db) -> SearchResponse:
    ds = get_dataset(run.seed)
    needle = body.query.strip().lower()
    rows = _rows_for(run, ds)
    matches = [
        r for r in rows
        if needle in r["name"].lower()
        or needle in r["sector"].lower()
        or needle in r["city"].lower()
    ]

    notice = None

    # Ghost query: a competitor named on a profile page that is nowhere in the
    # research set, because the research set is winners only.
    if not matches and needle:
        ghosts = ghost_name_index(ds)
        if needle in ghosts and not run.archive_unlocked:
            await record_event(db, run, "ghost_query", subject=body.query)
            notice = {
                "title": "Not in the portfolio history",
                "message": (
                    "That company appears in our competitive notes but has no record "
                    "in the portfolio history. The history covers companies the firm "
                    "backed."
                ),
            }

    if META_QUERY.search(body.query):
        await record_event(db, run, "provenance_query", subject=body.query)
        if run.archive_unlocked:
            await record_event(db, run, "archive_completeness_questioned", subject=body.query)
            notice = notice or {
                "title": "Archive provenance",
                "message": (
                    "The recovered archive covers companies that formally filed "
                    "dissolution. Acqui-hires and quiet wind-downs did not."
                ),
            }
        else:
            notice = notice or {
                "title": "Search covers the portfolio history",
                "message": (
                    "The portfolio history contains companies the firm backed. "
                    "Ops may have records of what we passed on -- ask them."
                ),
            }

    return SearchResponse(matches=matches[:50], total=len(matches), notice=notice)


@router.post("/compare")
async def compare(body: CompareRequest, run: OwnedSession, db: Db) -> dict:
    ds = get_dataset(run.seed)
    allowed = set(ds.winner_ids) | (
        set(ds.visible_failure_ids) if run.archive_unlocked else set()
    )
    profiles = []
    for cid in body.company_ids:
        if cid not in allowed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Company {cid} not in your records")
        p = company_profile(ds, cid)
        if p:
            profiles.append(p)

    await record_event(
        db, run, "comparison_added", payload={"company_ids": body.company_ids}
    )
    return {"companies": profiles, "variables": [
        {"key": k, "label": P.FEATURE_LABELS[k]} for k in P.FEATURE_KEYS
    ]}


@router.get("/variables")
async def variables(run: OwnedSession) -> dict:
    """Evidence per variable, for the thesis screen.

    Prevalence before the reveal; prevalence plus win rates after it.
    """
    ds = get_dataset(run.seed)
    return variable_evidence(ds, archive_unlocked=run.archive_unlocked)


@router.get("/scatter")
async def scatter(run: OwnedSession) -> dict:
    """Cross-plot over the four continuous metrics.

    Before the archive arrives, the failure cloud is absent and the client
    renders the overlay control as visibly locked. That lock is the whole
    pedagogical point of the screen, so it is enforced here rather than in CSS.
    """
    ds = get_dataset(run.seed)
    return scatter_points(ds, include_failures=run.archive_unlocked)


@router.post("/request-comparison-group", status_code=202)
async def request_comparison_group(run: OwnedSession, db: Db) -> dict:
    """Fired when the student clicks the locked failure-overlay control.

    In the prototype this credit fired automatically the instant the Evidence
    screen loaded, so every student collected it by walking forward. It now
    requires actually asking for the comparison group, and only counts when
    asked before the archive arrives.
    """
    await record_event(db, run, "comparison_group_requested")
    if run.archive_unlocked:
        return {
            "granted": True,
            "message": "Failure overlay enabled.",
        }
    return {
        "granted": False,
        "message": (
            "The portfolio history has no failure records. If you want a comparison "
            "group you will have to find one."
        ),
    }
