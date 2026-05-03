from __future__ import annotations

import asyncio
import functools
import threading
import time
from enum import Enum
from typing import Any, Callable, TypeVar

import structlog

from app.core.logging_safety import log_debug


logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Global registry and lock for circuit breakers
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(RuntimeError):
    """Base error for circuit breaker."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when a call is attempted while the circuit is open."""
    def __init__(self, name: str, remaining_time: float):
        super().__init__(f"Circuit breaker '{name}' is open. Remaining time: {remaining_time:.1f}s")
        self.name = name
        self.remaining_time = remaining_time


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self._lock = threading.Lock()

    def _on_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

    def _on_success(self) -> None:
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def _transition_to(self, target_state: CircuitState) -> None:
        old_state = self.state
        self.state = target_state
        if target_state == CircuitState.CLOSED:
            self.failure_count = 0
        
        log_debug(
            logger, 
            "circuit_breaker.state_change", 
            name=self.name, 
            from_state=old_state.value, 
            to_state=target_state.value,
            failure_count=self.failure_count
        )

    def check(self) -> None:
        with self._lock:
            if self.state == CircuitState.OPEN:
                elapsed = time.time() - (self.last_failure_time or 0)
                if elapsed >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    raise CircuitBreakerOpenError(self.name, self.recovery_timeout - elapsed)

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        self.check()
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    async def call_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.check()
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise


def circuit_breaker(
    name: str | None = None,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    fallback: Callable[..., Any] | None = None,
) -> Callable:
    """Decorator to wrap a function with a circuit breaker."""

    def decorator(func: Callable) -> Callable:
        breaker_name = name or func.__name__
        
        with _breakers_lock:
            if breaker_name not in _breakers:
                _breakers[breaker_name] = CircuitBreaker(
                    breaker_name, 
                    failure_threshold=failure_threshold, 
                    recovery_timeout=recovery_timeout
                )
            breaker = _breakers[breaker_name]

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await breaker.call_async(func, *args, **kwargs)
                except Exception:
                    if fallback:
                        if asyncio.iscoroutinefunction(fallback):
                            return await fallback(*args, **kwargs)
                        return fallback(*args, **kwargs)
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return breaker.call(func, *args, **kwargs)
                except Exception:
                    if fallback:
                        return fallback(*args, **kwargs)
                    raise
            return sync_wrapper

    return decorator
