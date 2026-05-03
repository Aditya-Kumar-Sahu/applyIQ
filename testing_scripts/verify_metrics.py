import httpx
import asyncio

async def verify_metrics():
    headers = {"X-Metrics-Secret": "applyiq-metrics-secret"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Test with correct secret
        resp = await client.get("http://localhost:8000/metrics", headers=headers)
        print(f"Status with secret: {resp.status_code}")
        if resp.status_code == 200:
            print("Successfully retrieved metrics!")
            # Check for custom metrics
            content = resp.text
            if "scraper_requests_total" in content:
                print("Found scraper_requests_total metric!")
            else:
                print("Note: scraper_requests_total not yet initialized (normal if no scraper ran).")
        
        # 2. Test without secret
        resp_no_secret = await client.get("http://localhost:8000/metrics")
        print(f"Status without secret: {resp_no_secret.status_code}")
        
        # 3. Test with wrong secret
        resp_wrong_secret = await client.get("http://localhost:8000/metrics", headers={"X-Metrics-Secret": "wrong"})
        print(f"Status with wrong secret: {resp_wrong_secret.status_code}")

if __name__ == "__main__":
    asyncio.run(verify_metrics())
