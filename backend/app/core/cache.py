from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import json
import typing
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from app.core.observability import CACHE_HIT_MISS_TOTAL
from app.core.redis import get_redis_manager

logger = structlog.get_logger(__name__)

T = TypeVar("T")

CACHE_VERSION = "v1"

class SafeFormatter(dict):
    """Formatter that returns the key itself if missing to prevent KeyError."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def _generate_key(
    func: Callable,
    call_args: dict[str, Any],
    namespace: str | None = None,
    version: str = CACHE_VERSION,
) -> str:
    """
    Generate a stable, hashed cache key.
    - MD5 hash of arguments
    - 'id' field priority for objects
    - Class name awareness for methods
    - Versioning support
    - Parameterized namespace support
    """
    # 1. Class name awareness
    class_name = None
    if "self" in call_args:
        class_name = call_args["self"].__class__.__name__
    elif "cls" in call_args:
        class_name = call_args["cls"].__name__
    
    func_identity = f"{class_name}.{func.__name__}" if class_name else func.__name__

    # 2. Extract stable identifiers, skipping infrastructure objects
    skip_keys = {"self", "cls", "session", "db"}
    
    def _extract_id(obj: Any) -> Any:
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        if hasattr(obj, "id"):
            # Prioritize .id field for database models
            return f"{obj.__class__.__name__}:{obj.id}"
        if isinstance(obj, (list, tuple)):
            return [_extract_id(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _extract_id(v) for k, v in obj.items()}
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return str(obj)

    filtered_args = {
        k: _extract_id(v) 
        for k, v in call_args.items() 
        if k not in skip_keys
    }

    # 3. MD5 hash of arguments
    try:
        arg_str = json.dumps(filtered_args, sort_keys=True)
    except (TypeError, ValueError):
        arg_str = str(filtered_args)
    
    arg_hash = hashlib.md5(arg_str.encode()).hexdigest()

    # 4. Namespace formatting
    formatted_ns = ""
    if namespace:
        # Create a context for formatting where objects are replaced by their IDs
        format_context = {k: _extract_id(v) for k, v in call_args.items()}
        # Fail-open formatting for namespaces
        try:
            resolved_ns = namespace.format_map(SafeFormatter(**format_context))
        except Exception:
            resolved_ns = namespace
        formatted_ns = f"{resolved_ns}:"

    return f"applyiq:cache:{version}:{formatted_ns}{func_identity}:{arg_hash}"


def _serialize(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, list):
        return [_serialize(item) for item in data]
    if isinstance(data, dict):
        return {k: _serialize(v) for k, v in data.items()}
    return data


def _deserialize(data: Any, return_type: Any) -> Any:
    if data is None:
        return None

    # Handle Pydantic models
    if return_type and hasattr(return_type, "model_validate"):
        return return_type.model_validate(data)

    # Handle list of Pydantic models
    origin = typing.get_origin(return_type)
    if origin is list or origin is list:
        args = typing.get_args(return_type)
        if args and hasattr(args[0], "model_validate"):
            return [args[0].model_validate(item) for item in data]

    return data


def cached(
    ttl: int = 3600,
    namespace: str | None = None,
    version: str = CACHE_VERSION,
) -> Callable:
    """
    Decorator to cache function results in Redis.
    Supports both sync and async functions.
    - MD5-based stable keys
    - Parameterized namespaces
    - Fail-open philosophy
    - Metrics instrumentation
    """

    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        return_type = typing.get_type_hints(func).get("return")
        sig = inspect.signature(func)

        def _get_call_args(*args: Any, **kwargs: Any) -> dict[str, Any]:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return bound.arguments

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                call_args = _get_call_args(*args, **kwargs)
                key = _generate_key(func, call_args, namespace, version)
                
                # Use the original namespace string for metrics to avoid high cardinality
                metric_ns = namespace.split(":")[0] if namespace else "default"

                try:
                    redis = get_redis_manager()
                    cached_val = await redis.get_value(key)
                    
                    if cached_val is not None:
                        CACHE_HIT_MISS_TOTAL.labels(namespace=metric_ns, result="hit").inc()
                        return _deserialize(cached_val, return_type)

                    CACHE_HIT_MISS_TOTAL.labels(namespace=metric_ns, result="miss").inc()
                    result = await func(*args, **kwargs)
                    
                    if result is not None:
                        await redis.set_value(key, _serialize(result), ttl=ttl)
                    return result
                except Exception as e:
                    # Fail open: if Redis fails, just call the function
                    logger.warning("cache.async_wrapper.failed", error=str(e), func=func_name, key=key)
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                call_args = _get_call_args(*args, **kwargs)
                key = _generate_key(func, call_args, namespace, version)
                metric_ns = namespace.split(":")[0] if namespace else "default"

                try:
                    redis = get_redis_manager()
                    cached_val = redis.get_value_sync(key)
                    
                    if cached_val is not None:
                        CACHE_HIT_MISS_TOTAL.labels(namespace=metric_ns, result="hit").inc()
                        return _deserialize(cached_val, return_type)

                    CACHE_HIT_MISS_TOTAL.labels(namespace=metric_ns, result="miss").inc()
                    result = func(*args, **kwargs)
                    
                    if result is not None:
                        redis.set_value_sync(key, _serialize(result), ttl=ttl)
                    return result
                except Exception as e:
                    # Fail open
                    logger.warning("cache.sync_wrapper.failed", error=str(e), func=func_name, key=key)
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator
