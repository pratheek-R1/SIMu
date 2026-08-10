from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..deps import Db, OwnedSession
from ..registry import deal_rows, get_dataset
from ..schemas import PicksRequest
from ..scoring import model_score, resolve_fund
from ..service import now, record_event
from ..sim import parameters as P

router = APIRouter(prefix="/sessions/{session_id}", tags=["dealflow"])


def _even_split(picks: list[int]) -> dict[str, int]:
    """Fallback allocation when the student never sized the cheques.

    Kept exact: the remainder from an uneven division is handed to the first
    cheques one step at a time rather than left to float, so the total is the
    pool to the dollar.
    """
    if not picks:
        return {}
    base, remainder = divmod(P.FUND_POOL_USD, len(picks))
    sizes = {str(pid): base for pid in picks}
    for pid in picks[:remainder]:
        sizes[str(pid)] += 1
    return sizes


def _validate_sizes(sizes: dict[str, int], picks: list[int], *, final: bool) -> None:
    """Reject an allocation that would corrupt the capital or risk dimensions.

    `final` is set once the student has all five picks and is about to deploy;
    only then is the exact-total rule enforced, so partial sizing while they are
    still choosing companies is not treated as an error.
    """
    expected = {str(p) for p in picks}
    unknown = set(sizes) - expected
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cheque sized for a company that was not picked: {sorted(unknown)}",
        )

    for key, amount in sizes.items():
        if amount % P.CHEQUE_STEP_USD:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cheque for {key} must be a multiple of {P.CHEQUE_STEP_USD:,} USD",
            )
        if not P.CHEQUE_MIN_USD <= amount <= P.CHEQUE_MAX_USD:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cheque for {key} must be between {P.CHEQUE_MIN_USD:,} and "
                f"{P.CHEQUE_MAX_USD:,} USD",
            )

    if not final:
        return

    missing = expected - set(sizes)
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No cheque sized for: {sorted(int(m) for m in missing)}",
        )
    total = sum(sizes.values())
    if total != P.FUND_POOL_USD:
        short = P.FUND_POOL_USD - total
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cheques must total exactly {P.FUND_POOL_USD:,} USD; this allocation "
            f"is {abs(short):,} {'under' if short > 0 else 'over'}.",
        )


@router.get("/dealflow")
async def dealflow(run: OwnedSession) -> dict:
    """All 40 live deals, ranked by the student's own model.

    Every deal is returned. The prototype sliced `idx.slice(6, 22)` and rendered
    22 of 40 while the screen's own copy claimed "40 live deals" -- indices
    22-39 were unreachable. Splitting into shelves is presentation; the API
    returns the complete set and the client renders all of it.
    """
    if not run.model_weights:
        raise HTTPException(status.HTTP_409_CONFLICT, "Build your model first")

    ds = get_dataset(run.seed)
    rows = deal_rows(ds, reveal_outcomes=run.deployed)
    for r in rows:
        r["model_score"] = round(model_score(r["flags"], run.model_weights), 2)
    rows.sort(key=lambda r: -r["model_score"])
    for i, r in enumerate(rows):
        r["model_rank"] = i + 1

    return {
        "deals": rows,
        "total": len(rows),
        "cheque_usd": P.CHEQUE_USD,
        "cheques": P.N_CHEQUES,
        "picks": run.picks or [],
        "cheque_sizes": run.cheque_sizes or {},
        "pool_usd": P.FUND_POOL_USD,
        "cheque_min_usd": P.CHEQUE_MIN_USD,
        "cheque_max_usd": P.CHEQUE_MAX_USD,
        "cheque_step_usd": P.CHEQUE_STEP_USD,
        "deployed": run.deployed,
    }


@router.put("/picks")
async def set_picks(body: PicksRequest, run: OwnedSession, db: Db) -> dict:
    if run.deployed:
        raise HTTPException(status.HTTP_409_CONFLICT, "The fund is already deployed")

    ds = get_dataset(run.seed)
    valid = {d["id"] for d in ds.deals}
    unknown = [p for p in body.picks if p not in valid]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Not in deal flow: {unknown}")
    if len(set(body.picks)) != len(body.picks):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate picks")

    if body.cheque_sizes is not None:
        _validate_sizes(body.cheque_sizes, body.picks, final=False)
        run.cheque_sizes = body.cheque_sizes
    elif run.cheque_sizes:
        # Dropping a company must drop its cheque, or the stale entry fails
        # validation at deploy with a confusing message about a company the
        # student can no longer see selected.
        keep = {str(p) for p in body.picks}
        run.cheque_sizes = {k: v for k, v in run.cheque_sizes.items() if k in keep}

    run.picks = body.picks
    db.add(run)
    return {
        "picks": run.picks,
        "cheque_sizes": run.cheque_sizes or {},
        "allocated_usd": sum((run.cheque_sizes or {}).values()),
        "pool_usd": P.FUND_POOL_USD,
        "slots": f"{len(run.picks)}/{P.N_CHEQUES}",
    }


@router.post("/deploy")
async def deploy(run: OwnedSession, db: Db) -> dict:
    """Write the cheques. Irreversible, and the point at which outcomes exist.

    Until this call returns, no deal's outcome has ever been sent to the client.
    """
    if run.deployed:
        return run.fund_result or {}
    if not run.model_weights:
        raise HTTPException(status.HTTP_409_CONFLICT, "Build your model first")
    if len(run.picks or []) != P.N_CHEQUES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Select exactly {P.N_CHEQUES} companies"
        )

    picks = run.picks or []
    # A student who never touched the sliders deploys an even split. That is a
    # real, defensible allocation -- it just expresses no ordering, which is
    # exactly what Capital Allocation scores neutrally rather than punishing.
    sizes = run.cheque_sizes or _even_split(picks)
    _validate_sizes(sizes, picks, final=True)
    run.cheque_sizes = sizes

    ds = get_dataset(run.seed)
    result = resolve_fund(ds, picks, sizes)

    run.fund_result = result
    run.deployed = True
    run.deployed_at = now()
    db.add(run)
    await record_event(
        db,
        run,
        "fund_deployed",
        payload={"picks": picks, "hits": result["hits"], "cheque_sizes": sizes},
    )
    return result
