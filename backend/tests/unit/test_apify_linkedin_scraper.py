from __future__ import annotations

from app.scrapers.apify_linkedin import ApifyLinkedInScraper
from app.scrapers.base import ScrapeQuery


def test_apify_linkedin_scraper_builds_live_actor_payload() -> None:
    scraper = ApifyLinkedInScraper()

    payload = scraper._build_input_data(ScrapeQuery(target_role="ML Engineer", location="Remote", limit_per_source=15))

    assert payload["title"] == "ML Engineer"
    assert payload["location"] == "Remote"
    assert payload["rows"] == 15


def test_apify_linkedin_scraper_normalizes_current_actor_fields() -> None:
    scraper = ApifyLinkedInScraper()

    jobs = scraper._normalize(
        [
            {
                "jobId": "abc123",
                "title": "ML Engineer",
                "company": "Example AI",
                "location": "Remote",
                "url": "https://www.linkedin.com/jobs/view/abc123",
                "datePosted": "2026-04-01T12:00:00Z",
                "description": "Build ML systems.",
                "source": "linkedin",
            }
        ]
    )

    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "apify-li-abc123"
    assert job.company_name == "Example AI"
    assert job.apply_url == "https://www.linkedin.com/jobs/view/abc123"
    assert job.description_text == "Build ML systems."
    assert job.source == "linkedin"
