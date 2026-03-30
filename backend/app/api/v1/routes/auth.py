from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session
from app.core.rate_limit import RedisRateLimiter
from app.core.security import create_token, decode_token, get_password_hash, hash_token, verify_password
from app.models.refresh_token_session import RefreshTokenSession
from app.models.pipeline_run import PipelineRun
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


def _refresh_token_expires_at(request: Request) -> datetime:
    settings = request.app.state.settings
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


def _set_auth_cookies(request: Request, response: Response, access_token: str, refresh_token: str) -> None:
    settings = request.app.state.settings
    access_max_age = settings.access_token_expire_minutes * 60
    refresh_max_age = settings.refresh_token_expire_days * 24 * 60 * 60
    secure_cookie = settings.secure_cookies

    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=access_max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=refresh_max_age,
        path="/",
    )


def _clear_auth_cookies(request: Request, response: Response) -> None:
    settings = request.app.state.settings
    response.delete_cookie(settings.access_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/")


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip().lower()

    if request.client is not None and request.client.host:
        return request.client.host.lower()

    return "unknown"


async def _enforce_auth_rate_limit(
    request: Request,
    *,
    action: str,
    subjects: list[tuple[str, str]],
) -> None:
    settings = request.app.state.settings
    limiter = RedisRateLimiter(request.app.state.redis)
    limit = getattr(settings, f"auth_{action}_rate_limit")

    for subject_name, subject_value in subjects:
        allowed = await limiter.allow(
            key=f"auth:{action}:{subject_name}:{subject_value}",
            limit=limit,
            window_seconds=settings.auth_rate_window_seconds,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please retry later.",
            )


async def _revoke_all_refresh_sessions(session: AsyncSession, *, user_id: str) -> None:
    refresh_sessions = list(
        await session.scalars(
            select(RefreshTokenSession).where(RefreshTokenSession.user_id == user_id)
        )
    )
    revoked_at = datetime.now(timezone.utc)
    for refresh_session in refresh_sessions:
        refresh_session.revoked_at = revoked_at


async def _persist_refresh_session(
    *,
    session: AsyncSession,
    user_id: str,
    refresh_token: str,
    expires_at: datetime,
    replaced_from: RefreshTokenSession | None = None,
) -> RefreshTokenSession:
    refresh_session = RefreshTokenSession(
        user_id=user_id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )
    session.add(refresh_session)
    await session.flush()

    if replaced_from is not None:
        replaced_from.revoked_at = datetime.now(timezone.utc)
        replaced_from.replaced_by_token_hash = refresh_session.token_hash

    return refresh_session


@router.post("/register", response_model=Envelope[AuthSessionData], status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[AuthSessionData]:
    normalized_email = payload.email.strip().lower()
    await _enforce_auth_rate_limit(
        request,
        action="register",
        subjects=[("ip", _client_identifier(request)), ("email", normalized_email)],
    )
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
    await _persist_refresh_session(
        session=session,
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=_refresh_token_expires_at(request),
    )
    await session.commit()
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
    await _enforce_auth_rate_limit(
        request,
        action="login",
        subjects=[("ip", _client_identifier(request)), ("email", normalized_email)],
    )
    user = await session.scalar(select(User).where(User.email == normalized_email))

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token, refresh_token = _issue_tokens(request, user.id)
    user.last_login = datetime.now(timezone.utc)
    await _persist_refresh_session(
        session=session,
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=_refresh_token_expires_at(request),
    )
    await session.commit()
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

    token_fingerprint = hash_token(refresh_token)
    refresh_session = await session.scalar(
        select(RefreshTokenSession).where(
            RefreshTokenSession.user_id == user.id,
            RefreshTokenSession.token_hash == token_fingerprint,
        )
    )
    if refresh_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token session not found")
    if refresh_session.revoked_at is not None:
        if refresh_session.replaced_by_token_hash is not None:
            await _revoke_all_refresh_sessions(session, user_id=user.id)
            await session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token already rotated")
    expires_at = refresh_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    access_token, new_refresh_token = _issue_tokens(request, user.id)
    await _persist_refresh_session(
        session=session,
        user_id=user.id,
        refresh_token=new_refresh_token,
        expires_at=_refresh_token_expires_at(request),
        replaced_from=refresh_session,
    )
    await session.commit()
    _set_auth_cookies(request, response, access_token, new_refresh_token)

    return Envelope(
        success=True,
        data=TokenRefreshData(access_token=access_token, refresh_token=new_refresh_token),
        error=None,
    )


@router.get("/me", response_model=Envelope[MeData])
async def me(current_user: User = Depends(get_current_user)) -> Envelope[MeData]:
    return Envelope(success=True, data=MeData(user=_build_auth_user(current_user)), error=None)


@router.post("/logout", response_model=Envelope[dict[str, bool]])
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[dict[str, bool]]:
    settings = request.app.state.settings
    refresh_token = request.cookies.get(settings.refresh_cookie_name)

    if refresh_token is not None:
        try:
            payload = decode_token(
                refresh_token,
                secret_key=settings.jwt_secret_key,
                algorithm=settings.jwt_algorithm,
            )
        except Exception:
            payload = None

        if payload is not None and payload.get("type") == "refresh":
            token_fingerprint = hash_token(refresh_token)
            refresh_session = await session.scalar(
                select(RefreshTokenSession).where(
                    RefreshTokenSession.user_id == payload.get("sub"),
                    RefreshTokenSession.token_hash == token_fingerprint,
                )
            )
            if refresh_session is not None and refresh_session.revoked_at is None:
                refresh_session.revoked_at = datetime.now(timezone.utc)
                await session.commit()

    _clear_auth_cookies(request, response)
    return Envelope(success=True, data={"logged_out": True}, error=None)


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

    pipeline_runs = list(await session.scalars(select(PipelineRun).where(PipelineRun.user_id == current_user.id)))
    redis_client = request.app.state.redis.client
    checkpoint_keys: list[str] = []
    for run in pipeline_runs:
        checkpoint_keys.append(f"pipeline_run_state:{run.id}")
        checkpoint_keys.append(f"pipeline_run_checkpoint:{run.id}")
    if checkpoint_keys:
        await redis_client.delete(*checkpoint_keys)

    await session.delete(current_user)
    await session.commit()
    _clear_auth_cookies(request, response)

    return Envelope(success=True, data=DeleteAccountData(deleted=True), error=None)
