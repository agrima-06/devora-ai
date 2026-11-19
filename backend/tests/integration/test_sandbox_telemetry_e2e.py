"""Integration tests for Phase 9 Stage 9.3: Sandbox Resilience, OOM Classification & Resource Telemetry."""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import route_after_tester
from app.agents.specialists.tester import tester_node as run_tester_node
from app.agents.state import DevoraWorkflowState, TestRunOutput
from app.models.task import Task
from app.models.test_run import TestRun
from app.services.flaky_detector import FlakyTestDetector
from app.services.sandbox_service import ExecutionResult, SandboxExitClassifier
from app.services.test_discovery_service import NormalizedTestResult, TestDiscoveryService


@pytest.mark.asyncio
async def test_tester_node_captures_and_forwards_telemetry(tmp_path: Path):
    """Verify tester_node captures empirical telemetry from sandbox and embeds into TestRunOutput."""
    # Create simple python test repository in tmp_path
    test_file = tmp_path / "test_calc.py"
    test_file.write_text("def test_add():\n    assert 1 + 1 == 2\n")

    state: DevoraWorkflowState = {
        "task_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "repository_id": str(uuid.uuid4()),
        "workspace_path": str(tmp_path),
        "target_branch": "main",
        "task_description": "Verify calculation logic",
        "task_type": "bug_fix",
        "retry_count": 0,
        "maximum_retries": 3,
        "agent_execution_history": [],
    }

    result = await run_tester_node(state)
    assert result["current_agent"] == "tester"
    assert "test_results" in result

    tr = result["test_results"]
    assert tr["passed"] is True
    assert tr["exit_code"] == 0
    assert tr["exit_classification"] == "SUCCESS"
    assert tr["resource_telemetry_available"] is True
    assert tr["wall_time_seconds"] is not None
    assert tr["peak_memory_rss_mb"] is not None
    assert tr["peak_memory_rss_mb"] > 0


def test_routing_bypasses_retry_on_oom_killed():
    """route_after_tester must route directly to reporter on OOM to prevent destructive code rewrites."""
    state: DevoraWorkflowState = {
        "retry_count": 0,
        "maximum_retries": 3,
        "test_results": {
            "passed": False,
            "exit_code": 137,
            "oom_killed": True,
            "exit_classification": "OOM_KILLED",
            "failure_classification": "OOM_KILLED",
        },
    }
    next_node = route_after_tester(state)
    assert next_node == "reporter"


def test_routing_bypasses_retry_on_timeout():
    """route_after_tester must route directly to reporter on timeout expired."""
    state: DevoraWorkflowState = {
        "retry_count": 0,
        "maximum_retries": 3,
        "test_results": {
            "passed": False,
            "exit_code": 124,
            "exit_classification": "TIMEOUT",
            "failure_classification": "TIMEOUT",
        },
    }
    next_node = route_after_tester(state)
    assert next_node == "reporter"


def test_routing_bypasses_retry_on_missing_or_unexecutable_commands():
    """route_after_tester must route directly to reporter on missing command (127) or non-executable binary (126)."""
    # 1. Command not found
    state_127: DevoraWorkflowState = {
        "retry_count": 0,
        "maximum_retries": 3,
        "test_results": {
            "passed": False,
            "exit_code": 127,
            "exit_classification": "COMMAND_NOT_FOUND",
            "failure_classification": "COMMAND_NOT_FOUND",
        },
    }
    assert route_after_tester(state_127) == "reporter"

    # 2. Command not executable
    state_126: DevoraWorkflowState = {
        "retry_count": 0,
        "maximum_retries": 3,
        "test_results": {
            "passed": False,
            "exit_code": 126,
            "exit_classification": "COMMAND_NOT_EXECUTABLE",
            "failure_classification": "COMMAND_NOT_EXECUTABLE",
        },
    }
    assert route_after_tester(state_126) == "reporter"


def test_flaky_detector_ignores_oom_and_resource_faults(tmp_path: Path):
    """FlakyTestDetector must exclude repeat runs that fail due to OOM or timeout from valid test executions."""
    mock_sandbox = MagicMock()
    # Repeat runs: run 2 OOM killed, run 3 passes
    mock_sandbox.execute_command.side_effect = [
        # Run 2: OOM killed
        ExecutionResult(
            exit_code=137,
            stdout="",
            stderr="Killed",
            duration_seconds=1.5,
            oom_killed=True,
            exit_classification="OOM_KILLED",
            termination_reason="OOMKilled by kernel",
        ),
        # Run 3: Clean pass
        ExecutionResult(
            exit_code=0,
            stdout="1 passed",
            stderr="",
            duration_seconds=0.8,
            oom_killed=False,
            exit_classification="SUCCESS",
        ),
    ]

    initial_fail = NormalizedTestResult(
        framework="pytest",
        command="pytest tests/test_calc.py",
        exit_code=1,
        passed=False,
        total_tests=1,
        passed_tests=0,
        failed_tests=1,
        skipped_tests=0,
        duration_seconds=1.0,
        raw_stdout="",
        raw_stderr="AssertionError",
        failure_details=["FAILED tests/test_calc.py::test_calc"],
        selected_test_files=["tests/test_calc.py"],
    )

    detector = FlakyTestDetector(sandbox=mock_sandbox, discovery=TestDiscoveryService())
    report = detector.detect_flakiness(
        workspace_path=tmp_path,
        test_command="pytest tests/test_calc.py",
        framework="pytest",
        initial_failed_result=initial_fail,
        repeat_runs=3,
    )

    # Run 1 (Assertion failure) + Run 3 (Pass) = 1 pass, 1 fail out of 2 valid executions = 50% stability (FLAKY)
    # Run 2 was an OOM killed infrastructure fault and must NOT be counted as a test assertion failure
    assert report.total_runs == 3
    assert report.passed_runs == 1
    assert report.failed_runs == 1
    assert report.infrastructure_error_runs == 1
    assert report.stability_score == 50.0
    assert report.classification == "FLAKY"
    assert report.is_flaky is True


@pytest.mark.asyncio
async def test_test_run_telemetry_persistence(db_session: AsyncSession, test_user, test_repository):
    """Verify TestRun database model stores and retrieves extended telemetry columns."""
    task = Task(
        project_id=test_repository.project_id,
        repository_id=test_repository.id,
        created_by=test_user.id,
        title="Test Telemetry Task",
        prompt="Fix calculation bug",
        task_type="bug_fix",
        status="IN_PROGRESS",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    test_run = TestRun(
        task_id=task.id,
        iteration=1,
        command="pytest",
        exit_code=137,
        passed=False,
        total_tests=10,
        passed_tests=8,
        failed_tests=2,
        duration_seconds=4.5,
        peak_memory_rss_bytes=1572864000,
        peak_memory_rss_mb=1500.0,
        cpu_time_seconds=3.21,
        wall_time_seconds=4.50,
        memory_limit_bytes=1572864000,
        memory_limit_mb=1500.0,
        cpu_limit=2.0,
        oom_killed=True,
        termination_reason="Container exceeded memory limit (OOMKilled by Linux kernel)",
        exit_classification="OOM_KILLED",
        resource_telemetry_available=True,
    )
    db_session.add(test_run)
    await db_session.commit()
    await db_session.refresh(test_run)

    assert test_run.oom_killed is True
    assert test_run.exit_classification == "OOM_KILLED"
    assert test_run.peak_memory_rss_mb == 1500.0
    assert test_run.memory_limit_mb == 1500.0
    assert test_run.cpu_time_seconds == 3.21
    assert test_run.cpu_limit == 2.0
    assert test_run.resource_telemetry_available is True
