from __future__ import annotations

from hashlib import sha256
from typing import Any


_REDACTED = "[REDACTED]"
_SENSITIVE_KEYWORDS = {
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "credential",
    "resume",
    "cover_letter",
    "raw_text",
    "encrypted",
    "decrypted",
    "api_key",
}


def _is_sensitive_key(value: str) -> bool:
    lowered = value.lower()
    return any(keyword in lowered for keyword in _SENSITIVE_KEYWORDS)


def _truncate_text(value: str, *, max_length: int = 300) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}...<truncated:{len(value)}>"


def text_snapshot(value: str) -> dict[str, Any]:
    return {
        "length": len(value),
        "sha256": sha256(value.encode("utf-8")).hexdigest()[:16],
        "preview": _truncate_text(value, max_length=80),
    }


def bytes_snapshot(value: bytes) -> dict[str, Any]:
    return {
        "size": len(value),
        "sha256": sha256(value).hexdigest()[:16],
    }


def sanitize_for_logging(value: Any, *, max_items: int = 20, max_depth: int = 5, _depth: int = 0) -> Any:
    if _depth >= max_depth:
        return "<max_depth_reached>"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        return _truncate_text(value)

    if isinstance(value, bytes):
        return bytes_snapshot(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                sanitized["_truncated_items"] = len(value) - max_items
                break
            key_str = str(key)
            if _is_sensitive_key(key_str):
                sanitized[key_str] = _REDACTED
            else:
                sanitized[key_str] = sanitize_for_logging(
                    item,
                    max_items=max_items,
                    max_depth=max_depth,
                    _depth=_depth + 1,
                )
        return sanitized

    if isinstance(value, (list, tuple, set)):
        values = list(value)
        sanitized_list = [
            sanitize_for_logging(item, max_items=max_items, max_depth=max_depth, _depth=_depth + 1)
            for item in values[:max_items]
        ]
        if len(values) > max_items:
            sanitized_list.append(f"<truncated_items:{len(values) - max_items}>")
        return sanitized_list

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return sanitize_for_logging(model_dump(), max_items=max_items, max_depth=max_depth, _depth=_depth + 1)
        except Exception:
            return f"<{value.__class__.__name__}>"

    return _truncate_text(str(value))


def log_debug(logger: Any, event: str, **context: Any) -> None:
    logger.debug(event, **sanitize_for_logging(context))


def log_exception(logger: Any, event: str, error: Exception, **context: Any) -> None:
    payload = sanitize_for_logging(context)
    logger.exception(
        event,
        error_type=error.__class__.__name__,
        error_message=_truncate_text(str(error), max_length=200),
        context=payload,
    )
