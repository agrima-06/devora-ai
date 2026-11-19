"""Unit tests for Model Gateway Resilience, Retries, and Fallbacks (Phase 9 Stage 9.5)."""
import asyncio
from typing import Optional
import pytest
from pydantic import BaseModel

from app.agents.gateway.base import BaseLLMProvider
from app.agents.gateway.circuit_breaker import CircuitBreakerRegistry
from app.agents.gateway.exceptions import (
    CircuitOpenError,
    FallbackExhaustedError,
    ModelGatewayException,
    ModelProviderUnavailableError,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.agents.gateway.gateway import ModelGateway


class DummyOutput(BaseModel):
    summary: str
    score: int


class FlakyFailingProvider(BaseLLMProvider):
    """Fails N times with a transient error, then succeeds."""

    def __init__(self, fail_count: int = 2, provider_name: str = "mock", model_name: str = "flaky"):
        self.provider_name = provider_name
        self.model_name = model_name
        self.fail_count = fail_count
        self.attempts = 0

    async def generate_text(self, prompt: str, **kwargs) -> str:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise ProviderServerError(f"Simulated failure attempt {self.attempts}")
        return f"Success on attempt {self.attempts}"

    async def generate_structured(self, prompt: str, response_model, **kwargs):
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise ProviderTimeoutError(f"Simulated timeout {self.attempts}")
        return response_model(summary=f"Resolved on attempt {self.attempts}", score=100)

    async def generate_embedding(self, text: str):
        return [0.1] * 768

    def get_token_usage(self):
        return {"prompt_tokens": 10 * self.attempts, "completion_tokens": 5 * self.attempts, "total_tokens": 15 * self.attempts}


class PermanentFailureProvider(BaseLLMProvider):
    """Always fails with an error."""

    def __init__(self, exc: Exception, provider_name: str = "mock", model_name: str = "failing"):
        self.provider_name = provider_name
        self.model_name = model_name
        self.exc = exc
        self.attempts = 0

    async def generate_text(self, prompt: str, **kwargs) -> str:
        self.attempts += 1
        raise self.exc

    async def generate_structured(self, prompt: str, response_model, **kwargs):
        self.attempts += 1
        raise self.exc

    async def generate_embedding(self, text: str):
        raise self.exc

    def get_token_usage(self):
        return {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10}


class ReliableBackupProvider(BaseLLMProvider):
    """Always succeeds."""

    def __init__(self, provider_name: str = "backup", model_name: str = "backup-model"):
        self.provider_name = provider_name
        self.model_name = model_name
        self.attempts = 0

    async def generate_text(self, prompt: str, **kwargs) -> str:
        self.attempts += 1
        return "Backup provider text success"

    async def generate_structured(self, prompt: str, response_model, **kwargs):
        self.attempts += 1
        return response_model(summary="Backup structured success", score=99)

    async def generate_embedding(self, text: str):
        return [0.5] * 768

    def get_token_usage(self):
        return {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}


@pytest.fixture(autouse=True)
def reset_registry():
    CircuitBreakerRegistry.reset_instance()
    yield
    CircuitBreakerRegistry.reset_instance()


@pytest.mark.asyncio
async def test_gateway_retries_transient_failures_and_succeeds():
    # Fails twice, succeeds on 3rd attempt
    flaky = FlakyFailingProvider(fail_count=2, model_name="flaky-1")
    gateway = ModelGateway(provider=flaky)

    result = await gateway.generate_text("test prompt")
    assert "Success on attempt 3" in result
    assert flaky.attempts == 3
    assert gateway.total_retries == 2


@pytest.mark.asyncio
async def test_gateway_structured_generation_retries():
    flaky = FlakyFailingProvider(fail_count=1, model_name="flaky-struct")
    gateway = ModelGateway(provider=flaky)

    res = await gateway.generate_structured("analyze", response_model=DummyOutput)
    assert res.summary == "Resolved on attempt 2"
    assert res.score == 100
    assert gateway.total_retries == 1


@pytest.mark.asyncio
async def test_gateway_falls_back_when_primary_exhausted():
    failing_primary = PermanentFailureProvider(
        ProviderServerError("Primary service overloaded"),
        provider_name="primary_p",
        model_name="failing-primary",
    )
    backup = ReliableBackupProvider(provider_name="backup_p", model_name="backup-v1")

    gateway = ModelGateway(provider=failing_primary, fallback_providers=[backup])

    result = await gateway.generate_text("generate solution")
    assert result == "Backup provider text success"
    assert failing_primary.attempts == 3  # Tried max attempts
    assert backup.attempts == 1
    assert gateway.total_fallbacks == 1
    assert gateway.last_used_model == "backup-v1"


@pytest.mark.asyncio
async def test_gateway_non_retryable_auth_error_fails_immediately():
    auth_fail_primary = PermanentFailureProvider(
        ProviderAuthenticationError("Invalid API key [REDACTED]"),
        provider_name="auth_fail_p",
        model_name="unauthorized-model",
    )
    backup = ReliableBackupProvider()

    gateway = ModelGateway(provider=auth_fail_primary, fallback_providers=[backup])

    # Should not waste retries on 401/403, and proceed to fallback or raise
    result = await gateway.generate_text("test prompt")
    assert result == "Backup provider text success"
    assert auth_fail_primary.attempts == 1  # Exactly 1 attempt, no useless retries!


@pytest.mark.asyncio
async def test_gateway_raises_fallback_exhausted_when_all_fail():
    primary = PermanentFailureProvider(ProviderServerError("Err 1"), model_name="p1")
    backup = PermanentFailureProvider(ProviderServerError("Err 2"), model_name="b1")

    gateway = ModelGateway(provider=primary, fallback_providers=[backup])

    with pytest.raises(FallbackExhaustedError) as exc_info:
        await gateway.generate_text("test prompt")

    assert "All 2 candidate providers" in str(exc_info.value)
    assert exc_info.value.classification == "FALLBACK_EXHAUSTED"


@pytest.mark.asyncio
async def test_gateway_health_status_reporting():
    primary = ReliableBackupProvider(provider_name="gemini", model_name="gemini-1.5-pro")
    fallback = ReliableBackupProvider(provider_name="gemini", model_name="gemini-1.5-flash")

    gateway = ModelGateway(provider=primary, fallback_providers=[fallback])
    await gateway.generate_text("hello")

    health = gateway.get_health_status()
    assert health["status"] == "HEALTHY"
    assert health["active_primary_model"] == "gemini-1.5-pro"
    assert health["fallback_models"] == ["gemini-1.5-flash"]
    assert len(health["breakers"]) >= 2
    assert health["metrics"]["total_requests"] >= 1
