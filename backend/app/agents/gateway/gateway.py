"""Centralized Model Gateway: manages LLM provider lifecycle, circuit breaking, retry engine, fallback chains, and token accounting."""
import asyncio
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

from app.agents.events import WorkflowEventBroadcaster
from app.agents.gateway.base import BaseLLMProvider
from app.agents.gateway.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitState
from app.agents.gateway.exceptions import (
    CircuitOpenError,
    FallbackExhaustedError,
    ModelGatewayException,
    ModelProviderUnavailableError,
    ProviderRateLimitedError,
    classify_provider_exception,
    scrub_credentials,
)
from app.agents.gateway.gemini import GeminiProvider
from app.agents.gateway.mock import MockLLMProvider
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("model_gateway")
T = TypeVar("T", bound=BaseModel)


class ModelGateway:
    """Centralized LLM gateway.
    Enforces circuit breakers, intelligent jittered retries, capability-aware fallback, and token accounting.
    """

    _instance: Optional["ModelGateway"] = None

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        fallback_providers: Optional[List[BaseLLMProvider]] = None,
    ):
        self.circuit_registry = CircuitBreakerRegistry.get_instance()
        self.broadcaster = WorkflowEventBroadcaster.get_instance()

        if provider:
            self.primary_provider = provider
            self.fallback_providers = fallback_providers or []
        elif settings.USE_MOCK_LLM or not settings.GEMINI_API_KEY:
            logger.info("using_mock_llm_provider", reason="configured_or_no_api_key")
            self.primary_provider = MockLLMProvider()
            self.fallback_providers = [MockLLMProvider(model_name="mock-fallback")]
        else:
            logger.info("using_gemini_provider", model=settings.GEMINI_MODEL)
            self.primary_provider = GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.GEMINI_MODEL,
            )
            if settings.MODEL_FALLBACK_ENABLED and settings.MODEL_FALLBACK_MODEL:
                self.fallback_providers = [
                    GeminiProvider(
                        api_key=settings.GEMINI_API_KEY,
                        model_name=settings.MODEL_FALLBACK_MODEL,
                    )
                ]
            else:
                self.fallback_providers = []

        # Token telemetry
        self.total_tokens_used = 0
        self.prompt_tokens_used = 0
        self.completion_tokens_used = 0
        self.total_retries = 0
        self.total_fallbacks = 0

        # Runtime status
        self.last_used_provider: str = self.primary_provider.provider_name
        self.last_used_model: str = self.primary_provider.model_name
        self.last_fallback_invoked: bool = False
        self.last_fallback_reason: Optional[str] = None

    @property
    def provider(self) -> BaseLLMProvider:
        """Backwards compatibility accessor for primary provider."""
        return self.primary_provider

    @classmethod
    def get_instance(cls) -> "ModelGateway":
        """Get or initialize singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, gateway: "ModelGateway") -> None:
        """Override instance for testing."""
        cls._instance = gateway

    async def _execute_with_resilience(
        self,
        op_name: str,
        call_fn: Callable[[BaseLLMProvider], Any],
        task_id: Optional[str] = None,
    ) -> Any:
        """Execute model call through circuit breakers, intelligent retry, and fallback chain."""
        candidates = [self.primary_provider] + list(self.fallback_providers)
        last_error: Optional[Exception] = None

        for candidate_idx, candidate in enumerate(candidates):
            breaker = self.circuit_registry.get_breaker(
                provider_name=candidate.provider_name,
                model_name=candidate.model_name,
            )

            # Check if breaker allows call
            allowed, remaining = await breaker.can_execute()
            if not allowed:
                logger.warning(
                    "circuit_open_skipping_provider",
                    provider=candidate.provider_name,
                    model=candidate.model_name,
                    remaining=remaining,
                )
                last_error = CircuitOpenError(
                    provider=candidate.provider_name,
                    model=candidate.model_name,
                    cooldown_remaining_seconds=remaining or 0.0,
                )
                continue

            # If this is a fallback candidate, log & emit fallback start
            if candidate_idx > 0:
                self.last_fallback_invoked = True
                self.last_fallback_reason = str(last_error)
                logger.info(
                    "model_fallback_started",
                    from_model=self.primary_provider.model_name,
                    to_model=candidate.model_name,
                )
                if task_id:
                    asyncio.create_task(
                        self.broadcaster.emit(
                            task_id=task_id,
                            event_type="MODEL_FALLBACK_STARTED",
                            agent_name="model_gateway",
                            message=f"Failing over to fallback model '{candidate.model_name}' due to primary failure.",
                            payload={
                                "from_model": self.primary_provider.model_name,
                                "to_model": candidate.model_name,
                                "reason": scrub_credentials(str(last_error)),
                            },
                        )
                    )

            # Retry loop on candidate
            start_time = time.time()
            max_attempts = settings.MODEL_RETRY_MAX_ATTEMPTS if settings.MODEL_RETRY_ENABLED else 1

            for attempt in range(1, max_attempts + 1):
                # Check maximum elapsed retry time budget
                if (time.time() - start_time) > settings.MODEL_RETRY_MAX_ELAPSED_SECONDS:
                    logger.warning("model_retry_time_budget_exhausted", provider=candidate.provider_name, model=candidate.model_name)
                    break

                try:
                    t0 = time.time()
                    raw_res = await call_fn(candidate)
                    latency_ms = (time.time() - t0) * 1000

                    if isinstance(raw_res, tuple) and len(raw_res) == 2:
                        result, usage = raw_res
                    else:
                        result = raw_res
                        usage = getattr(candidate, "get_token_usage", lambda: {})() or {}

                    await breaker.record_success(latency_ms)
                    self._record_usage(usage)
                    self.last_used_provider = candidate.provider_name
                    self.last_used_model = candidate.model_name

                    if candidate_idx > 0:
                        self.total_fallbacks += 1
                        breaker.total_fallbacks += 1
                        if task_id:
                            asyncio.create_task(
                                self.broadcaster.emit(
                                    task_id=task_id,
                                    event_type="MODEL_FALLBACK_SUCCEEDED",
                                    agent_name="model_gateway",
                                    message=f"Fallback model '{candidate.model_name}' succeeded.",
                                    payload={"model_used": candidate.model_name},
                                )
                            )

                    return result

                except Exception as exc:
                    classified = classify_provider_exception(exc)
                    last_error = classified
                    await breaker.record_failure(exc)

                    logger.warning(
                        "model_call_failed",
                        provider=candidate.provider_name,
                        model=candidate.model_name,
                        attempt=attempt,
                        classification=classified.classification,
                        is_retryable=classified.is_retryable,
                        error=scrub_credentials(str(exc)),
                    )

                    # If not retryable or final attempt on this provider, exit retry loop
                    if not classified.is_retryable or attempt >= max_attempts:
                        break

                    # Check if circuit breaker tripped to OPEN during this failure
                    can_try_again, _ = await breaker.can_execute()
                    if not can_try_again:
                        logger.warning("circuit_tripped_during_retry", provider=candidate.provider_name, model=candidate.model_name)
                        break

                    # Calculate full jitter exponential backoff
                    if isinstance(classified, ProviderRateLimitedError) and classified.retry_after:
                        delay = min(settings.MODEL_RETRY_MAX_DELAY_SECONDS, max(1.0, classified.retry_after))
                    else:
                        max_backoff = min(
                            settings.MODEL_RETRY_MAX_DELAY_SECONDS,
                            settings.MODEL_RETRY_BASE_DELAY_SECONDS * (2 ** attempt),
                        )
                        delay = random.uniform(0.1, max_backoff)

                    self.total_retries += 1
                    breaker.total_retries += 1

                    if task_id:
                        asyncio.create_task(
                            self.broadcaster.emit(
                                task_id=task_id,
                                event_type="MODEL_RETRY_STARTED",
                                agent_name="model_gateway",
                                message=f"Retrying model call on {candidate.model_name} in {round(delay, 2)}s (attempt {attempt + 1}/{max_attempts}).",
                                payload={
                                    "provider": candidate.provider_name,
                                    "model": candidate.model_name,
                                    "attempt": attempt,
                                    "delay_seconds": round(delay, 2),
                                },
                            )
                        )

                    await asyncio.sleep(delay)

        # If all candidates exhausted
        logger.error("all_model_providers_exhausted", last_error=scrub_credentials(str(last_error)))
        if task_id:
            asyncio.create_task(
                self.broadcaster.emit(
                    task_id=task_id,
                    event_type="MODEL_PROVIDER_UNAVAILABLE",
                    agent_name="model_gateway",
                    message="All configured model providers and fallbacks failed.",
                    payload={"error": scrub_credentials(str(last_error))},
                )
            )

        if len(candidates) > 1:
            raise FallbackExhaustedError(
                f"All {len(candidates)} candidate providers and fallbacks exhausted. Last error: {scrub_credentials(str(last_error))}"
            )
        if isinstance(last_error, ModelGatewayException):
            raise last_error
        raise ModelProviderUnavailableError(
            f"All model providers and fallbacks failed. Last error: {scrub_credentials(str(last_error))}"
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> T:
        """Execute structured generation with circuit breaker, retries, fallback, and token accounting."""
        async def _call(provider: BaseLLMProvider):
            return await provider.generate_structured(
                prompt=prompt,
                response_model=response_model,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        return await self._execute_with_resilience("generate_structured", _call, task_id=task_id)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Execute text generation with circuit breaker, retries, fallback, and token accounting."""
        async def _call(provider: BaseLLMProvider):
            return await provider.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        return await self._execute_with_resilience("generate_text", _call, task_id=task_id)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate 768-dim normalized semantic vector embedding via configured provider."""
        return await self.primary_provider.generate_embedding(text)

    def _record_usage(self, usage: Dict[str, Any]) -> None:
        """Update gateway token usage counters."""
        self.total_tokens_used += usage.get("total_tokens", 0)
        self.prompt_tokens_used += usage.get("prompt_tokens", 0)
        self.completion_tokens_used += usage.get("completion_tokens", 0)

    def get_metrics(self) -> Dict[str, Any]:
        """Retrieve token and circuit breaker telemetry metrics."""
        breakers_metrics = [b.get_metrics() for b in self.circuit_registry.list_breakers()]
        return {
            "total_tokens": self.total_tokens_used,
            "prompt_tokens": self.prompt_tokens_used,
            "completion_tokens": self.completion_tokens_used,
            "total_retries": self.total_retries,
            "total_fallbacks": self.total_fallbacks,
            "active_provider": self.last_used_provider,
            "active_model": self.last_used_model,
            "circuit_breakers": breakers_metrics,
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Return standardized health and resilience status for ModelGatewayHealthResponse."""
        from datetime import datetime, timezone

        # Ensure primary and configured fallback providers have breakers instantiated
        primary_breaker = self.circuit_registry.get_breaker(
            self.primary_provider.provider_name, self.primary_provider.model_name
        )
        for fb in self.fallback_providers:
            self.circuit_registry.get_breaker(fb.provider_name, fb.model_name)

        breakers = self.circuit_registry.list_breakers()
        breaker_statuses = [b.to_status_dict() for b in breakers]

        is_primary_open = primary_breaker.state == CircuitState.OPEN
        any_open = any(b.state == CircuitState.OPEN for b in breakers)
        all_open = all(b.state == CircuitState.OPEN for b in breakers) if breakers else False

        if all_open:
            overall_status = "UNAVAILABLE"
        elif is_primary_open or any_open:
            overall_status = "DEGRADED"
        else:
            overall_status = "HEALTHY"

        last_times = [
            b._last_success_time for b in breakers if b._last_success_time
        ] + [
            b._last_failure_time for b in breakers if b._last_failure_time
        ]
        last_active_at = (
            datetime.fromtimestamp(max(last_times), tz=timezone.utc)
            if last_times
            else None
        )

        return {
            "status": overall_status,
            "circuit_breaker_enabled": settings.CIRCUIT_BREAKER_ENABLED,
            "active_primary_provider": self.primary_provider.provider_name,
            "active_primary_model": self.primary_provider.model_name,
            "fallback_enabled": settings.MODEL_FALLBACK_ENABLED,
            "fallback_models": [p.model_name for p in self.fallback_providers],
            "breakers": breaker_statuses,
            "metrics": {
                "total_requests": sum(b.total_calls for b in breakers),
                "total_prompt_tokens": self.prompt_tokens_used,
                "total_completion_tokens": self.completion_tokens_used,
                "total_retries": self.total_retries,
                "total_fallbacks": self.total_fallbacks,
                "last_active_at": last_active_at,
            },
            "timestamp": datetime.now(timezone.utc),
        }
