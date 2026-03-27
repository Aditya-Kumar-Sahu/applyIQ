from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.pipeline import router as pipeline_router
from app.api.v1.routes.resume import router as resume_router
from app.api.v1.routes.scrape import router as scrape_router
from app.api.v1.routes.system import router as system_router
from app.api.v1.routes.vault import router as vault_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(jobs_router)
router.include_router(pipeline_router)
router.include_router(resume_router)
router.include_router(scrape_router)
router.include_router(system_router)
router.include_router(vault_router)
