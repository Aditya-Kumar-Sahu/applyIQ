from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from app.core.constants import (
    GEMINI_BASE_URL,
    GEMINI_DEFAULT_CHAT_MODEL,
    GEMINI_DEFAULT_EMBEDDING_MODEL,
)
from app.core.logging_safety import log_debug, log_exception, text_snapshot


logger = structlog.get_logger(__name__)


class GeminiApiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        chat_model: str = GEMINI_DEFAULT_CHAT_MODEL,
        embedding_model: str = GEMINI_DEFAULT_EMBEDDING_MODEL,
        timeout_seconds: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def embed_text(self, text: str, *, model: str | None = None) -> list[float]:
        if not self.is_configured:
            raise GeminiApiError("Gemini API key is not configured")

        model_name = model or self._embedding_model
        payload = {
            "content": {"parts": [{"text": text}]},
            "taskType": "SEMANTIC_SIMILARITY",
        }
        log_debug(
            logger,
            "gemini.embed_text.start",
            model=model_name,
            input=text_snapshot(text),
        )
        response = self._post_json(path=f"/models/{model_name}:embedContent", payload=payload)
        vector = _extract_embedding_values(response)
        if not vector:
            raise GeminiApiError("Gemini embedding response did not include embedding values")
        log_debug(logger, "gemini.embed_text.complete", model=model_name, dimensions=len(vector))
        return vector

    def embed_batch(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        if len(texts) == 0:
            return []
        if not self.is_configured:
            raise GeminiApiError("Gemini API key is not configured")

        model_name = model or self._embedding_model
        requests_payload = [
            {
                "model": f"models/{model_name}",
                "content": {"parts": [{"text": text}]},
                "taskType": "SEMANTIC_SIMILARITY",
            }
            for text in texts
        ]
        payload = {"requests": requests_payload}
        log_debug(
            logger,
            "gemini.embed_batch.start",
            model=model_name,
            batch_size=len(texts),
        )

        try:
            response = self._post_json(path=f"/models/{model_name}:batchEmbedContents", payload=payload)
            embeddings_payload = response.get("embeddings", [])
            vectors = [_extract_embedding_values(item) for item in embeddings_payload]
            if len(vectors) == len(texts) and all(vectors):
                log_debug(
                    logger,
                    "gemini.embed_batch.complete",
                    model=model_name,
                    batch_size=len(texts),
                    dimensions=len(vectors[0]),
                )
                return vectors
        except GeminiApiError as error:
            log_debug(
                logger,
                "gemini.embed_batch.fallback_to_single_requests",
                model=model_name,
                reason=str(error),
            )

        return [self.embed_text(text, model=model_name) for text in texts]

    def generate_json(
        self,
        *,
        prompt: str,
        system_instruction: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise GeminiApiError("Gemini API key is not configured")

        model_name = model or self._chat_model
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "responseMimeType": "application/json",
        }
        if schema is not None:
            generation_config["responseSchema"] = schema

        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        log_debug(
            logger,
            "gemini.generate_json.start",
            model=model_name,
            prompt=text_snapshot(prompt),
        )
        response = self._post_json(path=f"/models/{model_name}:generateContent", payload=payload)
        raw_text = _extract_generated_text(response)
        if not raw_text:
            raise GeminiApiError("Gemini response did not include text output")

        parsed = _parse_json_payload(raw_text)
        log_debug(logger, "gemini.generate_json.complete", model=model_name, keys=list(parsed.keys()))
        return parsed

    def _post_json(self, *, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key:
            raise GeminiApiError("Gemini API key is not configured")

        url = f"{GEMINI_BASE_URL}{path}"
        try:
            response = self._http_client.post(
                url,
                params={"key": self._api_key},
                json=payload,
            )
        except Exception as error:
            log_exception(logger, "gemini.request.failed", error, path=path)
            raise GeminiApiError(f"Gemini request failed for {path}: {error}") from error

        if response.status_code >= 400:
            raise GeminiApiError(
                f"Gemini request failed for {path}: {response.status_code} {response.text[:200]}"
            )
        try:
            return response.json()
        except Exception as error:
            raise GeminiApiError(f"Gemini response JSON parse failed for {path}: {error}") from error


def _extract_embedding_values(payload: dict[str, Any]) -> list[float]:
    if "embedding" in payload and isinstance(payload["embedding"], dict):
        values = payload["embedding"].get("values")
        if isinstance(values, list):
            return [float(value) for value in values]
    if "embeddingValues" in payload and isinstance(payload["embeddingValues"], list):
        return [float(value) for value in payload["embeddingValues"]]
    if "values" in payload and isinstance(payload["values"], list):
        return [float(value) for value in payload["values"]]
    return []


def _extract_generated_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) == 0:
        return ""

    first_candidate = candidates[0]
    content = first_candidate.get("content", {})
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        return ""

    chunks: list[str] = []
    for part in parts:
        text = part.get("text")
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks).strip()


def _parse_json_payload(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GeminiApiError("Gemini returned non-JSON output")
    try:
        parsed = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError as error:
        raise GeminiApiError(f"Gemini JSON extraction failed: {error}") from error
    if not isinstance(parsed, dict):
        raise GeminiApiError("Gemini JSON output must be an object")
    return parsed
