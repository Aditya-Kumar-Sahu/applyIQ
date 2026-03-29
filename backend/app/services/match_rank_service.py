from __future__ import annotations

from collections import defaultdict
import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.logging_safety import log_debug, log_exception
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.schemas.match import JobDetailData, JobsListData, RankedJobItem, RankedJobScoreBreakdown
from app.schemas.resume import ParsedResumeProfile, SearchPreferencesPayload
from app.services.embedding_service import EmbeddingService


@dataclass
class RankedJobResult:
    job: Job
    item: RankedJobItem


logger = structlog.get_logger(__name__)


class MatchRankService:
    def __init__(self, *, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service

    async def list_ranked_jobs(self, *, session: AsyncSession, user: User) -> JobsListData:
        log_debug(logger, "match_rank.list_ranked_jobs.start", user_id=user.id)
        try:
            ranked = await self._rank_jobs(session=session, user=user)
            log_debug(
                logger,
                "match_rank.list_ranked_jobs.complete",
                user_id=user.id,
                ranked_count=len(ranked),
            )
            return JobsListData(total=len(ranked), items=[result.item for result in ranked])
        except Exception as error:
            log_exception(logger, "match_rank.list_ranked_jobs.failed", error, user_id=user.id)
            raise

    async def get_job_detail(self, *, session: AsyncSession, user: User, job_id: str) -> JobDetailData | None:
        log_debug(logger, "match_rank.get_job_detail.start", user_id=user.id, job_id=job_id)
        try:
            ranked = await self._rank_jobs(session=session, user=user)
            for result in ranked:
                if result.job.id == job_id:
                    log_debug(
                        logger,
                        "match_rank.get_job_detail.found",
                        user_id=user.id,
                        job_id=job_id,
                        match_score=result.item.match_score,
                    )
                    return JobDetailData(
                        **result.item.model_dump(),
                        company_domain=result.job.company_domain,
                        description_text=result.job.description_text,
                        posted_at=result.job.posted_at,
                    )
            log_debug(logger, "match_rank.get_job_detail.not_found", user_id=user.id, job_id=job_id)
            return None
        except Exception as error:
            log_exception(logger, "match_rank.get_job_detail.failed", error, user_id=user.id, job_id=job_id)
            raise

    async def semantic_search(self, *, session: AsyncSession, user: User, query: str) -> JobsListData:
        log_debug(
            logger,
            "match_rank.semantic_search.start",
            user_id=user.id,
            query_length=len(query),
        )
        try:
            ranked = await self._rank_jobs(session=session, user=user)
            query_embedding = self._embedding_service.embed_text(query)
            sorted_ranked = sorted(
                ranked,
                key=lambda result: self._cosine_similarity(query_embedding, result.job.description_embedding),
                reverse=True,
            )
            log_debug(
                logger,
                "match_rank.semantic_search.complete",
                user_id=user.id,
                total_ranked=len(sorted_ranked),
            )
            return JobsListData(total=len(sorted_ranked), items=[result.item for result in sorted_ranked])
        except Exception as error:
            log_exception(
                logger,
                "match_rank.semantic_search.failed",
                error,
                user_id=user.id,
                query_length=len(query),
            )
            raise

    async def _rank_jobs(self, *, session: AsyncSession, user: User) -> list[RankedJobResult]:
        log_debug(logger, "match_rank.rank_jobs.start", user_id=user.id)
        if user.resume_profile is None:
            log_debug(logger, "match_rank.rank_jobs.no_resume_profile", user_id=user.id)
            return []

        try:
            resume = ParsedResumeProfile.model_validate(user.resume_profile.parsed_profile)
            preferences = self._serialize_preferences(user)

            from app.models.application import Application

            seen_job_ids = set(
                (await session.scalars(select(Application.job_id).where(Application.user_id == user.id))).all()
            )

            jobs = list(await session.scalars(select(Job).where(Job.is_active.is_(True)).order_by(Job.scraped_at.desc())))
            log_debug(
                logger,
                "match_rank.rank_jobs.loaded_inputs",
                user_id=user.id,
                total_jobs=len(jobs),
                already_seen_jobs=len(seen_job_ids),
                preference_locations_count=len(preferences.preferred_locations),
                preference_excluded_companies_count=len(preferences.excluded_companies),
            )

            filtered_jobs: list[Job] = []
            filter_reasons: dict[str, int] = defaultdict(int)
            for job in jobs:
                if job.id in seen_job_ids:
                    filter_reasons["already_applied"] += 1
                    continue
                allowed, reason = self._passes_filters_with_reason(job=job, preferences=preferences)
                if not allowed:
                    filter_reasons[reason] += 1
                    continue
                filtered_jobs.append(job)

            log_debug(
                logger,
                "match_rank.rank_jobs.filtered",
                user_id=user.id,
                kept_jobs=len(filtered_jobs),
                dropped_jobs=len(jobs) - len(filtered_jobs),
                filter_reasons=dict(filter_reasons),
            )

            ranked_results: list[RankedJobResult] = []
            for index, job in enumerate(filtered_jobs, start=1):
                try:
                    result = self._score_job(job=job, resume=resume, preferences=preferences)
                    ranked_results.append(result)
                    await self._upsert_job_match(session=session, user=user, result=result)
                    log_debug(
                        logger,
                        "match_rank.rank_jobs.scored_job",
                        user_id=user.id,
                        job_id=job.id,
                        ordinal=index,
                        total=len(filtered_jobs),
                        match_score=result.item.match_score,
                        recommendation=result.item.recommendation,
                    )
                except Exception as error:
                    log_exception(
                        logger,
                        "match_rank.rank_jobs.score_failed",
                        error,
                        user_id=user.id,
                        job_id=job.id,
                        job_title=job.title,
                        company_name=job.company_name,
                    )
                    raise

            await session.commit()
            ranked_results.sort(key=lambda result: result.item.match_score, reverse=True)
            log_debug(
                logger,
                "match_rank.rank_jobs.complete",
                user_id=user.id,
                ranked_count=len(ranked_results),
            )
            return ranked_results
        except Exception as error:
            log_exception(logger, "match_rank.rank_jobs.failed", error, user_id=user.id)
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

        if preferences.preferred_locations:
            normalized_locations = {location.lower() for location in preferences.preferred_locations}
            if not job.is_remote and job.location.lower() not in normalized_locations:
                return False, "location_mismatch"

        if preferences.salary_min is not None and job.salary_max is not None and job.salary_max < preferences.salary_min:
            return False, "salary_below_min"

        if preferences.salary_max is not None and job.salary_min is not None and job.salary_min > preferences.salary_max:
            return False, "salary_above_max"

        return True, "passed"

    def _score_job(
        self,
        *,
        job: Job,
        resume: ParsedResumeProfile,
        preferences: SearchPreferencesPayload,
    ) -> RankedJobResult:
        log_debug(
            logger,
            "match_rank.score_job.start",
            job_id=job.id,
            job_title=job.title,
            company_name=job.company_name,
        )
        semantic_similarity = self._cosine_similarity(resume_summary_embedding(resume), job.description_embedding)
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
        reason = self._build_reason(matched_skills=matched_skills, missing_skills=missing_skills, recommendation=recommendation)

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

    def _seniority_alignment(self, *, job: Job, resume: ParsedResumeProfile, preferences: SearchPreferencesPayload) -> float:
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
            return 1.0 if job.is_remote else 0.0

        if not preferences.preferred_locations:
            return 1.0

        if job.is_remote and "remote" in {location.lower() for location in preferences.preferred_locations}:
            return 1.0

        return 1.0 if job.location.lower() in {location.lower() for location in preferences.preferred_locations} else 0.5

    def _salary_alignment(self, *, job: Job, resume: ParsedResumeProfile, preferences: SearchPreferencesPayload) -> float:
        target_min = preferences.salary_min or resume.inferred_salary_range.min
        target_max = preferences.salary_max or resume.inferred_salary_range.max
        if job.salary_min is None or job.salary_max is None:
            return 0.6
        if job.salary_min <= target_max and job.salary_max >= target_min:
            return 1.0
        return 0.35

    async def _upsert_job_match(self, *, session: AsyncSession, user: User, result: RankedJobResult) -> None:
        log_debug(
            logger,
            "match_rank.upsert_job_match.start",
            user_id=user.id,
            job_id=result.job.id,
        )
        existing = await session.scalar(
            select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == result.job.id)
        )
        created = False
        if existing is None:
            existing = JobMatch(user_id=user.id, job_id=result.job.id)
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
            user_id=user.id,
            job_id=result.job.id,
            created=created,
            match_score=result.item.match_score,
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
        if not left or not right:
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
