import asyncio
import os
import sys
from datetime import UTC, datetime

# Add parent directory to sys.path to import app modules
# Script location: backend/testing_scripts/seed_e2e_data.py
# Root for imports: backend/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.redis import init_redis
from app.core.security import get_password_hash
from app.models import (
    AgentRun,
    Application,
    CredentialVault,
    EmailMonitor,
    Job,
    JobMatch,
    LLMUsageLog,
    PipelineRun,
    RefreshTokenSession,
    ResumeProfile,
    SearchPreference,
    User,
)


async def seed_data():
    settings = get_settings()
    db_manager = DatabaseManager(settings.database_url.get_secret_value())

    # Initialize and flush Redis
    print("Flushing Redis cache...")
    redis_manager = init_redis(settings.redis_url.get_secret_value())
    await redis_manager.client.flushall()
    await redis_manager.close()

    print(f"Connecting to database at: {settings.database_url.get_secret_value().split('@')[-1]}")

    async with db_manager.session() as session:
        # Clear tables in reverse dependency order
        print("Clearing existing data...")
        await session.execute(delete(JobMatch))
        await session.execute(delete(Application))
        await session.execute(delete(ResumeProfile))
        await session.execute(delete(CredentialVault))
        await session.execute(delete(EmailMonitor))
        await session.execute(delete(PipelineRun))
        await session.execute(delete(AgentRun))
        await session.execute(delete(RefreshTokenSession))
        await session.execute(delete(SearchPreference))
        await session.execute(delete(LLMUsageLog))
        await session.execute(delete(Job))
        await session.execute(delete(User))

        print("Creating test user...")
        # Create test user: test@example.com / Password123!
        user = User(
            email="test@example.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="E2E Test User",
            is_active=True,
            subscription_tier="pro",
        )
        session.add(user)
        await session.flush()  # Get user.id

        print(f"User created with ID: {user.id}")

        print("Creating mock resume profile...")
        # Create mock resume profile
        resume = ResumeProfile(
            user_id=user.id,
            raw_text="Experienced Software Engineer with background in Python and Vue.js. Worked on building scalable microservices and responsive frontends.",
            parsed_profile={
                "name": "E2E Test User",
                "email": "test@example.com",
                "current_title": "Senior Software Engineer",
                "years_of_experience": 5,
                "seniority_level": "senior",
                "skills": {
                    "technical": ["Python", "SQL", "FastAPI", "Docker"],
                    "soft": ["Communication", "Leadership"],
                    "tools": ["Git", "GitHub Actions"],
                    "languages": ["English"],
                },
                "experience": [
                    {
                        "title": "Senior Software Engineer",
                        "company": "Tech Innovations Inc",
                        "duration_months": 36,
                        "highlights": [
                            "Led development of core API services.",
                            "Optimized database queries for 50% speedup.",
                        ],
                    }
                ],
                "education": [
                    {
                        "degree": "B.S. Computer Science",
                        "field": "Computer Science",
                        "institution": "State University",
                        "year": 2018,
                    }
                ],
                "preferred_roles": ["Senior Backend Engineer", "Full Stack Developer"],
                "inferred_salary_range": {"min": 120000, "max": 160000, "currency": "USD"},
                "work_style_signals": ["remote", "startup"],
                "summary_for_matching": "Experienced backend engineer specialized in Python/FastAPI with a strong interest in scalable architectures.",
            },
            resume_embedding=[0.1] * 3072,
            file_hash="mock-e2e-resume-hash-12345",
        )
        session.add(resume)

        print("Creating mock jobs...")
        # Create mock jobs
        job1 = Job(
            external_id="e2e-job-1",
            source="linkedin",
            title="Senior Python Backend Engineer",
            company_name="FastScale Systems",
            location="Remote",
            is_remote=True,
            description_text="We need an expert Python developer with FastAPI experience to build our core platform. Must be proficient in SQL, Docker, and Git.",
            description_embedding=[0.11] * 3072,
            apply_url="https://example.com/jobs/1",
            posted_at=datetime.now(UTC),
        )
        job2 = Job(
            external_id="e2e-job-2",
            source="indeed",
            title="Full Stack Developer (Vue + Python)",
            company_name="Modern Web Solutions",
            location="New York, NY",
            is_remote=False,
            description_text="Join us to build the next generation of web applications using Vue.js and Python. Experience with SQL and Git is required.",
            description_embedding=[0.22] * 3072,
            apply_url="https://example.com/jobs/2",
            posted_at=datetime.now(UTC),
        )
        session.add_all([job1, job2])
        await session.flush()  # Get job IDs

        print("Creating mock job matches...")
        # Create mock job matches
        match1 = JobMatch(
            user_id=user.id,
            job_id=job1.id,
            match_score=0.92,
            score_breakdown={
                "skills": 0.95,
                "experience": 0.88,
                "semantic_similarity": 0.94,
                "location_match": 1.0,
                "seniority_alignment": 0.9,
                "salary_alignment": 0.85,
            },
            matched_skills=["Python", "FastAPI", "Docker"],
            missing_skills=[],
            recommendation="strong_match",
            one_line_reason="Your deep expertise in Python and FastAPI perfectly matches the core requirements.",
        )
        match2 = JobMatch(
            user_id=user.id,
            job_id=job2.id,
            match_score=0.84,
            score_breakdown={
                "skills": 0.82,
                "experience": 0.86,
                "semantic_similarity": 0.85,
                "location_match": 0.8,
                "seniority_alignment": 0.9,
                "salary_alignment": 0.75,
            },
            matched_skills=["Python", "Vue.js"],
            missing_skills=["TypeScript"],
            recommendation="good_match",
            one_line_reason="Your full-stack background with Vue and Python is a great fit for this team.",
        )
        session.add_all([match1, match2])

        print("Creating mock pipeline run...")
        pipeline_run = PipelineRun(
            user_id=user.id,
            status="complete",
            current_node="complete",
            jobs_found=10,
            jobs_matched=5,
            applications_submitted=0,
            completed_at=datetime.now(UTC),
        )
        session.add(pipeline_run)

        await session.commit()
        print("E2E data seeded successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(seed_data())
    except Exception as e:
        print(f"Error seeding data: {e}")
        sys.exit(1)
