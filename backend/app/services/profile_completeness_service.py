from __future__ import annotations

import structlog

from app.core.logging_safety import log_debug, log_exception
from app.schemas.resume import ParsedResumeProfile, ProfileCompletenessData


logger = structlog.get_logger(__name__)


class ProfileCompletenessService:
    def score(self, profile: ParsedResumeProfile) -> ProfileCompletenessData:
        log_debug(logger, "profile_completeness.score.start")
        try:
            checks = {
                "name": bool(profile.name),
                "email": bool(profile.email),
                "current_title": bool(profile.current_title),
                "skills": bool(profile.skills.technical),
                "experience": bool(profile.experience),
                "education": bool(profile.education),
                "preferred_roles": bool(profile.preferred_roles),
                "summary_for_matching": bool(profile.summary_for_matching),
            }

            missing_fields = [field for field, present in checks.items() if not present]
            score = int(round((len(checks) - len(missing_fields)) / len(checks) * 100))

            recommendations = [
                f"Add or improve {field.replace('_', ' ')} to strengthen job matching."
                for field in missing_fields
            ]

            log_debug(
                logger,
                "profile_completeness.score.complete",
                score=score,
                missing_fields=missing_fields,
            )
            return ProfileCompletenessData(
                score=score,
                missing_fields=missing_fields,
                recommendations=recommendations,
            )
        except Exception as error:
            log_exception(logger, "profile_completeness.score.failed", error)
            raise
