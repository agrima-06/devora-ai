"""Abstract base class for LLM providers."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Abstract interface for all model providers (Gemini, Mock, etc.)."""

    provider_name: str = "base"
    model_name: str = "default"

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        """Generate structured response validated against a Pydantic model.
        Returns:
            Tuple of (validated_pydantic_instance, usage_metadata)
        """
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate plain text or markdown response.
        Returns:
            Tuple of (response_text, usage_metadata)
        """
        pass

    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate 768-dimensional normalized semantic vector embedding.
        Returns:
            List of 768 float values.
        """
        pass
