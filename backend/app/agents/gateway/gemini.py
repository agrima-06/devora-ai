"""Gemini LLM Provider using Google GenAI SDK with structured output and rate limiting."""
import asyncio
import json
import re
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.agents.gateway.base import BaseLLMProvider
from app.agents.gateway.exceptions import (
    InvalidStructuredOutputError,
    LLMGenerationError,
    ModelGatewayException,
    classify_provider_exception,
    scrub_credentials,
)
from app.core.exceptions import DevoraException
from app.core.logging import get_logger

logger = get_logger("gemini_provider")
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini model provider with retries, rate limiting, and structured JSON output."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        max_retries: int = 1,
        concurrency_limit: int = 5,
    ):
        self.provider_name = "gemini"
        self.api_key = api_key
        self.model_name = model_name
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.client = genai.Client(api_key=api_key)

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        """Call Gemini to generate structured output validated against response_model."""
        schema_json = json.dumps(response_model.model_json_schema())
        augmented_prompt = (
            f"{prompt}\n\n"
            f"CRITICAL REQUIREMENT: Return ONLY a valid JSON object matching this schema:\n"
            f"{schema_json}\n"
            f"Do not include markdown triple-backtick fences or conversational introductory text."
        )

        async with self.semaphore:
            last_err = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    config = types.GenerateContentConfig(
                        temperature=temperature,
                        response_mime_type="application/json",
                        response_schema=response_model,
                        system_instruction=system_instruction,
                        max_output_tokens=max_output_tokens,
                    )

                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=augmented_prompt,
                        config=config,
                    )

                    raw_text = (response.text or "").strip()
                    # Strip any markdown code fences if present
                    clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
                    clean_json = re.sub(r"\s*```$", "", clean_json, flags=re.MULTILINE).strip()

                    parsed_instance = response_model.model_validate_json(clean_json)

                    usage = self._extract_usage(response)
                    logger.info(
                        "gemini_structured_generation_success",
                        model=self.model_name,
                        schema=response_model.__name__,
                        total_tokens=usage.get("total_tokens", 0),
                    )
                    return parsed_instance, usage

                except (ValidationError, json.JSONDecodeError) as val_err:
                    last_err = val_err
                    logger.warning(
                        "gemini_validation_retry",
                        attempt=attempt,
                        error=str(val_err),
                    )
                    await asyncio.sleep(2 ** attempt)

                except Exception as api_err:
                    last_err = api_err
                    logger.warning(
                        "gemini_api_retry",
                        attempt=attempt,
                        error=str(api_err),
                    )
                    await asyncio.sleep(2 ** attempt)

            if isinstance(last_err, (ValidationError, json.JSONDecodeError)):
                raise InvalidStructuredOutputError(
                    f"Failed to generate valid structured response for {response_model.__name__}: {scrub_credentials(str(last_err))}"
                )
            base_exc = classify_provider_exception(last_err or Exception("Gemini generation failed"))
            raise type(base_exc)(
                f"Failed to generate valid structured response for {response_model.__name__}: {base_exc.message}"
            )

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Call Gemini to generate unstructured text/markdown."""
        async with self.semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    config = types.GenerateContentConfig(
                        temperature=temperature,
                        system_instruction=system_instruction,
                        max_output_tokens=max_output_tokens,
                    )
                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=config,
                    )
                    text = (response.text or "").strip()
                    usage = self._extract_usage(response)
                    return text, usage
                except Exception as exc:
                    if attempt == self.max_retries:
                        raise classify_provider_exception(exc)
                    await asyncio.sleep(2 ** attempt)

    def _extract_usage(self, response: Any) -> Dict[str, Any]:
        """Safely extract token usage metadata."""
        usage: Dict[str, Any] = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
        try:
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage["prompt_tokens"] = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                usage["completion_tokens"] = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                usage["total_tokens"] = getattr(response.usage_metadata, "total_token_count", 0) or 0
        except Exception:
            pass
        return usage

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate 768-dim normalized semantic embedding vector using Gemini."""
        if not text:
            return [0.0] * 768

        from app.config import settings
        from app.services.repo_intelligence_service import generate_embedding_vector

        async with self.semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    res = await self.client.aio.models.embed_content(
                        model=settings.GEMINI_EMBEDDING_MODEL,
                        contents=text,
                    )
                    if hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                        values = list(res.embedding.values)
                        if len(values) == 768:
                            return values
                    elif hasattr(res, "embeddings") and res.embeddings:
                        values = list(res.embeddings[0].values)
                        if len(values) == 768:
                            return values
                    return generate_embedding_vector(text, dim=768)
                except Exception as exc:
                    logger.warning("gemini_embedding_retry", attempt=attempt, error=str(exc))
                    if attempt == self.max_retries:
                        return generate_embedding_vector(text, dim=768)
                    await asyncio.sleep(2 ** attempt)
        return generate_embedding_vector(text, dim=768)
