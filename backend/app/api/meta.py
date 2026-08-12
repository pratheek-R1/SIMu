from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..registry import continuous_catalogue, feature_catalogue
from ..service import SCREEN_LABELS, SCREEN_ORDER
from ..sim import parameters as P

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/config")
async def config() -> dict:
    """Client bootstrap.

    `inr_rate` is served rather than hardcoded in the client -- in the prototype
    it was a magic number buried in profile.js.

    Note what is NOT here: the variable classes. Shipping the A/B/C/D taxonomy
    to the client would hand over the answer key.
    """
    return {
        "inr_rate": settings.inr_rate,
        "deliberation_seconds": settings.deliberation_seconds,
        "variables": feature_catalogue(),
        "continuous_metrics": continuous_catalogue(),
        "screens": [{"key": s, "label": SCREEN_LABELS[s]} for s in SCREEN_ORDER],
        "max_thesis_variables": 4,
        "cheques": P.N_CHEQUES,
        # The mandate's own numbers. Served rather than hardcoded in the client
        # for the same reason `inr_rate` is: the brief screen was quoting a
        # pool figure that only existed as a string in two components, so
        # changing the pool would have left them both lying.
        "fund_pool_usd": P.FUND_POOL_USD,
        "cheque_min_usd": P.CHEQUE_MIN_USD,
        "cheque_max_usd": P.CHEQUE_MAX_USD,
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
