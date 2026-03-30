from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging_safety import log_debug, log_exception
from app.models.credential_vault import CredentialVault

import structlog


logger = structlog.get_logger(__name__)


class GmailService:
    _GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    _GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
    _VAULT_SITE_NAME = "gmail_oauth"
    _VAULT_SITE_URL = "https://mail.google.com"

    def build_auth_url(self, *, user_id: str, settings: Settings) -> str:
        self._assert_oauth_configured(settings)
        state_token = self._build_state_token(user_id=user_id, settings=settings)
        query = urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": settings.google_redirect_uri,
                "response_type": "code",
                "scope": settings.gmail_oauth_scope,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state_token,
            }
        )
        return f"{self._GOOGLE_AUTH_URL}?{query}"

    def validate_state(self, *, state: str, settings: Settings) -> str:
        try:
            payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except Exception as error:
            raise ValueError("Invalid OAuth state") from error

        if payload.get("type") != "gmail_oauth":
            raise ValueError("Invalid OAuth state type")

        user_id = str(payload.get("sub") or "").strip()
        if not user_id:
            raise ValueError("Invalid OAuth state subject")
        return user_id

    async def exchange_code_for_credentials(
        self,
        *,
        code: str,
        settings: Settings,
    ) -> dict[str, Any]:
        self._assert_oauth_configured(settings)
        payload = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
        token_payload = await self._token_request(payload=payload)
        return self._normalize_credentials(token_payload)

    async def refresh_credentials_if_expired(
        self,
        *,
        credentials: dict[str, Any],
        settings: Settings,
    ) -> tuple[dict[str, Any], bool]:
        expires_at_raw = credentials.get("expires_at")
        if not isinstance(expires_at_raw, str):
            return credentials, False

        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            return credentials, False

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at > datetime.now(timezone.utc) + timedelta(seconds=60):
            return credentials, False

        refresh_token = credentials.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return credentials, False

        self._assert_oauth_configured(settings)
        payload = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        refreshed = await self._token_request(payload=payload)
        refreshed_credentials = self._normalize_credentials(refreshed, fallback_refresh_token=refresh_token)
        return refreshed_credentials, True

    async def store_credentials(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        credentials: dict[str, Any],
        encryption_service,
        account_hint: str | None = None,
    ) -> CredentialVault:
        credential_row = await session.scalar(
            select(CredentialVault).where(
                CredentialVault.user_id == user_id,
                CredentialVault.site_name == self._VAULT_SITE_NAME,
            )
        )
        if credential_row is None:
            credential_row = CredentialVault(
                user_id=user_id,
                site_name=self._VAULT_SITE_NAME,
                site_url=self._VAULT_SITE_URL,
                encrypted_username="",
                encrypted_password="",
            )
            session.add(credential_row)

        username = account_hint or "gmail-oauth"
        credential_row.encrypted_username = encryption_service.encrypt_for_user(user_id, username)
        credential_row.encrypted_password = encryption_service.encrypt_for_user(
            user_id,
            json.dumps(credentials, separators=(",", ":"), sort_keys=True),
        )
        credential_row.last_used_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(credential_row)
        log_debug(logger, "gmail.store_credentials.complete", user_id=user_id)
        return credential_row

    async def touch_credentials(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        encryption_service,
        account_hint: str | None = None,
    ) -> CredentialVault | None:
        credential_row = await session.scalar(
            select(CredentialVault).where(
                CredentialVault.user_id == user_id,
                CredentialVault.site_name == self._VAULT_SITE_NAME,
            )
        )
        if credential_row is None:
            return None

        normalized_hint = self._normalize_account_hint(account_hint)
        if normalized_hint is not None:
            current_hint = self._normalize_account_hint(
                encryption_service.decrypt_for_user(user_id, credential_row.encrypted_username)
            )
            if current_hint is None:
                credential_row.encrypted_username = encryption_service.encrypt_for_user(user_id, normalized_hint)

        credential_row.last_used_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(credential_row)
        log_debug(logger, "gmail.touch_credentials.complete", user_id=user_id)
        return credential_row

    async def get_credentials(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        encryption_service,
    ) -> dict[str, Any] | None:
        credential_row = await session.scalar(
            select(CredentialVault).where(
                CredentialVault.user_id == user_id,
                CredentialVault.site_name == self._VAULT_SITE_NAME,
            )
        )
        if credential_row is None:
            return None

        try:
            payload = encryption_service.decrypt_for_user(user_id, credential_row.encrypted_password)
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                return None
            return parsed
        except Exception as error:
            log_exception(logger, "gmail.get_credentials.failed", error, user_id=user_id)
            return None

    async def get_account_hint(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        encryption_service,
    ) -> str | None:
        credential_row = await session.scalar(
            select(CredentialVault).where(
                CredentialVault.user_id == user_id,
                CredentialVault.site_name == self._VAULT_SITE_NAME,
            )
        )
        if credential_row is None:
            return None

        try:
            return self._normalize_account_hint(
                encryption_service.decrypt_for_user(user_id, credential_row.encrypted_username)
            )
        except Exception:
            return None

    async def get_last_used_at(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        encryption_service,
    ) -> datetime | None:
        credential_row = await session.scalar(
            select(CredentialVault).where(
                CredentialVault.user_id == user_id,
                CredentialVault.site_name == self._VAULT_SITE_NAME,
            )
        )
        if credential_row is None:
            return None
        return credential_row.last_used_at

    async def list_message_ids(
        self,
        *,
        access_token: str,
        query: str,
        max_results: int,
    ) -> list[str]:
        response = await self._gmail_get(
            access_token=access_token,
            path="/messages",
            params={
                "q": query,
                "maxResults": str(max_results),
            },
        )
        messages = response.get("messages", [])
        if not isinstance(messages, list):
            return []
        message_ids: list[str] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            message_id = item.get("id")
            if isinstance(message_id, str) and message_id:
                message_ids.append(message_id)
        return message_ids

    async def get_message(
        self,
        *,
        access_token: str,
        message_id: str,
    ) -> dict[str, Any]:
        return await self._gmail_get(
            access_token=access_token,
            path=f"/messages/{message_id}",
            params={"format": "full"},
        )

    async def get_profile(self, *, access_token: str) -> dict[str, Any]:
        return await self._gmail_get(access_token=access_token, path="/profile")

    async def _gmail_get(
        self,
        *,
        access_token: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self._GMAIL_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}

    async def _token_request(self, *, payload: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(self._GOOGLE_TOKEN_URL, data=payload)
            response.raise_for_status()
            token_payload = response.json()
            return token_payload if isinstance(token_payload, dict) else {}

    def _normalize_credentials(
        self,
        payload: dict[str, Any],
        *,
        fallback_refresh_token: str | None = None,
    ) -> dict[str, Any]:
        access_token = str(payload.get("access_token") or "")
        refresh_token = str(payload.get("refresh_token") or fallback_refresh_token or "")
        token_type = str(payload.get("token_type") or "Bearer")
        expires_in_raw = payload.get("expires_in")
        expires_in = int(expires_in_raw) if isinstance(expires_in_raw, (int, float, str)) and str(expires_in_raw).isdigit() else 3600
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        scope = str(payload.get("scope") or "")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token_type,
            "scope": scope,
            "expires_at": expires_at.isoformat(),
        }

    def _build_state_token(self, *, user_id: str, settings: Settings) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "type": "gmail_oauth",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def _assert_oauth_configured(self, settings: Settings) -> None:
        missing = [
            name
            for name, value in (
                ("GOOGLE_CLIENT_ID", settings.google_client_id),
                ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
                ("GOOGLE_REDIRECT_URI", settings.google_redirect_uri),
            )
            if value is None or not str(value).strip()
        ]
        if missing:
            raise ValueError("Google OAuth is not configured: " + ", ".join(missing))

    def _normalize_account_hint(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or normalized.lower() == "gmail-oauth":
            return None
        return normalized
