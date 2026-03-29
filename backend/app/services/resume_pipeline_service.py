from __future__ import annotations

import hashlib

import structlog

from app.core.logging_safety import bytes_snapshot, log_debug, log_exception
from app.core.security import EncryptionService
from app.models.resume_profile import ResumeProfile
from app.models.search_preference import SearchPreference
from app.models.user import User
from app.schemas.resume import ParsedResumeProfile, SearchPreferencesPayload
from app.services.embedding_service import EmbeddingService
from app.services.file_extraction_service import FileExtractionService
from app.services.profile_completeness_service import ProfileCompletenessService
from app.services.resume_parser_service import ResumeParserService


logger = structlog.get_logger(__name__)


class ResumePipelineService:
    def __init__(
        self,
        *,
        extraction_service: FileExtractionService,
        parser_service: ResumeParserService,
        embedding_service: EmbeddingService,
        completeness_service: ProfileCompletenessService,
        encryption_service: EncryptionService,
    ) -> None:
        self._extraction_service = extraction_service
        self._parser_service = parser_service
        self._embedding_service = embedding_service
        self._completeness_service = completeness_service
        self._encryption_service = encryption_service

    def process_upload(self, *, user: User, filename: str, content: bytes) -> tuple[ResumeProfile, ParsedResumeProfile]:
        log_debug(
            logger,
            "resume_pipeline.process_upload.start",
            user_id=user.id,
            filename=filename,
            content=bytes_snapshot(content),
        )
        try:
            raw_text = self._extraction_service.extract_text(filename, content)
            log_debug(logger, "resume_pipeline.process_upload.extracted", user_id=user.id, raw_text_length=len(raw_text))

            parsed_profile = self._parser_service.parse(raw_text)
            log_debug(
                logger,
                "resume_pipeline.process_upload.parsed",
                user_id=user.id,
                skills_count=len(parsed_profile.skills.technical),
                experience_entries=len(parsed_profile.experience),
            )

            embedding = self._embedding_service.embed_text(parsed_profile.summary_for_matching)
            log_debug(
                logger,
                "resume_pipeline.process_upload.embedded",
                user_id=user.id,
                embedding_dimensions=len(embedding),
            )

            encrypted_text = self._encryption_service.encrypt_for_user(user.id, raw_text)
            file_hash = hashlib.sha256(content).hexdigest()

            resume_profile = user.resume_profile or ResumeProfile(user_id=user.id, file_hash=file_hash, raw_text="")
            resume_profile.raw_text = encrypted_text
            resume_profile.parsed_profile = parsed_profile.model_dump()
            resume_profile.resume_embedding = embedding
            resume_profile.file_hash = file_hash

            log_debug(
                logger,
                "resume_pipeline.process_upload.complete",
                user_id=user.id,
                file_hash_prefix=file_hash[:12],
                updated_existing=bool(user.resume_profile),
            )
            return resume_profile, parsed_profile
        except Exception as error:
            log_exception(
                logger,
                "resume_pipeline.process_upload.failed",
                error,
                user_id=user.id,
                filename=filename,
                content=bytes_snapshot(content),
            )
            raise

    def upsert_preferences(self, *, user: User, payload: SearchPreferencesPayload) -> SearchPreference:
        log_debug(
            logger,
            "resume_pipeline.upsert_preferences.start",
            user_id=user.id,
            target_roles_count=len(payload.target_roles),
            preferred_locations_count=len(payload.preferred_locations),
        )
        try:
            preferences = user.search_preferences or SearchPreference(user_id=user.id)
            preferences.target_roles = payload.target_roles
            preferences.preferred_locations = payload.preferred_locations
            preferences.remote_preference = payload.remote_preference
            preferences.salary_min = payload.salary_min
            preferences.salary_max = payload.salary_max
            preferences.currency = payload.currency
            preferences.excluded_companies = payload.excluded_companies
            preferences.seniority_level = payload.seniority_level
            preferences.is_active = payload.is_active
            log_debug(
                logger,
                "resume_pipeline.upsert_preferences.complete",
                user_id=user.id,
                excluded_companies_count=len(payload.excluded_companies),
                is_active=payload.is_active,
            )
            return preferences
        except Exception as error:
            log_exception(logger, "resume_pipeline.upsert_preferences.failed", error, user_id=user.id)
            raise

    def reparse_existing_profile(self, *, user: User) -> ParsedResumeProfile:
        if user.resume_profile is None:
            raise ValueError("Resume profile not found")

        log_debug(logger, "resume_pipeline.reparse_existing.start", user_id=user.id)
        try:
            raw_text = self._encryption_service.decrypt_for_user(user.id, user.resume_profile.raw_text)
            parsed_profile = self._parser_service.parse(raw_text)
            embedding = self._embedding_service.embed_text(parsed_profile.summary_for_matching)

            user.resume_profile.parsed_profile = parsed_profile.model_dump()
            user.resume_profile.resume_embedding = embedding

            log_debug(
                logger,
                "resume_pipeline.reparse_existing.complete",
                user_id=user.id,
                skills_count=len(parsed_profile.skills.technical),
                experience_entries=len(parsed_profile.experience),
            )
            return parsed_profile
        except Exception as error:
            log_exception(logger, "resume_pipeline.reparse_existing.failed", error, user_id=user.id)
            raise

    def completeness(self, profile: ParsedResumeProfile):
        log_debug(logger, "resume_pipeline.completeness.start")
        try:
            result = self._completeness_service.score(profile)
            log_debug(logger, "resume_pipeline.completeness.complete", score=result.score)
            return result
        except Exception as error:
            log_exception(logger, "resume_pipeline.completeness.failed", error)
            raise
