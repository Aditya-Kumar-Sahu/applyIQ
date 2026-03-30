from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db_session, get_encryption_service
from app.models.user import User
from app.schemas.common import Envelope
from app.schemas.resume import (
    ParsedResumeProfile,
    ProfileCompletenessData,
    ResumeDetailData,
    ResumeUploadData,
    SearchPreferencesData,
    SearchPreferencesPayload,
)
from app.services.embedding_service import EmbeddingService
from app.services.file_extraction_service import FileExtractionService
from app.services.profile_completeness_service import ProfileCompletenessService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_pipeline_service import ResumePipelineService


router = APIRouter(prefix="/resume", tags=["resume"])

_ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_BAD_TITLE_MARKERS = {"summary", "professional summary", "experience", "education", "skills"}


def _build_pipeline_service(encryption_service) -> ResumePipelineService:
    return ResumePipelineService(
        extraction_service=FileExtractionService(),
        parser_service=ResumeParserService(),
        embedding_service=EmbeddingService(),
        completeness_service=ProfileCompletenessService(),
        encryption_service=encryption_service,
    )


def _serialize_preferences(preferences) -> SearchPreferencesPayload | None:
    if preferences is None:
        return None

    return SearchPreferencesPayload(
        target_roles=preferences.target_roles,
        preferred_locations=preferences.preferred_locations,
        remote_preference=preferences.remote_preference,
        salary_min=preferences.salary_min,
        salary_max=preferences.salary_max,
        currency=preferences.currency,
        excluded_companies=preferences.excluded_companies,
        seniority_level=preferences.seniority_level,
        is_active=preferences.is_active,
    )


def _should_reparse_profile(profile: ParsedResumeProfile) -> bool:
    if not profile.current_title.strip():
        return True

    normalized_title = profile.current_title.strip().casefold()
    if normalized_title in _BAD_TITLE_MARKERS:
        return True

    if not profile.skills.technical:
        return True

    if len(profile.skills.technical) > 25:
        return True

    if len(profile.education) > 3:
        return True

    if profile.experience:
        first_entry = profile.experience[0]
        if "@" in first_entry.title or re.search(r"\+?\d[\d\s()\-]{7,}", first_entry.company):
            return True

    return False


def _declared_resume_format(filename: str) -> str | None:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return "pdf"
    if lower_name.endswith(".docx"):
        return "docx"
    return None


@router.post("/upload", response_model=Envelope[ResumeUploadData], status_code=status.HTTP_201_CREATED)
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[ResumeUploadData]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing file name")
    declared_format = _declared_resume_format(file.filename)
    if declared_format is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported resume file extension")
    if file.content_type not in _ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file content type")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    settings = request.app.state.settings
    if len(content) > settings.max_resume_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Resume file is too large")
    extraction_service = FileExtractionService()
    detected_format = extraction_service.detect_content_format(content)
    if detected_format != declared_format:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume file content does not match the declared file extension",
        )
    pipeline = _build_pipeline_service(encryption_service)

    try:
        resume_profile, parsed_profile = pipeline.process_upload(
            user=current_user,
            filename=file.filename,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session.add(resume_profile)
    await session.commit()
    await session.refresh(resume_profile)

    return Envelope(
        success=True,
        data=ResumeUploadData(
            profile=parsed_profile,
            file_hash=resume_profile.file_hash,
            embedding_dimensions=len(resume_profile.resume_embedding),
        ),
        error=None,
    )


@router.get("", response_model=Envelope[ResumeDetailData])
async def get_resume(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[ResumeDetailData]:
    if current_user.resume_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")

    pipeline = _build_pipeline_service(encryption_service)
    profile = ParsedResumeProfile.model_validate(current_user.resume_profile.parsed_profile)
    if _should_reparse_profile(profile):
        profile = pipeline.reparse_existing_profile(user=current_user)
        session.add(current_user.resume_profile)
        await session.commit()
        await session.refresh(current_user.resume_profile)

    return Envelope(
        success=True,
        data=ResumeDetailData(
            profile=profile,
            preferences=_serialize_preferences(current_user.search_preferences),
        ),
        error=None,
    )


@router.put("/preferences", response_model=Envelope[SearchPreferencesData])
async def update_preferences(
    payload: SearchPreferencesPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[SearchPreferencesData]:
    pipeline = _build_pipeline_service(encryption_service)
    preferences = pipeline.upsert_preferences(user=current_user, payload=payload)
    session.add(preferences)
    await session.commit()
    await session.refresh(preferences)

    return Envelope(
        success=True,
        data=SearchPreferencesData(preferences=payload),
        error=None,
    )


@router.get("/profile-completeness", response_model=Envelope[ProfileCompletenessData])
async def profile_completeness(
    current_user: User = Depends(get_current_user),
    encryption_service=Depends(get_encryption_service),
) -> Envelope[ProfileCompletenessData]:
    if current_user.resume_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")

    profile = ParsedResumeProfile.model_validate(current_user.resume_profile.parsed_profile)
    completeness = _build_pipeline_service(encryption_service).completeness(profile)
    return Envelope(success=True, data=completeness, error=None)
