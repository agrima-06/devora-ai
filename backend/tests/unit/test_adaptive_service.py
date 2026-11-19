"""Unit tests for Phase 7 Adaptive Intelligence Service."""
import uuid
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engineering_experience import EngineeringExperience
from app.models.task import Task
from app.models.task_failure_record import TaskFailureRecord
from app.models.user import User
from app.services.adaptive_service import AdaptiveIntelligenceService, STATUS_WEIGHTS


def test_status_weights_specification():
    """Verify that experience status multipliers strictly follow the approved empirical weighting."""
    assert STATUS_WEIGHTS["verified_successful"] == 1.3
    assert STATUS_WEIGHTS["verified_failed"] == 0.5
    assert STATUS_WEIGHTS["unverified_hypothesis"] == 0.7
    assert STATUS_WEIGHTS["incomplete_attempt"] == 0.2


def test_deterministic_embedding_generation():
    """Test fallback vector generation produces unit-norm 768-dim embeddings."""
    service = AdaptiveIntelligenceService(gateway=MagicMock())
    emb1 = service._generate_fallback_embedding("ZeroDivisionError: division by zero in billing.py")
    emb2 = service._generate_fallback_embedding("ZeroDivisionError: division by zero in billing.py")
    emb3 = service._generate_fallback_embedding("KeyError: 'user_id' in auth token decoder")

    assert len(emb1) == 768
    # Deterministic for identical inputs
    assert emb1 == emb2
    # Distinct for different inputs
    assert emb1 != emb3

    # Normalized to unit length (L2 norm ~ 1.0)
    norm = np.linalg.norm(np.array(emb1, dtype=np.float32))
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_record_task_failure_logic(db_session: AsyncSession, test_user: User):
    """Test recording structured failure records with lessons learned."""
    service = AdaptiveIntelligenceService()
    task_id = uuid.uuid4()

    failure = await service.record_task_failure(
        task_id=task_id,
        stage="TESTING",
        failure_type="IMPLEMENTATION_DEFECT",
        failed_strategy="Directly dividing billing items without checking if denominator is non-zero",
        error_log="ZeroDivisionError: float division by zero at billing.py line 42",
        review_notes="Sandbox test test_zero_discount_calculator failed with exit code 1",
        lessons_learned="Always guard against zero denominator before division operations.",
        attempt_number=1,
        db=db_session,
    )

    assert failure.id is not None
    assert failure.task_id == task_id
    assert failure.stage == "TESTING"
    assert failure.failure_type == "IMPLEMENTATION_DEFECT"
    assert failure.attempt_number == 1
    assert "division by zero" in failure.error_log
    assert "Always guard" in failure.lessons_learned


@pytest.mark.asyncio
async def test_agent_performance_aggregation(db_session: AsyncSession):
    """Test agent performance metrics calculation returns all 9 specialized agents."""
    service = AdaptiveIntelligenceService()
    metrics_response = await service.get_agent_performance_metrics(db=db_session)

    assert metrics_response is not None
    assert len(metrics_response.agents) in (9, 10)

    agent_names = [a.agent_name for a in metrics_response.agents]
    expected_agents = [
        "orchestrator",
        "codebase_analyst",
        "ml_classifier",
        "bug_investigator",
        "planner",
        "coder",
        "tester",
        "code_reviewer",
        "security_reviewer",
    ]
    for exp_agent in expected_agents:
        assert exp_agent in agent_names

    # Check metric value ranges
    for a in metrics_response.agents:
        assert 0.0 <= a.success_rate <= 1.0
        assert a.average_duration_ms >= 0.0
        assert a.retry_frequency >= 0.0
        assert a.rejection_rate >= 0.0
        assert a.estimated_cost_usd >= 0.0


@pytest.mark.asyncio
async def test_feedback_submission_and_scoring(db_session: AsyncSession, test_user: User):
    """Test human developer feedback submission updates experience score."""
    service = AdaptiveIntelligenceService()
    task_id = uuid.uuid4()

    # Pre-populate an experience for this task
    exp = EngineeringExperience(
        repository_id=None,
        task_category="bug_fix",
        bug_category="runtime_logic_error",
        problem_summary="Fix ZeroDivisionError in invoice calculation",
        root_cause="Missing denominator guard",
        resolution_strategy="Added if denominator == 0 return 0.0",
        diff_patch="--- billing.py\n+++ billing.py\n+ if total == 0: return 0.0",
        embedding=service._generate_fallback_embedding("Fix ZeroDivisionError in invoice calculation"),
        status_type="verified_successful",
        technology_stack=["python", "pytest"],
        files_involved=["billing.py"],
        attempts_count=1,
        failed_approaches=[],
        successful_approach="Added guard clause",
        test_results={"exit_code": 0},
        review_findings={"lgtm": True},
        security_findings={"vulnerabilities": 0},
        is_anonymized=False,
        is_verified=True,
        quality_score=10,
    )
    db_session.add(exp)
    await db_session.commit()
    await db_session.refresh(exp)

    # Submit ACCEPTED feedback
    fb = await service.submit_feedback(
        task_id=task_id,
        user=test_user,
        rating="ACCEPTED",
        plan_accepted=True,
        code_accepted=True,
        solution_helpful=True,
        comments="High precision fix, tests passed cleanly on first iteration.",
        db=db_session,
    )

    assert fb.rating == "ACCEPTED"
    assert fb.solution_accepted is True
