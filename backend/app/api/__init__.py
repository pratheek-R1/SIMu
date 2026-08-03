from fastapi import APIRouter

from . import admin, auth, dealflow, evidence, meta, model, research, results, sessions, thesis

router = APIRouter()
router.include_router(meta.router)
router.include_router(auth.router)
router.include_router(sessions.router)
router.include_router(research.router)
router.include_router(thesis.router)
router.include_router(evidence.router)
router.include_router(model.router)
router.include_router(dealflow.router)
router.include_router(results.router)
router.include_router(admin.router)
