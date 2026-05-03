import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import select
from app.core.database import DatabaseManager
from app.core.config import get_settings
from app.models.llm_usage_log import LLMUsageLog
from app.services.usage_service import UsageTrackingService
from app.schemas.llm import GeminiResponse, UsageMetadata

async def verify_usage_tracking():
    settings = get_settings()
    db_manager = DatabaseManager(settings.database_url.get_secret_value())
    
    async with db_manager.session() as session:
        print("1. Testing UsageTrackingService.log_llm_usage...")
        
        mock_response = GeminiResponse(
            data={"test": "data"},
            usage=UsageMetadata(
                prompt_tokens=1000,
                completion_tokens=500,
                total_tokens=1500
            ),
            model="gemini-2.0-flash",
            request_id="test-request-id"
        )
        
        await UsageTrackingService.log_llm_usage(
            session=session,
            response=mock_response,
            user_id="test-user-id"
        )
        
        # Verify in DB
        stmt = select(LLMUsageLog).where(LLMUsageLog.request_id == "test-request-id")
        log = (await session.execute(stmt)).scalar_one_or_none()
        
        if log:
            print(f"Log found in DB!")
            print(f"- Model: {log.model_name}")
            print(f"- Tokens: {log.total_tokens}")
            print(f"- Cost: ${log.estimated_cost_usd:.6f}")
            
            # Verify cost calculation: (1000 * 0.10 / 1M) + (500 * 0.40 / 1M)
            # = (0.00010) + (0.00020) = 0.00030
            expected_cost = 0.00030
            assert abs(log.estimated_cost_usd - expected_cost) < 1e-9
            print("Cost calculation verified!")
        else:
            print("Error: Log not found in DB.")
            return

        print("\nVerification Successful!")

if __name__ == "__main__":
    asyncio.run(verify_usage_tracking())
