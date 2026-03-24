from __future__ import annotations

import hashlib

from app.core.security import EncryptionService
from app.models.resume_profile import ResumeProfile
from app.models.search_preference import SearchPreference
from app.models.user import User
from app.schemas.resume import ParsedResumeProfile, SearchPreferencesPayload
from app.services.embedding_service import EmbeddingService
from app.services.file_extraction_service import FileExtractionService
from app.services.profile_completeness_service import ProfileCompletenessService
from app.services.resume_parser_service import ResumeParserService


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
        raw_text = self._extraction_service.extract_text(filename, content)
        parsed_profile = self._parser_service.parse(raw_text)
        embedding = self._embedding_service.embed_text(parsed_profile.summary_for_matching)
        encrypted_text = self._encryption_service.encrypt_for_user(user.id, raw_text)
        file_hash = hashlib.sha256(content).hexdigest()

        resume_profile = user.resume_profile or ResumeProfile(user_id=user.id, file_hash=file_hash, raw_text="")
        resume_profile.raw_text = encrypted_text
        resume_profile.parsed_profile = parsed_profile.model_dump()
        resume_profile.resume_embedding = embedding
        resume_profile.file_hash = file_hash

        return resume_profile, parsed_profile

    def upsert_preferences(self, *, user: User, payload: SearchPreferencesPayload) -> SearchPreference:
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
        return preferences

    def completeness(self, profile: ParsedResumeProfile):
        return self._completeness_service.score(profile)
