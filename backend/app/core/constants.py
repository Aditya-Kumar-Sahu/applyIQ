from __future__ import annotations

APP_NAME = "ApplyIQ API"
PROJECT_SLUG = "applyiq"
API_V1_PREFIX = "/api/v1"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]
HEALTHY_STATUS = "ok"
DEGRADED_STATUS = "degraded"
UP_STATUS = "up"
DOWN_STATUS = "down"
NOT_CONFIGURED_STATUS = "not_configured"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_DEFAULT_CHAT_MODEL = "gemini-2.0-flash"
GEMINI_DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_DEFAULT_EMBEDDING_DIMENSIONS = 3072

# LLM Pricing (USD per 1M tokens) - Gemini 2.0 Flash
GEMINI_2_FLASH_INPUT_PRICE_PER_1M = 0.10
GEMINI_2_FLASH_OUTPUT_PRICE_PER_1M = 0.40
