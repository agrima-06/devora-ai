"""Unit tests for Centralized ModelGateway and provider abstraction."""
import pytest
from pydantic import BaseModel, Field

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.agents.state import OrchestratorDecision


class SampleModel(BaseModel):
    name: str = Field(...)
    score: int = Field(...)


@pytest.mark.asyncio
async def test_model_gateway_structured_generation():
    mock_provider = MockLLMProvider()
    gateway = ModelGateway(provider=mock_provider)

    decision = await gateway.generate_structured(
        prompt="Fix division by zero error in calculator",
        response_model=OrchestratorDecision,
    )

    assert isinstance(decision, OrchestratorDecision)
    assert decision.task_type in ("bug_fix", "feature", "refactor", "exploration")
    assert decision.next_agent is not None

    metrics = gateway.get_metrics()
    assert metrics["total_tokens"] > 0
    assert metrics["prompt_tokens"] > 0


@pytest.mark.asyncio
async def test_model_gateway_custom_response_override():
    mock_provider = MockLLMProvider()
    custom_inst = SampleModel(name="test_symbol", score=99)
    mock_provider.set_response(SampleModel, custom_inst)

    gateway = ModelGateway(provider=mock_provider)
    res = await gateway.generate_structured("prompt", response_model=SampleModel)

    assert res.name == "test_symbol"
    assert res.score == 99


@pytest.mark.asyncio
async def test_model_gateway_text_generation():
    mock_provider = MockLLMProvider()
    gateway = ModelGateway(provider=mock_provider)

    text = await gateway.generate_text("Summarize architecture")
    assert isinstance(text, str)
    assert len(text) > 0
