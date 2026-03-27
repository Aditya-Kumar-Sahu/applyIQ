from __future__ import annotations

from app.models.job import Job
from app.schemas.resume import EducationEntry, ExperienceEntry, ParsedResumeProfile, SalaryRange, SkillGroups
from app.services.cover_letter_service import CoverLetterService


def test_cover_letter_generation_enforces_constraints_and_varies_by_tone() -> None:
    service = CoverLetterService()
    resume = ParsedResumeProfile(
        name="Pipeline User",
        email="pipeline-user@example.com",
        current_title="Senior ML Engineer",
        years_of_experience=5,
        seniority_level="senior",
        skills=SkillGroups(technical=["Python", "FastAPI", "PostgreSQL", "Docker"]),
        experience=[
            ExperienceEntry(
                company="Acme AI",
                title="Senior ML Engineer",
                duration_months=48,
                highlights=["Built an automation pipeline that reduced review time by 42 percent."],
            )
        ],
        education=[EducationEntry(degree="B.Tech", field="Computer Science", institution="ABC University", year=2020)],
        preferred_roles=["ML Engineer"],
        inferred_salary_range=SalaryRange(min=2500000, max=4000000, currency="INR"),
        work_style_signals=["remote-leaning"],
        summary_for_matching="Senior ML engineer focused on production systems.",
    )
    job = Job(
        external_id="job-1",
        source="linkedin",
        title="ML Engineer Platform 7",
        company_name="Company 7",
        company_domain="company7.example",
        location="Remote",
        is_remote=True,
        salary_min=2600000,
        salary_max=3600000,
        description_text="Company 7 is building production ML systems with Python, FastAPI, PostgreSQL, and Docker.",
        description_embedding=[0.2, 0.3, 0.4],
        apply_url="https://jobs.applyiq.dev/linkedin/7",
    )

    formal = service.generate(job=job, resume=resume, matched_skills=["Python", "FastAPI"], tone="formal", variant=1)
    conversational = service.generate(
        job=job,
        resume=resume,
        matched_skills=["Python", "FastAPI"],
        tone="conversational",
        variant=2,
    )

    assert formal.tone == "formal"
    assert conversational.tone == "conversational"
    assert formal.cover_letter != conversational.cover_letter
    assert formal.word_count <= 250
    assert conversational.word_count <= 250
    assert "Company 7" in formal.cover_letter
    assert "Company 7" in conversational.cover_letter
    assert "42" in formal.cover_letter
    assert "42" in conversational.cover_letter
    assert "I am writing to express my interest" not in formal.cover_letter
    assert "I believe I would be a great fit" not in formal.cover_letter
    assert "Please find attached" not in formal.cover_letter
