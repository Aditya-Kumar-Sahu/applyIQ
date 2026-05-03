import asyncio
from datetime import UTC, datetime

from app.core.config import get_settings
from app.scrapers.base import ScrapeQuery
from app.scrapers.search_api import SerpApiGoogleJobsScraper, _parse_posted_at


async def main():
    print("=== Testing SerpAPI Google Jobs Scraper ===")
    settings = get_settings()
    scraper = SerpApiGoogleJobsScraper(settings)
    scraper.source_name = "google_jobs_test"
    query = ScrapeQuery(target_role="Software Developer", location="New York", limit_per_source=5)

    # 1. Test Date Parsing
    print("1. Testing Date Parsing function _parse_posted_at()")
    test_dates = ["2 days ago", "about 10 hours ago", "invalid-date-string", None]
    for d in test_dates:
        parsed = _parse_posted_at(d)
        is_fallback = False
        if d in ("invalid-date-string", None):
            now = datetime.now(UTC)
            if abs((now - parsed).total_seconds()) < 60:
                is_fallback = True
        print(f"  Input: {d!r:25} -> Output: {parsed.isoformat()} (Silent fallback: {is_fallback})")

    # 2. Test Real API Response & Normalization
    print("\n2. Testing Real Data Fetch and Normalization (Requires serpapi_api_key)")
    if not scraper._settings.serpapi_api_key:
        print("  [SKIPPED] No serpapi_api_key in settings")
        return

    try:
        jobs = await scraper.fetch_jobs(query)
        print(f"  Fetched {len(jobs)} jobs")

        for i, j in enumerate(jobs):
            # Check for fallbacks
            warnings = []
            if j.title == "Unknown Role":
                warnings.append("Missing Title")
            if j.company_name == "Unknown Company":
                warnings.append("Missing Company")
            if not j.apply_url:
                warnings.append("Missing URL from apply_options")

            print(f"  Job {i + 1}: {j.title[:30]} at {j.company_name[:20]}")
            if warnings:
                print(f"    [WARNING] Fallbacks used: {', '.join(warnings)}")

    except Exception as e:
        print(f"  [ERROR] fetch_jobs failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
