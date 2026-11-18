"""Centralized Model Gateway: manages LLM provider lifecycle, token accounting, and schema enforcement."""
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

from app.agents.gateway.base import BaseLLMProvider
from app.agents.gateway.gemini import GeminiProvider
from app.agents.gateway.mock import MockLLMProvider
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("model_gateway")
T = TypeVar("T", bound=BaseModel)


class ModelGateway:
    """Centralized LLM gateway.
    Ensures all specialist agents access models through a single managed entrypoint.
    """

    _instance: Optional["ModelGateway"] = None

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider: BaseLLMProvider
        if provider:
            self.provider = provider
        elif settings.USE_MOCK_LLM or not settings.GEMINI_API_KEY:
            logger.info("using_mock_llm_provider", reason="configured_or_no_api_key")
            self.provider = MockLLMProvider()
        else:
            logger.info("using_gemini_provider", model=settings.GEMINI_MODEL)
            self.provider = GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.GEMINI_MODEL,
            )

        # Global cumulative telemetry
        self.total_tokens_used = 0
        self.prompt_tokens_used = 0
        self.completion_tokens_used = 0

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

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> T:
        """Execute structured generation with token accounting and error wrapping."""
        parsed, usage = await self.provider.generate_structured(
            prompt=prompt,
            response_model=response_model,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        self._record_usage(usage)
        return parsed

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Execute text generation with token accounting."""
        text, usage = await self.provider.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        self._record_usage(usage)
        return text

    def _record_usage(self, usage: Dict[str, Any]) -> None:
        """Update gateway token usage counters."""
        self.total_tokens_used += usage.get("total_tokens", 0)
        self.prompt_tokens_used += usage.get("prompt_tokens", 0)
        self.completion_tokens_used += usage.get("completion_tokens", 0)

    def get_metrics(self) -> Dict[str, int]:
        """Retrieve token telemetry metrics."""
        return {
            "total_tokens": self.total_tokens_used,
            "prompt_tokens": self.prompt_tokens_used,
            "completion_tokens": self.completion_tokens_used,
        }
