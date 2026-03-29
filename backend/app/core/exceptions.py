from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import structlog

from app.core.logging_safety import log_exception, sanitize_for_logging


def register_exception_handlers(app: FastAPI) -> None:
    logger = structlog.get_logger(__name__)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(
            "http.handled_exception",
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            detail=sanitize_for_logging(exc.detail),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {"code": "http_error", "message": exc.detail},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "http.validation_error",
            path=request.url.path,
            method=request.method,
            errors=sanitize_for_logging(exc.errors()),
            body=sanitize_for_logging(exc.body),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "data": None,
                "error": {"code": "validation_error", "message": str(exc)},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log_exception(
            logger,
            "http.unhandled_exception",
            exc,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error": {"code": "internal_server_error", "message": "Internal server error"},
            },
        )
