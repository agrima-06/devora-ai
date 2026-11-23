"""Unit tests for Model Gateway Circuit Breaker Engine (Phase 9 Stage 9.5)."""
import asyncio
import time
import pytest

from app.agents.gateway.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitState
from app.agents.gateway.exceptions import (
    CircuitOpenError,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderServerError,
    ProviderTimeoutError,
    classify_provider_exception,
    scrub_credentials,
)


@pytest.fixture
def clean_registry():
    CircuitBreakerRegistry.reset_instance()
    yield CircuitBreakerRegistry.get_instance()
    CircuitBreakerRegistry.reset_instance()


@pytest.mark.asyncio
async def test_circuit_breaker_initial_state():
    breaker = CircuitBreaker("mock", "gemini-1.5-pro", failure_threshold=3, open_duration_seconds=1.0)
    assert breaker.state == CircuitState.CLOSED
    allowed, cooldown = await breaker.can_execute()
    assert allowed is True
    assert cooldown is None


@pytest.mark.asyncio
async def test_circuit_breaker_trips_to_open_after_threshold():
    breaker = CircuitBreaker("mock", "gemini-1.5-pro", failure_threshold=3, open_duration_seconds=1.0)

    # 1st failure
    await breaker.record_failure(ProviderTimeoutError("Connection timed out"))
    assert breaker.state == CircuitState.CLOSED

    # 2nd failure
    await breaker.record_failure(ProviderServerError("500 Internal Server Error"))
    assert breaker.state == CircuitState.CLOSED

    # 3rd failure reaches threshold
    await breaker.record_failure(ProviderServerError("503 Service Unavailable"))
    assert breaker.state == CircuitState.OPEN

    # Subsequent can_execute should be rejected
    allowed, cooldown = await breaker.can_execute()
    assert allowed is False
    assert cooldown is not None
    assert cooldown > 0.0


@pytest.mark.asyncio
async def test_circuit_breaker_transitions_to_half_open_after_cooldown():
    breaker = CircuitBreaker(
        "mock",
        "gemini-1.5-pro",
        failure_threshold=2,
        open_duration_seconds=0.1,  # Short cooldown for testing
        success_threshold=2,
    )

    await breaker.record_failure(ProviderTimeoutError("Timeout 1"))
    await breaker.record_failure(ProviderTimeoutError("Timeout 2"))
    assert breaker.state == CircuitState.OPEN

    # Wait for cooldown to expire
    await asyncio.sleep(0.15)

    # First probe call should transition to HALF_OPEN and be allowed
    allowed, cooldown = await breaker.can_execute()
    assert allowed is True
    assert cooldown is None
    assert breaker.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_closes_after_success_threshold_in_half_open():
    breaker = CircuitBreaker(
        "mock",
        "gemini-1.5-pro",
        failure_threshold=2,
        open_duration_seconds=0.1,
        success_threshold=2,
    )

    await breaker.record_failure(ProviderTimeoutError("Err 1"))
    await breaker.record_failure(ProviderTimeoutError("Err 2"))
    assert breaker.state == CircuitState.OPEN

    await asyncio.sleep(0.15)
    allowed, _ = await breaker.can_execute()
    assert allowed is True
    assert breaker.state == CircuitState.HALF_OPEN

    # 1st probe success
    await breaker.record_success(latency_ms=120.0)
    assert breaker.state == CircuitState.HALF_OPEN

    # 2nd probe success closes the circuit
    await breaker.record_success(latency_ms=110.0)
    assert breaker.state == CircuitState.CLOSED
    assert breaker._consecutive_failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_reopens_on_failure_in_half_open():
    breaker = CircuitBreaker(
        "mock",
        "gemini-1.5-pro",
        failure_threshold=2,
        open_duration_seconds=0.1,
        success_threshold=2,
    )

    await breaker.record_failure(ProviderTimeoutError("Err 1"))
    await breaker.record_failure(ProviderTimeoutError("Err 2"))
    assert breaker.state == CircuitState.OPEN

    await asyncio.sleep(0.15)
    allowed, _ = await breaker.can_execute()
    assert breaker.state == CircuitState.HALF_OPEN

    # Probe fails -> immediately reverts to OPEN
    await breaker.record_failure(ProviderServerError("Probe failed"))
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_sliding_window_clears_aged_failures():
    breaker = CircuitBreaker(
        "mock",
        "gemini-1.5-pro",
        failure_threshold=3,
        failure_window_seconds=0.2,  # 200ms failure window
    )

    await breaker.record_failure(ProviderTimeoutError("Err 1"))
    await breaker.record_failure(ProviderTimeoutError("Err 2"))
    assert len(breaker._failures) == 2

    # Wait for window to slide past
    await asyncio.sleep(0.25)

    # 3rd failure occurs outside previous window -> should not trip breaker
    await breaker.record_failure(ProviderTimeoutError("Err 3"))
    assert breaker.state == CircuitState.CLOSED
    assert len(breaker._failures) == 1


def test_registry_singleton_and_isolation(clean_registry):
    reg = clean_registry
    b1 = reg.get_breaker("gemini", "gemini-1.5-pro")
    b2 = reg.get_breaker("gemini", "gemini-1.5-pro")
    b3 = reg.get_breaker("gemini", "gemini-1.5-flash")

    assert b1 is b2
    assert b1 is not b3
    assert len(reg.list_breakers()) == 2


from tests.fixtures.synthetic_credentials import get_synthetic_google_api_key, get_synthetic_bearer_token


def test_credential_scrubbing():
    dirty_text = f"Failed call with key {get_synthetic_google_api_key()} and bearer {get_synthetic_bearer_token()}"
    clean_text = scrub_credentials(dirty_text)
    assert "AIza" not in clean_text
    assert "[REDACTED]" in clean_text


def test_exception_classification():
    assert classify_provider_exception(TimeoutError("Read timed out")).classification == "PROVIDER_TIMEOUT"
    assert classify_provider_exception(Exception("429 Too Many Requests: resource exhausted")).classification == "PROVIDER_RATE_LIMITED"
    assert classify_provider_exception(Exception("503 Service Unavailable")).classification == "PROVIDER_OVERLOADED"
    assert classify_provider_exception(Exception("500 Internal Server Error")).classification == "PROVIDER_SERVER_ERROR"
    assert classify_provider_exception(Exception(f"Invalid API key provided: {'AIza' + 'SyTest'}")).classification == "PROVIDER_AUTHENTICATION_ERROR"
