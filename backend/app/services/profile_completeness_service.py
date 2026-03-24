from __future__ import annotations

from app.schemas.resume import ParsedResumeProfile, ProfileCompletenessData


class ProfileCompletenessService:
    def score(self, profile: ParsedResumeProfile) -> ProfileCompletenessData:
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

        return ProfileCompletenessData(
            score=score,
            missing_fields=missing_fields,
            recommendations=recommendations,
        )
