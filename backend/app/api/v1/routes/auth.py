from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session
from app.core.security import create_token, decode_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import (
    AuthSessionData,
    AuthUser,
    DeleteAccountData,
    DeleteAccountRequest,
    LoginRequest,
    MeData,
    RegisterRequest,
    TokenRefreshData,
)
from app.schemas.common import Envelope


router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        subscription_tier=user.subscription_tier,
    )


def _issue_tokens(request: Request, user_id: str) -> tuple[str, str]:
    settings = request.app.state.settings
    access_token = create_token(
        subject=user_id,
        token_type="access",
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_token(
        subject=user_id,
        token_type="refresh",
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return access_token, refresh_token


def _set_auth_cookies(request: Request, response: Response, access_token: str, refresh_token: str) -> None:
    settings = request.app.state.settings
    access_max_age = settings.access_token_expire_minutes * 60
    refresh_max_age = settings.refresh_token_expire_days * 24 * 60 * 60

    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=access_max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=refresh_max_age,
        path="/",
    )


def _clear_auth_cookies(request: Request, response: Response) -> None:
    settings = request.app.state.settings
    response.delete_cookie(settings.access_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/")


@router.post("/register", response_model=Envelope[AuthSessionData], status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[AuthSessionData]:
    normalized_email = payload.email.strip().lower()
    existing_user = await session.scalar(select(User).where(User.email == normalized_email))

    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")

    user = User(
        email=normalized_email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name.strip(),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    access_token, refresh_token = _issue_tokens(request, user.id)
    _set_auth_cookies(request, response, access_token, refresh_token)

    return Envelope(
        success=True,
        data=AuthSessionData(
            user=_build_auth_user(user),
            access_token=access_token,
            refresh_token=refresh_token,
        ),
        error=None,
    )


@router.post("/login", response_model=Envelope[AuthSessionData])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[AuthSessionData]:
    normalized_email = payload.email.strip().lower()
    user = await session.scalar(select(User).where(User.email == normalized_email))

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login = datetime.now(timezone.utc)
    await session.commit()

    access_token, refresh_token = _issue_tokens(request, user.id)
    _set_auth_cookies(request, response, access_token, refresh_token)

    return Envelope(
        success=True,
        data=AuthSessionData(
            user=_build_auth_user(user),
            access_token=access_token,
            refresh_token=refresh_token,
        ),
        error=None,
    )


@router.post("/refresh", response_model=Envelope[TokenRefreshData])
async def refresh_token(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[TokenRefreshData]:
    settings = request.app.state.settings
    refresh_token = request.cookies.get(settings.refresh_cookie_name)

    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        payload = decode_token(
            refresh_token,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = await session.scalar(select(User).where(User.id == payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token, new_refresh_token = _issue_tokens(request, user.id)
    _set_auth_cookies(request, response, access_token, new_refresh_token)

    return Envelope(
        success=True,
        data=TokenRefreshData(access_token=access_token, refresh_token=new_refresh_token),
        error=None,
    )


@router.get("/me", response_model=Envelope[MeData])
async def me(current_user: User = Depends(get_current_user)) -> Envelope[MeData]:
    return Envelope(success=True, data=MeData(user=_build_auth_user(current_user)), error=None)


@router.delete("/account", response_model=Envelope[DeleteAccountData])
async def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[DeleteAccountData]:
    if not verify_password(payload.password_confirmation, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await session.delete(current_user)
    await session.commit()
    _clear_auth_cookies(request, response)

    return Envelope(success=True, data=DeleteAccountData(deleted=True), error=None)
