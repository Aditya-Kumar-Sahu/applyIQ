from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.system import router as system_router


router = APIRouter()
router.include_router(system_router)
