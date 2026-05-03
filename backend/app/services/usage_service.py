from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    GEMINI_2_FLASH_INPUT_PRICE_PER_1M,
    GEMINI_2_FLASH_OUTPUT_PRICE_PER_1M,
)
from app.core.observability import LLM_TOKEN_USAGE_TOTAL
from app.models.llm_usage_log import LLMUsageLog
from app.schemas.llm import GeminiResponse

logger = structlog.get_logger(__name__)


class UsageTrackingService:
    @staticmethod
    async def log_llm_usage(
        *,
        session: AsyncSession,
        response: GeminiResponse,
        user_id: str | None = None,
    ) -> None:
        """
        Logs LLM token usage to Prometheus and the Database.
        """
        # 1. Update Prometheus Metrics
        LLM_TOKEN_USAGE_TOTAL.labels(
            model=response.model, 
            type="prompt"
        ).inc(response.usage.prompt_tokens)
        
        LLM_TOKEN_USAGE_TOTAL.labels(
            model=response.model, 
            type="completion"
        ).inc(response.usage.completion_tokens)

        # 2. Calculate Estimated Cost
        estimated_cost = UsageTrackingService._calculate_cost(
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )

        # 3. Persist to Database
        try:
            log_entry = LLMUsageLog(
                request_id=response.request_id,
                user_id=user_id,
                model_name=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                estimated_cost_usd=estimated_cost,
            )
            session.add(log_entry)
            await session.commit()
            
            structlog.get_logger(__name__).debug(
                "usage_tracker.log_success",
                model=response.model,
                total_tokens=response.usage.total_tokens,
                cost_usd=estimated_cost,
                user_id=user_id
            )
        except Exception as e:
            structlog.get_logger(__name__).error("usage_tracker.log_failed", error=str(e))
            await session.rollback()

    @staticmethod
    def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        # Default to Gemini 2.0 Flash pricing
        # In a multi-model system, this would be a lookup table
        input_price = GEMINI_2_FLASH_INPUT_PRICE_PER_1M / 1_000_000
        output_price = GEMINI_2_FLASH_OUTPUT_PRICE_PER_1M / 1_000_000
        
        return (prompt_tokens * input_price) + (completion_tokens * output_price)
