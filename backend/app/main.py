from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import cache
from .api import router
from .config import settings
from .db import init_db
from .registry import get_dataset
from .sim.validate import run_gate

log = logging.getLogger("survivors")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail at boot rather than issuing tokens anyone can forge. Render's
    # blueprint generates the secret, so this only fires on a misconfigured
    # manual deploy.
    if settings.is_production and settings.jwt_secret == "dev-secret-change-me":
        raise RuntimeError("JWT_SECRET must be set when ENVIRONMENT=production")
    if settings.is_production and settings.is_sqlite:
        log.warning(
            "running against SQLite in production: Render's disk is ephemeral "
            "and all student sessions are lost on redeploy. Set DATABASE_URL."
        )

    await init_db()

    # Build the default dataset at boot so the first student does not pay for
    # generation, and run the gate so a bad parameter change fails loudly here
    # rather than quietly in front of a cohort.
    ds = get_dataset(settings.default_cohort_seed)
    gate = run_gate(settings.default_cohort_seed, ds=ds)
    if gate.passed:
        log.info(
            "dataset %s ready: %d winners, %d visible failures, %d/5 naive top-5 are traps",
            ds.fingerprint, ds.n_winners, ds.n_failures_visible, gate.traps_in_top5,
        )
    else:
        log.error("VALIDATION GATE FAILED for seed %s: %s", ds.seed, gate.failures)

    yield
    await cache.close()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Backend for The Survivors' Illusion. Owns all ground truth about what "
        "causes startup success; the client is read-only over projections that "
        "never include an outcome the narrative has not yet earned."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "api": settings.api_prefix}
