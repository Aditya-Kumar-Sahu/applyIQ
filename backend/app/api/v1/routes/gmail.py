from __future__ import annotations

from urllib.parse import urlencode

from httpx import HTTPStatusError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.v1.deps import get_current_user, get_db_session, get_encryption_service
from app.models.email_monitor import EmailMonitor
from app.models.user import User
from app.schemas.common import Envelope
from app.schemas.gmail import GmailAuthUrlData, GmailPollData, GmailStatusData
from app.services.email_monitor_service import EmailMonitorService
from app.services.gmail_service import GmailService


router = APIRouter(prefix="/gmail", tags=["gmail"])
logger = structlog.get_logger(__name__)


def _settings_redirect_url(settings, *, query: dict[str, str] | None = None) -> str:
    base = (settings.cors_origins[0] if settings.cors_origins else "").rstrip("/")
    if not base:
        base = "/settings"
    else:
        base = f"{base}/settings"
    if query:
        return f"{base}?{urlencode(query)}"
    return base


@router.get("/auth-url", response_model=Envelope[GmailAuthUrlData])
async def get_gmail_auth_url(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Envelope[GmailAuthUrlData]:
    settings = request.app.state.settings
    service = GmailService()
    try:
        auth_url = service.build_auth_url(user_id=current_user.id, settings=settings)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Envelope(success=True, data=GmailAuthUrlData(auth_url=auth_url), error=None)


@router.get("/callback", response_class=RedirectResponse)
async def gmail_callback(
    code: str,
    state: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> RedirectResponse:
    settings = request.app.state.settings
    service = GmailService()
    try:
        user_id = service.validate_state(state=state, settings=settings)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    credentials = await service.exchange_code_for_credentials(code=code, settings=settings)
    account_hint = user.email
    try:
        profile = await service.get_profile(access_token=credentials["access_token"])
        profile_email = str(profile.get("emailAddress") or "").strip()
        if profile_email:
            account_hint = profile_email
    except HTTPStatusError as error:
        logger.warning(
            "gmail.callback.profile_lookup_failed",
            user_id=user_id,
            status_code=getattr(error.response, "status_code", None),
        )
    except Exception as error:
        logger.warning(
            "gmail.callback.profile_lookup_failed",
            user_id=user_id,
            error_type=error.__class__.__name__,
        )
    await service.store_credentials(
        session=session,
        user_id=user_id,
        credentials=credentials,
        encryption_service=encryption_service,
        account_hint=account_hint,
    )

    return RedirectResponse(
        url=_settings_redirect_url(settings, query={"gmail": "connected"}),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/status", response_model=Envelope[GmailStatusData])
async def gmail_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[GmailStatusData]:
    service = GmailService()
    credentials = await service.get_credentials(
        session=session,
        user_id=current_user.id,
        encryption_service=encryption_service,
    )
    connected = credentials is not None
    account_hint = None
    if connected:
        account_hint = await service.get_account_hint(
            session=session,
            user_id=current_user.id,
            encryption_service=encryption_service,
        )
        if account_hint is None:
            account_hint = current_user.email

    last_checked_at = await session.scalar(
        select(func.max(EmailMonitor.last_checked_at)).where(EmailMonitor.user_id == current_user.id)
    )
    if connected:
        credential_last_used_at = await service.get_last_used_at(
            session=session,
            user_id=current_user.id,
            encryption_service=encryption_service,
        )
        if credential_last_used_at is not None and (
            last_checked_at is None or credential_last_used_at > last_checked_at
        ):
            last_checked_at = credential_last_used_at
    data = GmailStatusData(
        connected=connected,
        gmail_account_hint=account_hint,
        email=account_hint,
        last_checked_at=last_checked_at,
    )
    return Envelope(success=True, data=data, error=None)


@router.post("/poll", response_model=Envelope[GmailPollData])
async def poll_gmail(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[GmailPollData]:
    settings = request.app.state.settings
    service = EmailMonitorService()
    result = await service.poll_inbox_with_stats(
        session=session,
        user=current_user,
        encryption_service=encryption_service,
        settings=settings,
    )
    data = GmailPollData(
        polled=result.polled,
        processed_messages=result.processed_messages,
        matched_notifications=len(result.notifications.items),
    )
    return Envelope(success=True, data=data, error=None)
