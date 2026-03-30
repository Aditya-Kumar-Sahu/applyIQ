from __future__ import annotations

import hashlib
import math
import re

import structlog

from app.core.config import Settings, get_settings
from app.core.constants import GEMINI_DEFAULT_EMBEDDING_DIMENSIONS
from app.core.logging_safety import log_debug, log_exception, text_snapshot
from app.services.gemini_client import GeminiApiError, GeminiClient


logger = structlog.get_logger(__name__)


class EmbeddingService:
    def __init__(
        self,
        *,
        dimensions: int = GEMINI_DEFAULT_EMBEDDING_DIMENSIONS,
        settings: Settings | None = None,
        gemini_client: GeminiClient | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self._dimensions = dimensions
        self._gemini_client = gemini_client or GeminiClient(
            api_key=resolved_settings.gemini_api_key,
            chat_model=resolved_settings.gemini_chat_model,
            embedding_model=resolved_settings.gemini_embedding_model,
        )
        self._gemini_embedding_model = resolved_settings.gemini_embedding_model
        log_debug(
            logger,
            "embedding.init",
            configured_gemini=self._gemini_client.is_configured,
            dimensions=dimensions,
            model=self._gemini_embedding_model,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        normalized_text = (text or "").strip()
        if normalized_text == "":
            return [0.0] * self._dimensions

        if self._gemini_client.is_configured:
            try:
                vector = self._gemini_client.embed_text(normalized_text, model=self._gemini_embedding_model)
            except Exception as error:
                log_exception(
                    logger,
                    "embedding.embed_text.gemini_failed",
                    error if isinstance(error, Exception) else RuntimeError(str(error)),
                    model=self._gemini_embedding_model,
                )
                vector = self._embed_text_deterministic(normalized_text)
                log_debug(
                    logger,
                    "embedding.embed_text.gemini_fallback",
                    model=self._gemini_embedding_model,
                    input=text_snapshot(normalized_text),
                    dimensions=len(vector),
                )
                return vector
            self._dimensions = len(vector)
            log_debug(
                logger,
                "embedding.embed_text.gemini_success",
                model=self._gemini_embedding_model,
                input=text_snapshot(normalized_text),
                dimensions=len(vector),
            )
            return vector

        vector = self._embed_text_deterministic(normalized_text)
        log_debug(
            logger,
            "embedding.embed_text.deterministic_fallback",
            input=text_snapshot(normalized_text),
            dimensions=len(vector),
        )
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if len(texts) == 0:
            return []

        normalized_texts = [(text or "").strip() for text in texts]
        if self._gemini_client.is_configured:
            try:
                vectors = self._gemini_client.embed_batch(normalized_texts, model=self._gemini_embedding_model)
            except Exception as error:
                log_exception(
                    logger,
                    "embedding.embed_batch.gemini_failed",
                    error if isinstance(error, Exception) else RuntimeError(str(error)),
                    batch_size=len(normalized_texts),
                    model=self._gemini_embedding_model,
                )
                vectors = [self._embed_text_deterministic(text) for text in normalized_texts]
                log_debug(
                    logger,
                    "embedding.embed_batch.gemini_fallback",
                    batch_size=len(vectors),
                    dimensions=self._dimensions,
                )
                return vectors
            if len(vectors) != len(normalized_texts):
                raise GeminiApiError(
                    "Gemini batch embedding response size mismatch: "
                    f"{len(vectors)} != {len(normalized_texts)}"
                )
            self._dimensions = len(vectors[0]) if vectors else self._dimensions
            log_debug(
                logger,
                "embedding.embed_batch.gemini_success",
                model=self._gemini_embedding_model,
                batch_size=len(vectors),
                dimensions=self._dimensions,
            )
            return vectors

        vectors = [self._embed_text_deterministic(text) for text in normalized_texts]
        log_debug(
            logger,
            "embedding.embed_batch.deterministic_fallback",
            batch_size=len(vectors),
            dimensions=self._dimensions,
        )
        return vectors

    def _embed_text_deterministic(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if len(tokens) == 0:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(0, min(len(digest), self._dimensions)):
                vector[index] += digest[index] / 255.0

        magnitude = math.sqrt(sum(component * component for component in vector)) or 1.0
        return [round(component / magnitude, 6) for component in vector]
