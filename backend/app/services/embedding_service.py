from __future__ import annotations

import hashlib
import math
import re

import structlog

from app.core.logging_safety import log_debug, log_exception


logger = structlog.get_logger(__name__)


class EmbeddingService:
    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions
        log_debug(logger, "embedding.init", dimensions=dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        try:
            vector = [0.0] * self._dimensions
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            log_debug(
                logger,
                "embedding.embed_text.start",
                dimensions=self._dimensions,
                input_length=len(text),
                token_count=len(tokens),
            )

            if not tokens:
                log_debug(logger, "embedding.embed_text.empty_tokens", dimensions=self._dimensions)
                return vector

            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                for index in range(0, min(len(digest), self._dimensions)):
                    vector[index] += digest[index] / 255.0

            magnitude = math.sqrt(sum(component * component for component in vector)) or 1.0
            result = [round(component / magnitude, 6) for component in vector]
            log_debug(logger, "embedding.embed_text.complete", dimensions=self._dimensions, output_length=len(result))
            return result
        except Exception as error:
            log_exception(
                logger,
                "embedding.embed_text.failed",
                error,
                dimensions=self._dimensions,
                input_length=len(text),
            )
            raise
