from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, status

from ..deps import Db, OwnedSession
from ..registry import get_dataset
from ..schemas import WeightsRequest
from ..service import record_event
from ..sim import parameters as P
from ..sim.generator import build_backtest_pool

router = APIRouter(prefix="/sessions/{session_id}", tags=["model"])

SEED_WEIGHT = 2.0  # thesis variables start here; everything else at zero
TOP_N = 50
_pools: dict[int, tuple[np.ndarray, np.ndarray]] = {}


def _pool(seed: int):
    if seed not in _pools:
        _pools[seed] = build_backtest_pool(seed)
    return _pools[seed]


@router.get("/model")
async def get_model(run: OwnedSession, db: Db) -> dict:
    """Return the weight sliders, seeding them from the locked thesis.

    The first call captures `w1_snapshot` -- the pre-revision baseline that
    Revision Quality is measured against. It must be captured exactly once, at
    the moment the student first sees this screen, or the dimension measures
    nothing.
    """
    if not run.archive_unlocked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Review the evidence first")

    if run.w1_snapshot is None:
        seeded = {k: 0.0 for k in P.FEATURE_KEYS}
        for v in run.thesis_variables or []:
            seeded[v] = SEED_WEIGHT
        run.w1_snapshot = seeded
        run.model_weights = dict(seeded)
        db.add(run)
        await record_event(db, run, "model_baseline_captured", payload=seeded)

    return {
        "variables": [
            {
                "key": k,
                "label": P.FEATURE_LABELS[k],
                "weight": (run.model_weights or {}).get(k, 0.0),
                "baseline": (run.w1_snapshot or {}).get(k, 0.0),
                "in_thesis": k in (run.thesis_variables or []),
            }
            for k in P.FEATURE_KEYS
        ],
        "range": {"min": -3.0, "max": 3.0, "step": 0.5},
    }


@router.put("/model/weights")
async def set_weights(body: WeightsRequest, run: OwnedSession, db: Db) -> dict:
    if run.w1_snapshot is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Open the model screen first")
    if run.deployed:
        raise HTTPException(status.HTTP_409_CONFLICT, "The fund is already deployed")

    unknown = [k for k in body.weights if k not in P.BINARY_FEATURES]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown variables: {unknown}")

    weights = dict(run.model_weights or {})
    weights.update(body.weights)
    run.model_weights = weights
    db.add(run)
    return {"weights": weights}


@router.get("/model/backtest")
async def backtest(run: OwnedSession) -> dict:
    """What the student's current weights would actually have done.

    Ranks a held-out population of 1,000 companies at a 20% base rate by the
    student's model and reports the realised success rate of its top 50. Fixed
    per seed, so moving a slider produces a change the student can attribute to
    that slider rather than to noise.
    """
    if run.w1_snapshot is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Open the model screen first")

    flags, outcome = _pool(run.seed)
    weights = run.model_weights or {}
    w = np.array([weights.get(k, 0.0) for k in P.FEATURE_KEYS], dtype=np.float64)
    scores = flags @ w

    # Deterministic tie-break so equal-scoring companies order stably.
    order = np.lexsort((np.arange(len(scores)), -scores))
    top = order[:TOP_N]
    rate = float(outcome[top].mean())

    return {
        "top_n": TOP_N,
        "success_rate": round(rate * 100, 1),
        "baseline_rate": round(P.DEAL_BASE_RATE * 100, 1),
        "sample_size": int(len(outcome)),
        "lift_vs_random": round(rate / P.DEAL_BASE_RATE, 2) if P.DEAL_BASE_RATE else 0.0,
    }
