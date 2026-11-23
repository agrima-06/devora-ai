"""Unit tests for Phase 9 Stage 9.6: Reliability Observability Service."""
import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.reliability import (
    ModelGatewayReliabilitySummary,
    RecoveryOperationsSummary,
    ReliabilityEventItem,
    ReliabilityOverviewResponse,
    SandboxReliabilitySummary,
    SubsystemHealth,
    TestStabilitySummary,
    WorkflowReliabilitySummary,
)
from app.services.reliability_service import ReliabilityService


@pytest.fixture
def reliability_service():
    return ReliabilityService()


def test_subsystem_health_empty_initial_state(reliability_service):
    """Subsystems with no recorded activity must report UNKNOWN, never false HEALTHY."""
    empty_wf = WorkflowReliabilitySummary()
    empty_sb = SandboxReliabilitySummary()
    empty_stab = TestStabilitySummary()
    empty_gw = ModelGatewayReliabilitySummary(
        status="UNKNOWN",
        active_primary_provider="gemini",
        active_primary_model="gemini-1.5-pro",
        fallback_enabled=False,
    )
    empty_rec = RecoveryOperationsSummary()

    # Create mock session that returns 0 for agent runs and github installations
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_db.execute.return_value = mock_result

    # Run _evaluate_subsystems
    import asyncio
    subsystems = asyncio.run(
        reliability_service._evaluate_subsystems(
            db=mock_db,
            user_id=uuid.uuid4(),
            workflow_summary=empty_wf,
            sandbox_summary=empty_sb,
            test_stability_summary=empty_stab,
            gateway_summary=empty_gw,
            recovery_summary=empty_rec,
        )
    )

    statuses = {s.name: s.status for s in subsystems}
    assert statuses["workflow"] == "UNKNOWN"
    assert statuses["sandbox"] == "UNKNOWN"
    assert statuses["agent"] == "UNKNOWN"
    assert statuses["flaky"] == "UNKNOWN"
    assert statuses["recovery"] == "UNKNOWN"
    assert statuses["github"] == "UNKNOWN"


def test_subsystem_health_degraded_on_high_interruptions(reliability_service):
    """Workflow engine must report DEGRADED when multiple interrupted tasks exist."""
    wf_summary = WorkflowReliabilitySummary(
        total_tasks=10,
        running_tasks=1,
        completed_tasks=5,
        failed_tasks=4,
        interrupted_tasks=4,  # > 3 interrupted
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 10
    mock_db.execute.return_value = mock_result

    import asyncio
    subsystems = asyncio.run(
        reliability_service._evaluate_subsystems(
            db=mock_db,
            user_id=uuid.uuid4(),
            workflow_summary=wf_summary,
            sandbox_summary=SandboxReliabilitySummary(total_runs=5, passed_runs=5),
            test_stability_summary=TestStabilitySummary(total_tracked_tests=5, stable_pass_count=5),
            gateway_summary=ModelGatewayReliabilitySummary(
                status="HEALTHY",
                active_primary_provider="gemini",
                active_primary_model="gemini-1.5-pro",
                fallback_enabled=True,
            ),
            recovery_summary=RecoveryOperationsSummary(interrupted_tasks_count=4, recovery_eligible_count=4),
        )
    )

    statuses = {s.name: s.status for s in subsystems}
    assert statuses["workflow"] == "DEGRADED"
    assert "interrupted tasks require recovery" in subsystems[0].last_failure_reason


def test_sandbox_degraded_on_oom_or_timeouts(reliability_service):
    """Sandbox runner must report DEGRADED when OOM kills or timeouts occur."""
    sb_summary = SandboxReliabilitySummary(
        total_runs=10,
        passed_runs=6,
        failed_runs=4,
        oom_terminations=3,  # > 2
        timeouts=1,
        avg_peak_memory_mb=180.0,
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    mock_db.execute.return_value = mock_result

    import asyncio
    subsystems = asyncio.run(
        reliability_service._evaluate_subsystems(
            db=mock_db,
            user_id=uuid.uuid4(),
            workflow_summary=WorkflowReliabilitySummary(total_tasks=5, completed_tasks=5),
            sandbox_summary=sb_summary,
            test_stability_summary=TestStabilitySummary(),
            gateway_summary=ModelGatewayReliabilitySummary(
                status="HEALTHY",
                active_primary_provider="gemini",
                active_primary_model="gemini-1.5-pro",
                fallback_enabled=False,
            ),
            recovery_summary=RecoveryOperationsSummary(),
        )
    )

    statuses = {s.name: s.status for s in subsystems}
    assert statuses["sandbox"] == "DEGRADED"
    assert "Resource exhaustion detected" in next(s for s in subsystems if s.name == "sandbox").last_failure_reason


def test_flaky_subsystem_degraded_when_flaky_tests_found(reliability_service):
    """Flaky test subsystem must report DEGRADED when non-deterministic tests exist."""
    flaky_summary = TestStabilitySummary(
        total_tracked_tests=10,
        stable_pass_count=8,
        flaky_count=2,  # > 0
        avg_stability_score=85.0,
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    mock_db.execute.return_value = mock_result

    import asyncio
    subsystems = asyncio.run(
        reliability_service._evaluate_subsystems(
            db=mock_db,
            user_id=uuid.uuid4(),
            workflow_summary=WorkflowReliabilitySummary(),
            sandbox_summary=SandboxReliabilitySummary(),
            test_stability_summary=flaky_summary,
            gateway_summary=ModelGatewayReliabilitySummary(
                status="HEALTHY",
                active_primary_provider="gemini",
                active_primary_model="gemini-1.5-pro",
                fallback_enabled=False,
            ),
            recovery_summary=RecoveryOperationsSummary(),
        )
    )

    statuses = {s.name: s.status for s in subsystems}
    assert statuses["flaky"] == "DEGRADED"
    assert "2 non-deterministic tests identified" in next(s for s in subsystems if s.name == "flaky").last_failure_reason


def test_model_gateway_multi_worker_disclosure():
    """Model Gateway summary must explicitly disclose process-local deployment topology."""
    summary = ModelGatewayReliabilitySummary(
        status="HEALTHY",
        active_primary_provider="gemini",
        active_primary_model="gemini-1.5-pro",
        fallback_enabled=True,
        fallback_models=["gemini-1.5-flash"],
        multi_worker_shared_state=False,
        deployment_topology="PROCESS_LOCAL_WITH_DB_SYNC",
    )

    assert summary.multi_worker_shared_state is False
    assert summary.deployment_topology == "PROCESS_LOCAL_WITH_DB_SYNC"


def test_event_credential_scrubbing():
    """Event messages and payloads must be scrubbed of API keys and bearer tokens."""
    from app.agents.gateway.exceptions import scrub_credentials
    from tests.fixtures.synthetic_credentials import get_synthetic_google_api_key, get_synthetic_github_pat

    dirty_msg = f"Model call failed with token {get_synthetic_github_pat()} and key {get_synthetic_google_api_key()}"
    clean_msg = scrub_credentials(dirty_msg)

    assert "ghp_" not in clean_msg
    assert "AIza" not in clean_msg
    assert "[REDACTED" in clean_msg
