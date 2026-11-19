"""Circuit Breaker Engine for Model Gateway (Phase 9 Stage 9.5)."""
import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from app.agents.gateway.exceptions import (
    CircuitOpenError,
    classify_provider_exception,
    scrub_credentials,
)
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Manages failure tracking and state transitions for a specific (provider, model) pair."""

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        failure_threshold: Optional[int] = None,
        failure_window_seconds: Optional[float] = None,
        open_duration_seconds: Optional[float] = None,
        half_open_max_calls: Optional[int] = None,
        success_threshold: Optional[int] = None,
        on_state_change: Optional[Callable[["CircuitBreaker", CircuitState, CircuitState], Any]] = None,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.failure_threshold = failure_threshold or settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.failure_window_seconds = failure_window_seconds or settings.CIRCUIT_BREAKER_FAILURE_WINDOW_SECONDS
        self.open_duration_seconds = open_duration_seconds or settings.CIRCUIT_BREAKER_OPEN_DURATION_SECONDS
        self.half_open_max_calls = half_open_max_calls or settings.CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS
        self.success_threshold = success_threshold or settings.CIRCUIT_BREAKER_SUCCESS_THRESHOLD
        self.on_state_change = on_state_change

        self._state: CircuitState = CircuitState.CLOSED
        self._failures: Deque[float] = deque()
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_calls = 0

        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._last_state_change: float = time.time()
        self._last_failure_reason: Optional[str] = None
        self._last_failure_classification: Optional[str] = None

        self.total_calls = 0
        self.total_failures = 0
        self.total_retries = 0
        self.total_fallbacks = 0
        self._latencies: Deque[float] = deque(maxlen=50)

        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def time_until_probe(self) -> Optional[float]:
        if self._state != CircuitState.OPEN:
            return None
        elapsed = time.time() - self._last_state_change
        return max(0.0, round(self.open_duration_seconds - elapsed, 2))

    def to_status_dict(self) -> Dict[str, Any]:
        from datetime import datetime, timezone
        return {
            "key": f"{self.provider_name}:{self.model_name}",
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "state": self._state.value,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "recent_failures_in_window": len(self._failures),
            "failure_threshold": self.failure_threshold,
            "open_duration_seconds": self.open_duration_seconds,
            "time_until_probe_seconds": self.time_until_probe,
            "last_failure_reason": self._last_failure_reason,
            "last_failure_classification": self._last_failure_classification,
            "last_failure_at": datetime.fromtimestamp(self._last_failure_time, tz=timezone.utc) if self._last_failure_time else None,
            "last_success_at": datetime.fromtimestamp(self._last_success_time, tz=timezone.utc) if self._last_success_time else None,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_probes": self._half_open_calls,
        }

    async def can_execute(self) -> Tuple[bool, Optional[float]]:
        """Determine whether a call is allowed through the circuit breaker.
        Returns:
            Tuple of (is_allowed: bool, cooldown_remaining: Optional[float])
        """
        async with self._lock:
            now = time.time()

            # Clean expired failures from sliding window
            while self._failures and self._failures[0] < now - self.failure_window_seconds:
                self._failures.popleft()

            if self._state == CircuitState.CLOSED:
                return True, None

            if self._state == CircuitState.OPEN:
                elapsed = now - self._last_state_change
                if elapsed >= self.open_duration_seconds:
                    old_state = self._state
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 1
                    self._consecutive_successes = 0
                    self._last_state_change = now
                    logger.info(
                        "circuit_breaker_state_transition",
                        provider=self.provider_name,
                        model=self.model_name,
                        from_state=old_state.value,
                        to_state=self._state.value,
                    )
                    if self.on_state_change:
                        try:
                            res = self.on_state_change(self, old_state, self._state)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception as e:
                            logger.warning("circuit_breaker_callback_error", error=str(e))
                    return True, None
                else:
                    remaining = self.open_duration_seconds - elapsed
                    return False, remaining

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True, None
                else:
                    return False, 0.0

            return True, None

    async def record_success(self, latency_ms: float = 0.0) -> None:
        """Record successful invocation through this provider/model."""
        async with self._lock:
            now = time.time()
            self.total_calls += 1
            self._last_success_time = now
            if latency_ms > 0:
                self._latencies.append(latency_ms)

            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.success_threshold:
                    old_state = self._state
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    self._failures.clear()
                    self._last_state_change = now
                    logger.info(
                        "circuit_breaker_state_transition",
                        provider=self.provider_name,
                        model=self.model_name,
                        from_state=old_state.value,
                        to_state=self._state.value,
                    )
                    if self.on_state_change:
                        try:
                            res = self.on_state_change(self, old_state, self._state)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception as e:
                            logger.warning("circuit_breaker_callback_error", error=str(e))

            elif self._state == CircuitState.CLOSED:
                self._consecutive_failures = 0

    async def record_failure(self, exc: Exception) -> None:
        """Record execution failure, update counters, and potentially trip circuit."""
        classified = classify_provider_exception(exc)
        clean_reason = scrub_credentials(str(exc))

        async with self._lock:
            now = time.time()
            self.total_calls += 1
            self.total_failures += 1
            self._last_failure_time = now
            self._last_failure_reason = clean_reason
            self._last_failure_classification = classified.classification

            # If the error is application-side or client validation, do not trip breaker
            if not classified.trips_circuit:
                return

            self._consecutive_failures += 1
            self._consecutive_successes = 0

            # HALF_OPEN probe failed: immediately revert to OPEN
            if self._state == CircuitState.HALF_OPEN:
                old_state = self._state
                self._state = CircuitState.OPEN
                self._last_state_change = now
                logger.warning(
                    "circuit_breaker_probe_failed_reopened",
                    provider=self.provider_name,
                    model=self.model_name,
                    error=clean_reason,
                )
                if self.on_state_change:
                    try:
                        res = self.on_state_change(self, old_state, self._state)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except Exception as e:
                        logger.warning("circuit_breaker_callback_error", error=str(e))
                return

            # CLOSED state: track in sliding window
            if self._state == CircuitState.CLOSED:
                self._failures.append(now)

                # Clean expired
                while self._failures and self._failures[0] < now - self.failure_window_seconds:
                    self._failures.popleft()

                if len(self._failures) >= self.failure_threshold:
                    old_state = self._state
                    self._state = CircuitState.OPEN
                    self._last_state_change = now
                    logger.warning(
                        "circuit_breaker_opened",
                        provider=self.provider_name,
                        model=self.model_name,
                        failure_count=len(self._failures),
                        threshold=self.failure_threshold,
                        error=clean_reason,
                    )
                    if self.on_state_change:
                        try:
                            res = self.on_state_change(self, old_state, self._state)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception as e:
                            logger.warning("circuit_breaker_callback_error", error=str(e))

    def get_metrics(self) -> Dict[str, Any]:
        """Return diagnostic metrics for this circuit breaker."""
        avg_lat = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
        health_status = "HEALTHY"
        if self._state == CircuitState.OPEN:
            health_status = "CIRCUIT_OPEN"
        elif self._state == CircuitState.HALF_OPEN:
            health_status = "RECOVERING"
        elif self._consecutive_failures > 0:
            health_status = "DEGRADED"

        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "circuit_state": self._state.value,
            "health_status": health_status,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "failures_in_window": len(self._failures),
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_retries": self.total_retries,
            "total_fallbacks": self.total_fallbacks,
            "average_latency_ms": round(avg_lat, 2),
            "last_failure_at": self._last_failure_time,
            "last_success_at": self._last_success_time,
            "last_failure_reason": self._last_failure_reason,
            "last_failure_classification": self._last_failure_classification,
            "last_state_change_at": self._last_state_change,
        }

    def reset(self) -> None:
        """Reset circuit breaker to clean closed state."""
        self._state = CircuitState.CLOSED
        self._failures.clear()
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_calls = 0
        self._last_state_change = time.time()


class CircuitBreakerRegistry:
    """Registry maintaining per-provider and per-model CircuitBreaker instances."""

    _instance: Optional["CircuitBreakerRegistry"] = None

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "CircuitBreakerRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def get_breaker(
        self,
        provider_name: str,
        model_name: str,
        on_state_change: Optional[Callable[[CircuitBreaker, CircuitState, CircuitState], Any]] = None,
    ) -> CircuitBreaker:
        key = f"{provider_name}:{model_name}"
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(
                provider_name=provider_name,
                model_name=model_name,
                on_state_change=on_state_change,
            )
        return self._breakers[key]

    def list_breakers(self) -> List[CircuitBreaker]:
        return list(self._breakers.values())

    def reset_all(self) -> None:
        for breaker in self._breakers.values():
            breaker.reset()
