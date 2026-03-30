from __future__ import annotations

from app.models.job import Job
from app.schemas.resume import SearchPreferencesPayload
from app.services.embedding_service import EmbeddingService
from app.services.match_rank_service import MatchRankService


def test_location_filters_accept_remote_aliases_and_normalized_city_names() -> None:
    service = MatchRankService(embedding_service=EmbeddingService())

    remote_job = Job(
        id="job-1",
        external_id="job-1",
        source="linkedin",
        title="ML Engineer",
        company_name="Example AI",
        company_domain="example.ai",
        location="Remote - India",
        is_remote=False,
        salary_min=2500000,
        salary_max=3500000,
        description_text="Remote ML role",
        description_embedding=[0.2, 0.3, 0.4],
        apply_url="https://jobs.example.ai/1",
    )
    city_job = Job(
        id="job-2",
        external_id="job-2",
        source="linkedin",
        title="ML Engineer",
        company_name="Example AI",
        company_domain="example.ai",
        location="New York, NY",
        is_remote=False,
        salary_min=2500000,
        salary_max=3500000,
        description_text="NYC ML role",
        description_embedding=[0.2, 0.3, 0.4],
        apply_url="https://jobs.example.ai/2",
    )

    remote_preferences = SearchPreferencesPayload(preferred_locations=["Remote"], remote_preference="any")
    city_preferences = SearchPreferencesPayload(preferred_locations=["New York"], remote_preference="any")

    remote_passes, remote_reason = service._passes_filters_with_reason(job=remote_job, preferences=remote_preferences)
    city_passes, city_reason = service._passes_filters_with_reason(job=city_job, preferences=city_preferences)

    assert remote_passes is True
    assert remote_reason == "passed"
    assert city_passes is True
    assert city_reason == "passed"
    assert service._location_match(job=remote_job, preferences=remote_preferences) == 1.0
    assert service._location_match(job=city_job, preferences=city_preferences) == 1.0