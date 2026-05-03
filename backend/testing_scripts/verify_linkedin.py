import asyncio
from datetime import UTC, datetime

from app.core.config import get_settings
from app.scrapers.apify_linkedin import ApifyLinkedInScraper, _parse_posted_at
from app.scrapers.base import ScrapeQuery


async def main():
    print("=== Testing Apify LinkedIn Scraper ===")
    settings = get_settings()
    scraper = ApifyLinkedInScraper(settings)
    query = ScrapeQuery(target_role="Software Engineer", location="Remote", limit_per_source=5)
    
    # 1. Test Date Parsing
    print("1. Testing Date Parsing function _parse_posted_at()")
    test_dates = [
        "2024-03-15T12:00:00Z",
        "2024-03-15T12:00:00.000Z", 
        "invalid-date-string",
        None
    ]
    for d in test_dates:
        parsed = _parse_posted_at(d)
        is_fallback = False
        if d in ("invalid-date-string", None):
            # Check if it recently got created as UTC now
            now = datetime.now(UTC)
            if abs((now - parsed).total_seconds()) < 60:
                is_fallback = True
        print(f"  Input: {d!r:25} -> Output: {parsed.isoformat()} (Silent fallback: {is_fallback})")
        
    # 2. Test Real API Response & Normalization
    print("\n2. Testing Real Data Fetch and Normalization (Requires apify_api_token)")
    if not scraper._settings.apify_api_token:
        print("  [SKIPPED] No apify_api_token in settings")
        return
        
    try:
        jobs = await scraper.fetch_jobs(query)
        print(f"  Fetched {len(jobs)} jobs")
        
        for i, j in enumerate(jobs):
            # Check for fallbacks
            warnings = []
            if j.title == "Unknown Role": warnings.append("Missing Title")
            if j.company_name == "Unknown Company": warnings.append("Missing Company")
            if j.location == "Remote" and query.location != "Remote": warnings.append("Missing Location")
            
            print(f"  Job {i+1}: {j.title[:30]} at {j.company_name[:20]}")
            if warnings:
                print(f"    [WARNING] Fallbacks used: {', '.join(warnings)}")
                
    except Exception as e:
        print(f"  [ERROR] fetch_jobs failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
