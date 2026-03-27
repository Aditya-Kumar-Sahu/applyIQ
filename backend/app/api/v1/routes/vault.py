from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session, get_encryption_service
from app.models.user import User
from app.schemas.common import Envelope
from app.schemas.vault import CredentialStorePayload, DeleteCredentialData, VaultCredentialItem, VaultCredentialListData
from app.services.vault_service import VaultService


router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/credentials", response_model=Envelope[VaultCredentialItem], status_code=status.HTTP_201_CREATED)
async def store_credentials(
    payload: CredentialStorePayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[VaultCredentialItem]:
    service = VaultService()
    data = await service.store_credential(
        session=session,
        user=current_user,
        payload=payload,
        encryption_service=encryption_service,
    )
    return Envelope(success=True, data=data, error=None)


@router.get("/credentials", response_model=Envelope[VaultCredentialListData])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[VaultCredentialListData]:
    service = VaultService()
    data = await service.list_credentials(
        session=session,
        user=current_user,
        encryption_service=encryption_service,
    )
    return Envelope(success=True, data=data, error=None)


@router.delete("/credentials/{credential_id}", response_model=Envelope[DeleteCredentialData])
async def delete_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[DeleteCredentialData]:
    service = VaultService()
    data = await service.delete_credential(session=session, user=current_user, credential_id=credential_id)
    return Envelope(success=True, data=data, error=None)
