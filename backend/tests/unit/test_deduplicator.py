from __future__ import annotations

from app.schemas.jobs import RawJob
from app.scrapers.deduplicator import JobDeduplicator


def test_deduplicator_removes_exact_url_and_fuzzy_title_duplicates() -> None:
    deduplicator = JobDeduplicator()
    jobs = [
        RawJob(
            external_id="linkedin-1",
            source="linkedin",
            title="Senior ML Engineer",
            company_name="Acme AI",
            company_domain="acme.ai",
            location="Remote",
            is_remote=True,
            salary_min=2500000,
            salary_max=4000000,
            description_text="Build ML systems with Python and FastAPI.",
            apply_url="https://jobs.acme.ai/ml-engineer",
            posted_at="2026-03-20T10:00:00Z",
        ),
        RawJob(
            external_id="indeed-1",
            source="indeed",
            title="Senior ML Engineer",
            company_name="Acme AI",
            company_domain="acme.ai",
            location="Remote",
            is_remote=True,
            salary_min=2600000,
            salary_max=4100000,
            description_text="Duplicate by exact apply URL.",
            apply_url="https://jobs.acme.ai/ml-engineer",
            posted_at="2026-03-20T10:05:00Z",
        ),
        RawJob(
            external_id="remotive-1",
            source="remotive",
            title="Machine Learning Engineer",
            company_name="Northstar Labs",
            company_domain="northstar.dev",
            location="Remote",
            is_remote=True,
            salary_min=None,
            salary_max=None,
            description_text="Same company and nearly identical title.",
            apply_url="https://northstar.dev/jobs/ml-engineer-1",
            posted_at="2026-03-20T11:00:00Z",
        ),
        RawJob(
            external_id="wellfound-1",
            source="wellfound",
            title="Machine Learning Enginer",
            company_name="Northstar Labs",
            company_domain="northstar.dev",
            location="Remote",
            is_remote=True,
            salary_min=None,
            salary_max=None,
            description_text="Duplicate by fuzzy title matching.",
            apply_url="https://northstar.dev/jobs/ml-engineer-2",
            posted_at="2026-03-20T11:10:00Z",
        ),
        RawJob(
            external_id="serpapi-1",
            source="other",
            title="AI Platform Engineer",
            company_name="Orbit Systems",
            company_domain="orbit.systems",
            location="Bengaluru",
            is_remote=False,
            salary_min=2200000,
            salary_max=3200000,
            description_text="A distinct role that should remain.",
            apply_url="https://orbit.systems/jobs/platform-engineer",
            posted_at="2026-03-20T12:00:00Z",
        ),
    ]

    deduplicated = deduplicator.deduplicate(jobs)

    assert len(deduplicated) == 3
    assert [job.external_id for job in deduplicated] == ["linkedin-1", "remotive-1", "serpapi-1"]
