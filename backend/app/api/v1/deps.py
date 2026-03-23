from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import EncryptionService, decode_token
from app.models.user import User


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session() as session:
        yield session


def get_encryption_service(request: Request) -> EncryptionService:
    settings = request.app.state.settings
    return EncryptionService(
        fernet_secret_key=settings.fernet_secret_key,
        encryption_pepper=settings.encryption_pepper,
    )


def _extract_token(request: Request, cookie_name: str) -> str | None:
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        return cookie_token

    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]

    return None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> User:
    settings = request.app.state.settings
    token = _extract_token(request, settings.access_cookie_name)

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(token, secret_key=settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    statement = select(User).where(User.id == payload["sub"])
    user = await session.scalar(statement)

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
