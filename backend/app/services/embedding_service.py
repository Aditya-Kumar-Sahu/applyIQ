from __future__ import annotations

import hashlib
import math
import re


class EmbeddingService:
    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(0, min(len(digest), self._dimensions)):
                vector[index] += digest[index] / 255.0

        magnitude = math.sqrt(sum(component * component for component in vector)) or 1.0
        return [round(component / magnitude, 6) for component in vector]
