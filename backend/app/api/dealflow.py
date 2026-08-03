from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..deps import Db, OwnedSession
from ..registry import deal_rows, get_dataset
from ..schemas import PicksRequest
from ..scoring import model_score, resolve_fund
from ..service import now, record_event
from ..sim import parameters as P

router = APIRouter(prefix="/sessions/{session_id}", tags=["dealflow"])


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

    run.picks = body.picks
    db.add(run)
    return {"picks": run.picks, "slots": f"{len(run.picks)}/{P.N_CHEQUES}"}


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

    ds = get_dataset(run.seed)
    result = resolve_fund(ds, run.picks or [])

    run.fund_result = result
    run.deployed = True
    run.deployed_at = now()
    db.add(run)
    await record_event(
        db, run, "fund_deployed", payload={"picks": run.picks, "hits": result["hits"]}
    )
    return result
