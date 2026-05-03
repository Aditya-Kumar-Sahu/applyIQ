import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.health_service import HealthService
from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.redis import RedisManager
from app.worker import celery_app

async def verify_health():
    settings = get_settings()
    db = DatabaseManager(settings.database_url.get_secret_value())
    redis = RedisManager(settings.redis_url.get_secret_value())
    
    health_service = HealthService(
        settings=settings,
        database=db,
        redis=redis,
        celery=celery_app
    )
    
    print("Running Health Report...")
    report = await health_service.get_report()
    
    import json
    print(json.dumps(report, indent=2))
    
    # Assertions
    assert "status" in report
    assert "db" in report
    assert "redis" in report
    assert "celery" in report
    assert "broker" in report["celery"]
    assert "workers" in report["celery"]
    
    print("\nVerification Successful!")

if __name__ == "__main__":
    asyncio.run(verify_health())
