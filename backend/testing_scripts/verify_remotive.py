import asyncio

from app.core.config import get_settings
from app.scrapers.base import ScrapeQuery
from app.scrapers.remotive import RemotiveScraper


async def main():
    print("=== Testing Remotive Scraper ===")
    settings = get_settings()
    scraper = RemotiveScraper(settings)
    query = ScrapeQuery(target_role="Software", location="", limit_per_source=5)
    
    # 2. Test Real API Response & Normalization
    print("1. Testing Real Data Fetch and Normalization")
    try:
        jobs = await scraper.fetch_jobs(query)
        print(f"  Fetched {len(jobs)} jobs")
        
        for i, j in enumerate(jobs):
            # Check for fallbacks
            warnings = []
            if j.title == "Unknown Role": warnings.append("Missing Title")
            if j.company_name == "Unknown Company": warnings.append("Missing Company")
            if not j.apply_url: warnings.append("Missing URL")
            if j.location == "Remote": warnings.append("Defaulted Location to Remote")
            
            print(f"  Job {i+1}: {j.title[:30]} at {j.company_name[:20]}")
            if warnings:
                print(f"    [WARNING] Fallbacks used: {', '.join(warnings)}")
                
    except Exception as e:
        print(f"  [ERROR] fetch_jobs failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())