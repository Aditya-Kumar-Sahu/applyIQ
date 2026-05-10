from __future__ import annotations

import math
import re
from dataclasses import dataclass

import structlog
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_safety import log_debug, log_exception
from app.core.cache import cached
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.schemas.match import JobDetailData, JobsListData, RankedJobItem, RankedJobScoreBreakdown
from app.schemas.resume import ParsedResumeProfile, SearchPreferencesPayload
from app.services.embedding_service import EmbeddingService

_REMOTE_LOCATION_KEYWORDS = {"remote", "wfh", "anywhere", "worldwide"}


def _normalize_location(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _contains_remote_keyword(value: str) -> bool:
    normalized_tokens = set(_normalize_location(value).split())
    return any(keyword in normalized_tokens for keyword in _REMOTE_LOCATION_KEYWORDS)


def _is_remote_preference(value: str) -> bool:
    return _normalize_location(value) in _REMOTE_LOCATION_KEYWORDS


@dataclass
class RankedJobResult:
    job: Job
    item: RankedJobItem


logger = structlog.get_logger(__name__)


def _user_id(user: User) -> str:
    user_id = getattr(user, "id", None)
    if user_id is not None:
        return str(user_id)

    identity = inspect(user).identity
    if identity and identity[0] is not None:
        return str(identity[0])
    raise ValueError("User identity is unavailable")


class MatchRankService:
    def __init__(self, *, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service

    @cached(ttl=3600, namespace="user:{user}:rankings")
    async def list_ranked_jobs(
        self,
        *,
        session: AsyncSession,
        user: User,
        apply_urls: list[str] | None = None,
    ) -> JobsListData:
        user_id = _user_id(user)
        log_debug(logger, "match_rank.list_ranked_jobs.start", user_id=user_id)
        try:
            ranked = await self._rank_jobs(session=session, user=user, apply_urls=apply_urls)
            log_debug(
                logger,
                "match_rank.list_ranked_jobs.complete",
                user_id=user_id,
                ranked_count=len(ranked),
            )
            return JobsListData(total=len(ranked), items=[result.item for result in ranked])
        except Exception as error:
            log_exception(logger, "match_rank.list_ranked_jobs.failed", error, user_id=user_id)
            raise

    async def get_job_detail(self, *, session: AsyncSession, user: User, job_id: str) -> JobDetailData | None:
        user_id = _user_id(user)
        log_debug(logger, "match_rank.get_job_detail.start", user_id=user_id, job_id=job_id)
        try:
            ranked = await self._rank_jobs(session=session, user=user)
            for result in ranked:
                if result.job.id == job_id:
                    log_debug(
                        logger,
                        "match_rank.get_job_detail.found",
                        user_id=user_id,
                        job_id=job_id,
                        match_score=result.item.match_score,
                    )
                    return JobDetailData(
                        **result.item.model_dump(),
                        company_domain=result.job.company_domain,
                        description_text=result.job.description_text,
                        posted_at=result.job.posted_at,
                    )
            log_debug(logger, "match_rank.get_job_detail.not_found", user_id=user_id, job_id=job_id)
            return None
        except Exception as error:
            log_exception(logger, "match_rank.get_job_detail.failed", error, user_id=user_id, job_id=job_id)
            raise

    async def semantic_search(self, *, session: AsyncSession, user: User, query: str) -> JobsListData:
        user_id = _user_id(user)
        log_debug(
            logger,
            "match_rank.semantic_search.start",
            user_id=user_id,
            query_length=len(query),
        )
        try:
            query_embedding = self._embedding_service.embed_text(query)

            # Use pgvector cosine_distance for direct DB-level semantic search
            stmt = (
                select(Job)
                .where(Job.is_active.is_(True))
                .order_by(Job.description_embedding.cosine_distance(query_embedding))
                .limit(50)
            )
            jobs = list(await session.scalars(stmt))

            # Now rank these top 50 semantic matches using the full scoring logic
            # This is much faster than ranking ALL jobs in Python
            resume_profile = user.resume_profile
            if not resume_profile:
                return JobsListData(total=0, items=[])

            resume = ParsedResumeProfile.model_validate(resume_profile.parsed_profile)
            preferences = self._serialize_preferences(user)
            resume_emb = resume_profile.resume_embedding or resume_summary_embedding(resume)

            ranked_results = []
            for job in jobs:
                result = self._score_job(job=job, resume=resume, preferences=preferences, resume_embedding=resume_emb)
                ranked_results.append(result.item)

            log_debug(
                logger,
                "match_rank.semantic_search.complete",
                user_id=user_id,
                returned_count=len(ranked_results),
            )
            return JobsListData(total=len(ranked_results), items=ranked_results)
        except Exception as error:
            log_exception(
                logger,
                "match_rank.semantic_search.failed",
                error,
                user_id=user_id,
                query_length=len(query),
            )
            raise

    async def _rank_jobs(
        self,
        *,
        session: AsyncSession,
        user: User,
        apply_urls: list[str] | None = None,
    ) -> list[RankedJobResult]:
        user_id = _user_id(user)
        log_debug(logger, "match_rank.rank_jobs.start", user_id=user_id)
        if user.resume_profile is None:
            log_debug(logger, "match_rank.rank_jobs.no_resume_profile", user_id=user_id)
            return []

        if apply_urls is not None and len(apply_urls) == 0:
            log_debug(logger, "match_rank.rank_jobs.empty_batch", user_id=user_id)
            return []

        try:
            resume_profile = user.resume_profile
            resume = ParsedResumeProfile.model_validate(resume_profile.parsed_profile)
            preferences = self._serialize_preferences(user)

            resume_embedding = resume_profile.resume_embedding
            # Avoid ambiguous truth value checks for sequences (e.g., numpy arrays)
            if resume_embedding is None or (hasattr(resume_embedding, "__len__") and len(resume_embedding) == 0):
                resume_embedding = resume_summary_embedding(resume)

            from app.models.application import Application

            seen_job_ids = set(
                (await session.scalars(select(Application.job_id).where(Application.user_id == user_id))).all()
            )

            # Optimizing Job Query: Select similarity as part of the query
            similarity_col = (1 - Job.description_embedding.cosine_distance(resume_embedding)).label("similarity")
            job_query = select(Job, similarity_col).where(Job.is_active.is_(True))

            if apply_urls:
                job_query = job_query.where(Job.apply_url.in_(apply_urls))

            # If no specific URLs, limit to top 100 by similarity to avoid massive Python loops
            if not apply_urls:
                job_query = job_query.order_by(Job.description_embedding.cosine_distance(resume_embedding)).limit(100)
            else:
                job_query = job_query.order_by(Job.scraped_at.desc())

            results = await session.execute(job_query)
            job_rows = results.all()  # list of (Job, similarity)

            job_ids = [row[0].id for row in job_rows]
            existing_matches_by_job_id: dict[str, JobMatch] = {}
            if job_ids:
                existing_matches = list(
                    await session.scalars(
                        select(JobMatch).where(
                            JobMatch.user_id == user_id,
                            JobMatch.job_id.in_(job_ids),
                        )
                    )
                )
                existing_matches_by_job_id = {match.job_id: match for match in existing_matches}

            log_debug(
                logger,
                "match_rank.rank_jobs.loaded_inputs",
                user_id=user_id,
                total_jobs=len(job_rows),
            )

            ranked_results: list[RankedJobResult] = []
            for job, similarity in job_rows:
                if job.id in seen_job_ids:
                    continue

                allowed, _ = self._passes_filters_with_reason(job=job, preferences=preferences)
                if not allowed:
                    continue

                try:
                    # Pass pre-calculated similarity to avoid redundant Python math
                    result = self._score_job(
                        job=job,
                        resume=resume,
                        preferences=preferences,
                        resume_embedding=resume_embedding,
                        precalculated_similarity=float(similarity or 0.0),
                    )
                    ranked_results.append(result)
                    await self._upsert_job_match(
                        session=session,
                        user=user,
                        result=result,
                        existing=existing_matches_by_job_id.get(job.id),
                    )
                except Exception as error:
                    log_exception(logger, "match_rank.rank_jobs.score_failed", error, job_id=job.id)
                    raise

            await session.commit()
            ranked_results.sort(key=lambda result: result.item.match_score, reverse=True)
            return ranked_results
        except Exception as error:
            log_exception(logger, "match_rank.rank_jobs.failed", error, user_id=user_id)
            raise

    def _serialize_preferences(self, user: User) -> SearchPreferencesPayload:
        if user.search_preferences is None:
            return SearchPreferencesPayload()

        preferences = user.search_preferences
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

    def _passes_filters(self, *, job: Job, preferences: SearchPreferencesPayload) -> bool:
        passes, _ = self._passes_filters_with_reason(job=job, preferences=preferences)
        return passes

    def _passes_filters_with_reason(self, *, job: Job, preferences: SearchPreferencesPayload) -> tuple[bool, str]:
        if job.company_name.lower() in {company.lower() for company in preferences.excluded_companies}:
            return False, "excluded_company"

        if preferences.remote_preference == "remote" and not job.is_remote:
            return False, "remote_required"

        if preferences.preferred_locations and not self._matches_preferred_location(
            job=job,
            preferred_locations=preferences.preferred_locations,
        ):
            return False, "location_mismatch"

        if (
            preferences.salary_min is not None
            and job.salary_max is not None
            and job.salary_max < preferences.salary_min
        ):
            return False, "salary_below_min"

        if (
            preferences.salary_max is not None
            and job.salary_min is not None
            and job.salary_min > preferences.salary_max
        ):
            return False, "salary_above_max"

        return True, "passed"

    def _score_job(
        self,
        *,
        job: Job,
        resume: ParsedResumeProfile,
        preferences: SearchPreferencesPayload,
        resume_embedding: list[float],
        precalculated_similarity: float | None = None,
    ) -> RankedJobResult:
        log_debug(
            logger,
            "match_rank.score_job.start",
            job_id=job.id,
            job_title=job.title,
            company_name=job.company_name,
        )
        if precalculated_similarity is not None:
            semantic_similarity = precalculated_similarity
        else:
            semantic_similarity = self._cosine_similarity(resume_embedding, job.description_embedding)

        matched_skills, missing_skills, skills_coverage = self._skills_alignment(job=job, resume=resume)
        seniority_alignment = self._seniority_alignment(job=job, resume=resume, preferences=preferences)
        location_match = self._location_match(job=job, preferences=preferences)
        salary_alignment = self._salary_alignment(job=job, resume=resume, preferences=preferences)
        log_debug(
            logger,
            "match_rank.score_job.components",
            job_id=job.id,
            semantic_similarity=round(semantic_similarity, 4),
            skills_coverage=round(skills_coverage, 4),
            seniority_alignment=round(seniority_alignment, 4),
            location_match=round(location_match, 4),
            salary_alignment=round(salary_alignment, 4),
            matched_skills_count=len(matched_skills),
            missing_skills_count=len(missing_skills),
        )

        match_score = round(
            (semantic_similarity * 0.4)
            + (skills_coverage * 0.25)
            + (seniority_alignment * 0.15)
            + (location_match * 0.1)
            + (salary_alignment * 0.1),
            4,
        )
        score_breakdown = RankedJobScoreBreakdown(
            semantic_similarity=round(semantic_similarity, 4),
            skills_coverage=round(skills_coverage, 4),
            seniority_alignment=round(seniority_alignment, 4),
            location_match=round(location_match, 4),
            salary_alignment=round(salary_alignment, 4),
        )
        recommendation = self._recommendation(match_score)
        reason = self._build_reason(
            matched_skills=matched_skills, missing_skills=missing_skills, recommendation=recommendation
        )

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
            match_score=match_score,
            score_breakdown=score_breakdown,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            recommendation=recommendation,
            one_line_reason=reason,
        )
        log_debug(
            logger,
            "match_rank.score_job.complete",
            job_id=job.id,
            match_score=match_score,
            recommendation=recommendation,
        )
        return RankedJobResult(job=job, item=item)

    def _skills_alignment(self, *, job: Job, resume: ParsedResumeProfile) -> tuple[list[str], list[str], float]:
        resume_skills = {skill.lower(): skill for skill in resume.skills.technical}
        job_tokens = set(re.findall(r"[a-z0-9+#.]+", job.description_text.lower()))
        matched = [original for lowered, original in resume_skills.items() if lowered in job_tokens]
        missing = [original for lowered, original in resume_skills.items() if lowered not in job_tokens][:3]
        coverage = len(matched) / max(len(resume.skills.technical), 1)
        return matched, missing, min(max(coverage, 0.0), 1.0)

    def _seniority_alignment(
        self, *, job: Job, resume: ParsedResumeProfile, preferences: SearchPreferencesPayload
    ) -> float:
        desired_level = preferences.seniority_level or resume.seniority_level
        desired_rank = _seniority_rank(desired_level)
        job_rank = _seniority_rank(job.title)
        difference = abs(desired_rank - job_rank)
        if difference == 0:
            return 1.0
        if difference == 1:
            return 0.75
        return 0.45

    def _location_match(self, *, job: Job, preferences: SearchPreferencesPayload) -> float:
        if preferences.remote_preference == "remote":
            return 1.0 if job.is_remote or _contains_remote_keyword(job.location) else 0.0

        if not preferences.preferred_locations:
            return 1.0

        if job.is_remote:
            return 1.0

        if self._matches_preferred_location(job=job, preferred_locations=preferences.preferred_locations):
            return 1.0

        return 0.5

    def _salary_alignment(
        self, *, job: Job, resume: ParsedResumeProfile, preferences: SearchPreferencesPayload
    ) -> float:
        target_min = preferences.salary_min or resume.inferred_salary_range.min
        target_max = preferences.salary_max or resume.inferred_salary_range.max
        if job.salary_min is None or job.salary_max is None:
            return 0.6
        if job.salary_min <= target_max and job.salary_max >= target_min:
            return 1.0
        return 0.35

    async def _upsert_job_match(
        self,
        *,
        session: AsyncSession,
        user: User,
        result: RankedJobResult,
        existing: JobMatch | None = None,
    ) -> None:
        user_id = _user_id(user)
        log_debug(
            logger,
            "match_rank.upsert_job_match.start",
            user_id=user_id,
            job_id=result.job.id,
        )
        created = False
        if existing is None:
            existing = JobMatch(user_id=user_id, job_id=result.job.id)
            session.add(existing)
            created = True

        existing.match_score = result.item.match_score
        existing.score_breakdown = result.item.score_breakdown.model_dump()
        existing.matched_skills = result.item.matched_skills
        existing.missing_skills = result.item.missing_skills
        existing.recommendation = result.item.recommendation
        existing.one_line_reason = result.item.one_line_reason
        log_debug(
            logger,
            "match_rank.upsert_job_match.complete",
            user_id=user_id,
            job_id=result.job.id,
            created=created,
            match_score=result.item.match_score,
        )

    def _matches_preferred_location(self, *, job: Job, preferred_locations: list[str]) -> bool:
        normalized_job_location = _normalize_location(job.location)
        normalized_preferred_locations = {_normalize_location(location) for location in preferred_locations}

        if job.is_remote:
            return True

        if normalized_job_location in normalized_preferred_locations:
            return True

        if _contains_remote_keyword(job.location) and any(
            _is_remote_preference(location) for location in preferred_locations
        ):
            return True

        return any(
            preferred in normalized_job_location or normalized_job_location in preferred
            for preferred in normalized_preferred_locations
        )

    def _recommendation(self, match_score: float) -> str:
        if match_score >= 0.8:
            return "strong_match"
        if match_score >= 0.65:
            return "good_match"
        if match_score >= 0.5:
            return "stretch"
        return "skip"

    def _build_reason(self, *, matched_skills: list[str], missing_skills: list[str], recommendation: str) -> str:
        if recommendation == "strong_match":
            return f"Strong overlap on {', '.join(matched_skills[:3]) or 'core requirements'}."
        if missing_skills:
            return f"Good fit overall, with gaps around {', '.join(missing_skills[:2])}."
        return "Relevant profile alignment with manageable gaps."

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        # Avoid ambiguous truth value evaluation for array-like inputs (e.g., numpy arrays)
        if left is None or right is None:
            return 0.0
        if (hasattr(left, "__len__") and len(left) == 0) or (hasattr(right, "__len__") and len(right) == 0):
            return 0.0
        numerator = sum(left_value * right_value for left_value, right_value in zip(left, right))
        left_magnitude = math.sqrt(sum(value * value for value in left)) or 1.0
        right_magnitude = math.sqrt(sum(value * value for value in right)) or 1.0
        return max(min(numerator / (left_magnitude * right_magnitude), 1.0), 0.0)


def resume_summary_embedding(resume: ParsedResumeProfile) -> list[float]:
    from app.services.embedding_service import EmbeddingService

    return EmbeddingService().embed_text(resume.summary_for_matching)


def _seniority_rank(value: str) -> int:
    lowered = value.lower()
    if "principal" in lowered:
        return 5
    if "lead" in lowered:
        return 4
    if "senior" in lowered:
        return 3
    if "junior" in lowered:
        return 1
    return 2
