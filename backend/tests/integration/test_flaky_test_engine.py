"""Integration tests for FlakyTestDetector and test stability intelligence.
Tests real sandbox execution across consistent failures, deterministic flaky fixtures,
database persistence, LangGraph routing bypass, and REST API endpoints.
"""
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import create_workflow_graph
from app.agents.specialists.tester import tester_node as run_tester_node
from app.agents.state import DevoraWorkflowState
from app.models.flaky_test_record import FlakyTestRecord
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.flaky_detector import FlakyTestDetector
from app.services.sandbox_service import LocalIsolatedRunner, SandboxService
from app.services.test_discovery_service import TestDiscoveryService


@pytest.fixture
def sandbox():
    return SandboxService(runner=LocalIsolatedRunner())


# ---------------------------------------------------------------------------
# 1. Consistent Failure Real Sandbox Test
# ---------------------------------------------------------------------------


def test_consistent_failure_sandbox_execution(tmp_path: Path):
    """Verify that a genuine code bug consistently fails across all repeat runs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_broken.py").write_text(
        "def test_always_fails(): assert 1 == 2\n",
        encoding="utf-8",
    )

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    plan = discovery.select_tests_for_changes(suite, workspace, ["tests/test_broken.py"])

    runner = LocalIsolatedRunner()
    exec_res = runner.run_command(command=plan.command, workspace_path=workspace)
    norm = discovery.parse_test_output(
        framework=plan.framework,
        stdout=exec_res.stdout,
        stderr=exec_res.stderr,
        exit_code=exec_res.exit_code,
        duration_seconds=exec_res.duration_seconds,
        command=plan.command,
    )

    detector = FlakyTestDetector(sandbox=SandboxService(runner=runner), discovery=discovery)
    report = detector.detect_flakiness(
        workspace_path=workspace,
        test_command=plan.command,
        framework=plan.framework,
        initial_failed_result=norm,
        repeat_runs=3,
    )

    assert report.is_flaky is False
    assert report.classification == "CONSISTENT_FAILURE"
    assert report.stability_score == 0.0
    assert report.total_runs == 3
    assert report.failed_runs == 3
    assert report.passed_runs == 0


# ---------------------------------------------------------------------------
# 2. Controlled Non-Deterministic / Flaky Fixture Test
# ---------------------------------------------------------------------------


def test_flaky_test_detection_sandbox_execution(tmp_path: Path):
    """Verify that a non-deterministic test is correctly identified as FLAKY with stability score."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tests_dir = workspace / "tests"
    tests_dir.mkdir()

    # Creates a stateful counter that fails on run 1, passes on run 2 and 3
    (tests_dir / "test_flaky_sim.py").write_text(
        "from pathlib import Path\n"
        "COUNTER = Path(__file__).parent / '.counter'\n"
        "def test_intermittent():\n"
        "    val = int(COUNTER.read_text()) if COUNTER.exists() else 0\n"
        "    COUNTER.write_text(str(val + 1))\n"
        "    assert val > 0, 'Initial transient failure'\n",
        encoding="utf-8",
    )

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    plan = discovery.select_tests_for_changes(suite, workspace, ["tests/test_flaky_sim.py"])

    runner = LocalIsolatedRunner()
    # Run 1 fails
    exec_res = runner.run_command(command=plan.command, workspace_path=workspace)
    norm = discovery.parse_test_output(
        framework=plan.framework,
        stdout=exec_res.stdout,
        stderr=exec_res.stderr,
        exit_code=exec_res.exit_code,
        duration_seconds=exec_res.duration_seconds,
        command=plan.command,
    )
    assert norm.passed is False

    # Flaky detector runs repeat executions
    detector = FlakyTestDetector(sandbox=SandboxService(runner=runner), discovery=discovery)
    report = detector.detect_flakiness(
        workspace_path=workspace,
        test_command=plan.command,
        framework=plan.framework,
        initial_failed_result=norm,
        repeat_runs=3,
    )

    assert report.is_flaky is True
    assert report.classification == "FLAKY"
    assert report.total_runs == 3
    assert report.passed_runs == 2
    assert report.failed_runs == 1
    assert report.stability_score == 66.7
    assert len(report.execution_history) == 3


# ---------------------------------------------------------------------------
# 3. LangGraph Routing Bypass for Flaky Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flaky_test_langgraph_routing_bypass():
    """Verify that LangGraph route_after_tester bypasses retry_incrementer on confirmed flaky tests."""
    from app.agents.graph import route_after_tester

    # Case A: Consistent failure -> routes to retry_incrementer
    consistent_state: DevoraWorkflowState = {
        "test_results": {
            "passed": False,
            "is_flaky": False,
            "stability_classification": "CONSISTENT_FAILURE",
        },
        "retry_count": 0,
        "maximum_retries": 3,
    }
    assert route_after_tester(consistent_state) == "retry_incrementer"

    # Case B: Confirmed flaky test -> routes to code_reviewer (bypasses retry loop)
    flaky_state: DevoraWorkflowState = {
        "test_results": {
            "passed": False,
            "is_flaky": True,
            "stability_classification": "FLAKY",
        },
        "retry_count": 0,
        "maximum_retries": 3,
    }
    assert route_after_tester(flaky_state) == "code_reviewer"


# ---------------------------------------------------------------------------
# 4. Database Persistence & Query Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_persistence_and_summary(
    db_session: AsyncSession,
    test_user: User,
    test_repository: Repository,
):
    """Test FlakyTestDetector recording and stability summary calculation."""
    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        project_id=test_repository.project_id,
        repository_id=test_repository.id,
        created_by=test_user.id,
        title="Test Task Flaky",
        prompt="Fix intermittent issue",
    )
    db_session.add(task)
    await db_session.flush()

    detector = FlakyTestDetector()
    from app.services.flaky_detector import FlakyDetectionReport

    mock_report = FlakyDetectionReport(
        test_identifier="tests/test_cache.py::test_redis_timeout",
        test_file="tests/test_cache.py",
        framework="pytest",
        command="pytest -v tests/test_cache.py",
        classification="FLAKY",
        stability_score=66.7,
        total_runs=3,
        passed_runs=2,
        failed_runs=1,
        infrastructure_error_runs=0,
        timeout_runs=0,
        execution_history=[{"run_index": 1, "passed": False}, {"run_index": 2, "passed": True}],
        diagnostic_message="Flaky test detected",
        is_flaky=True,
    )

    rec = await detector.record_flaky_test(
        repository_id=test_repository.id,
        task_id=task.id,
        report=mock_report,
        db=db_session,
    )

    assert rec.id is not None
    assert rec.classification == "FLAKY"
    assert rec.stability_score == 66.7

    # Query repository summary
    summary = await detector.get_repository_stability_summary(
        repository_id=test_repository.id,
        db=db_session,
    )
    assert summary["total_tests_tracked"] >= 1
    assert summary["flaky_tests_count"] >= 1
    assert summary["average_stability_score"] > 0


# ---------------------------------------------------------------------------
# 5. REST API Endpoints Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flaky_tests_api_endpoints(
    client: AsyncClient,
    auth_headers: dict,
    test_repository: Repository,
    db_session: AsyncSession,
    test_user: User,
):
    """Test REST API routes for listing flaky tests and stability statistics."""
    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        project_id=test_repository.project_id,
        repository_id=test_repository.id,
        created_by=test_user.id,
        title="Task API Flaky",
        prompt="Sample",
    )
    db_session.add(task)
    await db_session.flush()

    rec = FlakyTestRecord(
        repository_id=test_repository.id,
        task_id=task.id,
        test_identifier="tests/test_api.py::test_latency",
        test_file="tests/test_api.py",
        framework="pytest",
        language="python",
        test_command="pytest -v tests/test_api.py",
        classification="FLAKY",
        stability_score=66.7,
        total_runs=3,
        passed_runs=2,
        failed_runs=1,
        infrastructure_error_runs=0,
        timeout_runs=0,
        execution_history={},
    )
    db_session.add(rec)
    await db_session.flush()

    # 1. GET /api/v1/repositories/{id}/flaky-tests
    resp = await client.get(
        f"/api/v1/repositories/{test_repository.id}/flaky-tests",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["classification"] == "FLAKY"

    # 2. GET /api/v1/repositories/{id}/test-stability
    resp_stab = await client.get(
        f"/api/v1/repositories/{test_repository.id}/test-stability",
        headers=auth_headers,
    )
    assert resp_stab.status_code == 200
    stab_data = resp_stab.json()
    assert stab_data["flaky_tests_count"] >= 1

    # 3. GET /api/v1/tasks/{id}/flaky-tests
    resp_task = await client.get(
        f"/api/v1/tasks/{task.id}/flaky-tests",
        headers=auth_headers,
    )
    assert resp_task.status_code == 200
    task_flaky = resp_task.json()
    assert len(task_flaky) >= 1

    # 4. GET /api/v1/flaky-tests/{id}
    resp_detail = await client.get(
        f"/api/v1/flaky-tests/{rec.id}",
        headers=auth_headers,
    )
    assert resp_detail.status_code == 200
    assert resp_detail.json()["id"] == str(rec.id)
