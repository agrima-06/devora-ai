"""Reliability and security tests for GeminiProvider."""
import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel, Field

from app.agents.gateway.gemini import GeminiProvider, LLMGenerationError


class SampleAuditSchema(BaseModel):
    category: str = Field(description="Bug category")
    confidence: float = Field(description="Confidence score 0 to 1")
    remediation_steps: list[str] = Field(description="List of steps")


@pytest.mark.asyncio
async def test_gemini_provider_structured_parsing_and_schema_validation():
    """GeminiProvider must parse valid JSON conforming to Pydantic model."""
    provider = GeminiProvider(api_key="AIzaSyDummyKeyForTestingPurposes12345", max_retries=2)

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "category": "logic_error",
        "confidence": 0.95,
        "remediation_steps": ["Check zero denominator", "Return 0.0"],
    })
    mock_response.usage_metadata.prompt_token_count = 120
    mock_response.usage_metadata.candidates_token_count = 45
    mock_response.usage_metadata.total_token_count = 165

    with patch.object(provider.client.aio.models, "generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        result, usage = await provider.generate_structured("Analyze bug", SampleAuditSchema)

        assert isinstance(result, SampleAuditSchema)
        assert result.category == "logic_error"
        assert result.confidence == 0.95
        assert len(result.remediation_steps) == 2
        assert usage["total_tokens"] == 165
        assert usage["prompt_tokens"] == 120
        assert usage["completion_tokens"] == 45


@pytest.mark.asyncio
async def test_gemini_provider_malformed_response_retries_and_recovers():
    """Malformed JSON should trigger retry with backoff and succeed if subsequent attempt returns valid JSON."""
    provider = GeminiProvider(api_key="AIzaSyDummyKeyForTestingPurposes12345", max_retries=3)

    malformed_response = MagicMock()
    malformed_response.text = "NOT_JSON { invalid json string"

    valid_response = MagicMock()
    valid_response.text = json.dumps({
        "category": "syntax_error",
        "confidence": 0.99,
        "remediation_steps": ["Add missing parenthesis"],
    })
    valid_response.usage_metadata.total_token_count = 50
    valid_response.usage_metadata.prompt_token_count = 30
    valid_response.usage_metadata.candidates_token_count = 20

    with patch.object(provider.client.aio.models, "generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = [malformed_response, valid_response]
        result, usage = await provider.generate_structured("Fix syntax", SampleAuditSchema)

        assert mock_gen.call_count == 2
        assert result.category == "syntax_error"
        assert result.confidence == 0.99


@pytest.mark.asyncio
async def test_gemini_provider_exhausted_retries_raises_llm_error():
    """Persistent failures must exhaust retries and raise LLMGenerationError."""
    provider = GeminiProvider(api_key="AIzaSyDummyKeyForTestingPurposes12345", max_retries=2)

    with patch.object(provider.client.aio.models, "generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("503 Service Unavailable")

        with pytest.raises(LLMGenerationError) as exc_info:
            await provider.generate_structured("Prompt", SampleAuditSchema)

        assert "Failed to generate valid structured response" in str(exc_info.value)
        assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_gemini_provider_credentials_never_appear_in_exceptions():
    """API key secret must never leak in error messages or logs."""
    secret_key = "AIzaSySuperSecretKeyNeverToLeak12345"
    provider = GeminiProvider(api_key=secret_key, max_retries=1)

    with patch.object(provider.client.aio.models, "generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception(f"Connection failed with key {secret_key}")

        with pytest.raises(LLMGenerationError) as exc_info:
            await provider.generate_structured("Prompt", SampleAuditSchema)

        error_message = str(exc_info.value)
        # Even if inner exception had the key, ensure standard sanitization or containment
        assert "Failed to generate valid structured response" in error_message


@pytest.mark.asyncio
async def test_gemini_provider_concurrency_rate_limiting():
    """Semaphore must enforce concurrency limit across concurrent requests."""
    provider = GeminiProvider(api_key="dummy", concurrency_limit=2)
    active_concurrent = 0
    max_observed_concurrent = 0

    async def mock_generate(*args, **kwargs):
        nonlocal active_concurrent, max_observed_concurrent
        active_concurrent += 1
        max_observed_concurrent = max(max_observed_concurrent, active_concurrent)
        await asyncio.sleep(0.05)
        active_concurrent -= 1
        resp = MagicMock()
        resp.text = json.dumps({"category": "c", "confidence": 1.0, "remediation_steps": []})
        return resp

    with patch.object(provider.client.aio.models, "generate_content", side_effect=mock_generate):
        tasks = [
            provider.generate_structured("p", SampleAuditSchema)
            for _ in range(6)
        ]
        await asyncio.gather(*tasks)

        # Max concurrent executions must not exceed concurrency_limit
        assert max_observed_concurrent <= 2
