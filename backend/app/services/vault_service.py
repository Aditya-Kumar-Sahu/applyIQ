from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.logging_safety import log_debug, log_exception
from app.models.credential_vault import CredentialVault
from app.models.user import User
from app.schemas.vault import CredentialStorePayload, DeleteCredentialData, VaultCredentialItem, VaultCredentialListData


logger = structlog.get_logger(__name__)


class ResolvedCredential:
    def __init__(self, *, username: str, password: str, site_name: str, site_url: str) -> None:
        self.username = username
        self.password = password
        self.site_name = site_name
        self.site_url = site_url


class VaultService:
    async def store_credential(
        self,
        *,
        session: AsyncSession,
        user: User,
        payload: CredentialStorePayload,
        encryption_service,
    ) -> VaultCredentialItem:
        log_debug(logger, "vault.store_credential.start", user_id=user.id, site_name=payload.site_name)
        try:
            existing = await session.scalar(
                select(CredentialVault).where(
                    CredentialVault.user_id == user.id,
                    CredentialVault.site_name == payload.site_name.lower(),
                )
            )
            created = False
            if existing is None:
                existing = CredentialVault(
                    user_id=user.id,
                    site_name=payload.site_name.lower(),
                    site_url=payload.site_url,
                )
                session.add(existing)
                created = True

            existing.site_url = payload.site_url
            existing.encrypted_username = encryption_service.encrypt_for_user(user.id, payload.username)
            existing.encrypted_password = encryption_service.encrypt_for_user(user.id, payload.password)
            await session.commit()
            await session.refresh(existing)
            log_debug(
                logger,
                "vault.store_credential.complete",
                user_id=user.id,
                credential_id=existing.id,
                created=created,
            )
            return self._to_item(existing, user_id=user.id, encryption_service=encryption_service)
        except Exception as error:
            log_exception(
                logger,
                "vault.store_credential.failed",
                error,
                user_id=user.id,
                site_name=payload.site_name,
            )
            raise

    async def list_credentials(
        self,
        *,
        session: AsyncSession,
        user: User,
        encryption_service,
    ) -> VaultCredentialListData:
        log_debug(logger, "vault.list_credentials.start", user_id=user.id)
        try:
            credentials = list(
                await session.scalars(
                    select(CredentialVault)
                    .where(CredentialVault.user_id == user.id)
                    .order_by(CredentialVault.created_at.desc())
                )
            )
            log_debug(logger, "vault.list_credentials.loaded", user_id=user.id, credentials_count=len(credentials))
            return VaultCredentialListData(
                items=[
                    self._to_item(credential, user_id=user.id, encryption_service=encryption_service)
                    for credential in credentials
                ]
            )
        except Exception as error:
            log_exception(logger, "vault.list_credentials.failed", error, user_id=user.id)
            raise

    async def delete_credential(self, *, session: AsyncSession, user: User, credential_id: str) -> DeleteCredentialData:
        log_debug(logger, "vault.delete_credential.start", user_id=user.id, credential_id=credential_id)
        credential = await session.scalar(
            select(CredentialVault).where(CredentialVault.user_id == user.id, CredentialVault.id == credential_id)
        )
        if credential is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        await session.delete(credential)
        await session.commit()
        log_debug(logger, "vault.delete_credential.complete", user_id=user.id, credential_id=credential_id)
        return DeleteCredentialData(deleted=True)

    async def resolve_credential(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        site_names: list[str],
        encryption_service,
    ) -> ResolvedCredential | None:
        log_debug(logger, "vault.resolve_credential.start", user_id=user_id, site_names=site_names)
        normalized_site_names = {site_name.lower() for site_name in site_names}
        credentials = list(await session.scalars(select(CredentialVault).where(CredentialVault.user_id == user_id)))
        for credential in credentials:
            if credential.site_name.lower() not in normalized_site_names:
                continue
            credential.last_used_at = datetime.now(timezone.utc)
            await session.commit()
            log_debug(
                logger,
                "vault.resolve_credential.match_found",
                user_id=user_id,
                credential_id=credential.id,
                site_name=credential.site_name,
            )
            return ResolvedCredential(
                username=encryption_service.decrypt_for_user(user_id, credential.encrypted_username),
                password=encryption_service.decrypt_for_user(user_id, credential.encrypted_password),
                site_name=credential.site_name,
                site_url=credential.site_url,
            )
        log_debug(logger, "vault.resolve_credential.no_match", user_id=user_id, site_names=site_names)
        return None

    def _to_item(self, credential: CredentialVault, *, user_id: str, encryption_service) -> VaultCredentialItem:
        username = encryption_service.decrypt_for_user(user_id, credential.encrypted_username)
        log_debug(
            logger,
            "vault.to_item",
            user_id=user_id,
            credential_id=credential.id,
            site_name=credential.site_name,
        )
        return VaultCredentialItem(
            id=credential.id,
            site_name=credential.site_name,
            site_url=credential.site_url,
            masked_username=_mask_username(username),
            created_at=credential.created_at,
            last_used_at=credential.last_used_at,
        )


def _mask_username(username: str) -> str:
    if "@" in username:
        local, domain = username.split("@", 1)
        visible = local[:1]
        masked_local = visible + ("*" * max(len(local) - 1, 2))
        return f"{masked_local}@{domain}"
    return username[:1] + ("*" * max(len(username) - 1, 2))
