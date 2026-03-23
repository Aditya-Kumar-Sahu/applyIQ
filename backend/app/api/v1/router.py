from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.system import router as system_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(system_router)
