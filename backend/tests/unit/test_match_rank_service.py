from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.job import Job
from app.models.job_match import JobMatch
from app.schemas.match import RankedJobItem, RankedJobScoreBreakdown
from app.schemas.resume import SearchPreferencesPayload
from app.services.embedding_service import EmbeddingService
from app.services.match_rank_service import MatchRankService, RankedJobResult


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


def test_user_id_accepts_simple_namespace_proxy() -> None:
    from app.services.match_rank_service import _user_id

    assert _user_id(SimpleNamespace(id="user-123")) == "user-123"


def test_ranked_jobs_can_be_scoped_to_fresh_scrape_batch(tmp_path: Path) -> None:
    async def run_test() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'match-rank.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        service = MatchRankService(embedding_service=EmbeddingService())

        job_one = Job(
            id="job-1",
            external_id="job-1",
            source="linkedin",
            title="ML Engineer",
            company_name="Example AI",
            company_domain="example.ai",
            location="Remote",
            is_remote=True,
            salary_min=2500000,
            salary_max=3500000,
            description_text="Build ML systems with Python and FastAPI.",
            description_embedding=[0.2, 0.3, 0.4],
            apply_url="https://jobs.example.ai/1",
            scraped_at=datetime.now(UTC),
        )
        job_two = Job(
            id="job-2",
            external_id="job-2",
            source="linkedin",
            title="Data Engineer",
            company_name="Example Data",
            company_domain="exampledata.ai",
            location="Remote",
            is_remote=True,
            salary_min=2200000,
            salary_max=3200000,
            description_text="Build data systems with Python and SQL.",
            description_embedding=[0.1, 0.2, 0.3],
            apply_url="https://jobs.example.ai/2",
            scraped_at=datetime.now(UTC),
        )

        async with session_factory() as session:
            session.add_all([job_one, job_two])
            await session.commit()

            user = SimpleNamespace(
                id="user-123",
                resume_profile=SimpleNamespace(
                    parsed_profile={
                        "name": "Pipeline User",
                        "email": "pipeline-user@example.com",
                        "current_title": "ML Engineer",
                        "years_of_experience": 5,
                        "seniority_level": "senior",
                        "skills": {"technical": ["Python", "FastAPI"], "soft": [], "tools": [], "languages": []},
                        "experience": [],
                        "education": [],
                        "preferred_roles": ["ML Engineer"],
                        "inferred_salary_range": {"min": 2500000, "max": 3500000, "currency": "INR"},
                        "work_style_signals": [],
                        "summary_for_matching": "ML engineer with Python and FastAPI experience.",
                    },
                    resume_embedding=[0.1] * 768
                ),
                search_preferences=SimpleNamespace(
                    target_roles=["ML Engineer"],
                    preferred_locations=["Remote"],
                    remote_preference="remote",
                    salary_min=2500000,
                    salary_max=4000000,
                    currency="INR",
                    excluded_companies=[],
                    seniority_level="senior",
                    is_active=True,
                ),
            )

            def _score_job(*, job: Job, resume, preferences, resume_embedding) -> RankedJobResult:
                item = RankedJobItem(
                    job_id=job.id,
                    title=job.title,
                    company_name=job.company_name,
                    source=job.source,
                    location=job.location,
                    is_remote=job.is_remote,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                    apply_url=job.apply_url,
                    match_score=0.9,
                    score_breakdown=RankedJobScoreBreakdown(
                        semantic_similarity=0.9,
                        skills_coverage=0.9,
                        seniority_alignment=0.9,
                        location_match=1.0,
                        salary_alignment=1.0,
                    ),
                    matched_skills=["Python"],
                    missing_skills=[],
                    recommendation="strong_match",
                    one_line_reason="Strong overlap on Python.",
                )
                return RankedJobResult(job=job, item=item)

            service._score_job = _score_job  # type: ignore[method-assign]

            batch = await service.list_ranked_jobs(
                session=session,
                user=user,
                apply_urls=["https://jobs.example.ai/2"],
            )

        assert batch.total == 1
        assert batch.items[0].job_id == "job-2"

        await engine.dispose()

    anyio.run(run_test)


def test_ranked_jobs_update_existing_matches_without_duplicate_inserts(tmp_path: Path) -> None:
    async def run_test() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'match-rank-update.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        service = MatchRankService(embedding_service=EmbeddingService())

        job_one = Job(
            id="job-1",
            external_id="job-1",
            source="linkedin",
            title="ML Engineer",
            company_name="Example AI",
            company_domain="example.ai",
            location="Remote",
            is_remote=True,
            salary_min=2500000,
            salary_max=3500000,
            description_text="Build ML systems with Python and FastAPI.",
            description_embedding=[0.2, 0.3, 0.4],
            apply_url="https://jobs.example.ai/1",
            scraped_at=datetime.now(UTC),
        )
        job_two = Job(
            id="job-2",
            external_id="job-2",
            source="linkedin",
            title="Data Engineer",
            company_name="Example Data",
            company_domain="exampledata.ai",
            location="Remote",
            is_remote=True,
            salary_min=2200000,
            salary_max=3200000,
            description_text="Build data systems with Python and SQL.",
            description_embedding=[0.1, 0.2, 0.3],
            apply_url="https://jobs.example.ai/2",
            scraped_at=datetime.now(UTC),
        )

        async with session_factory() as session:
            session.add_all([job_one, job_two])
            await session.commit()

            session.add(
                JobMatch(
                    user_id="user-123",
                    job_id="job-1",
                    match_score=0.1,
                    score_breakdown={
                        "semantic_similarity": 0.1,
                        "skills_coverage": 0.1,
                        "seniority_alignment": 0.1,
                        "location_match": 0.1,
                        "salary_alignment": 0.1,
                    },
                    matched_skills=[],
                    missing_skills=["Python"],
                    recommendation="skip",
                    one_line_reason="Old result.",
                )
            )
            await session.commit()

            user = SimpleNamespace(
                id="user-123",
                resume_profile=SimpleNamespace(
                    parsed_profile={
                        "name": "Pipeline User",
                        "email": "pipeline-user@example.com",
                        "current_title": "ML Engineer",
                        "years_of_experience": 5,
                        "seniority_level": "senior",
                        "skills": {"technical": ["Python", "FastAPI"], "soft": [], "tools": [], "languages": []},
                        "experience": [],
                        "education": [],
                        "preferred_roles": ["ML Engineer"],
                        "inferred_salary_range": {"min": 2500000, "max": 3500000, "currency": "INR"},
                        "work_style_signals": [],
                        "summary_for_matching": "ML engineer with Python and FastAPI experience.",
                    },
                    resume_embedding=[0.1] * 768
                ),
                search_preferences=SimpleNamespace(
                    target_roles=["ML Engineer"],
                    preferred_locations=["Remote"],
                    remote_preference="remote",
                    salary_min=2500000,
                    salary_max=4000000,
                    currency="INR",
                    excluded_companies=[],
                    seniority_level="senior",
                    is_active=True,
                ),
            )

            def _score_job(*, job: Job, resume, preferences, resume_embedding) -> RankedJobResult:
                item = RankedJobItem(
                    job_id=job.id,
                    title=job.title,
                    company_name=job.company_name,
                    source=job.source,
                    location=job.location,
                    is_remote=job.is_remote,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                    apply_url=job.apply_url,
                    match_score=0.9,
                    score_breakdown=RankedJobScoreBreakdown(
                        semantic_similarity=0.9,
                        skills_coverage=0.9,
                        seniority_alignment=0.9,
                        location_match=1.0,
                        salary_alignment=1.0,
                    ),
                    matched_skills=["Python"],
                    missing_skills=[],
                    recommendation="strong_match",
                    one_line_reason="Strong overlap on Python.",
                )
                return RankedJobResult(job=job, item=item)

            service._score_job = _score_job  # type: ignore[method-assign]

            batch = await service.list_ranked_jobs(session=session, user=user)

            matches = list(await session.scalars(select(JobMatch).where(JobMatch.user_id == "user-123")))
            updated_match = await session.scalar(
                select(JobMatch).where(JobMatch.user_id == "user-123", JobMatch.job_id == "job-1")
            )

        assert batch.total == 2
        assert len(matches) == 2
        assert updated_match is not None
        assert updated_match.match_score == 0.9
        assert updated_match.recommendation == "strong_match"

        await engine.dispose()

    anyio.run(run_test)