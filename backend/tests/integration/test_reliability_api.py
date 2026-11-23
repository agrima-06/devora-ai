"""Integration tests for Phase 9 Stage 9.6: Reliability Observability Console API."""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flaky_test_record import FlakyTestRecord
from app.models.model_gateway_health import ModelGatewayHealth
from app.models.project import Project
from app.models.repository import Repository
from app.models.task import Task
from app.models.test_run import TestRun
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.models.workflow_event import WorkflowEvent


@pytest.mark.asyncio
async def test_get_reliability_overview_empty(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test GET /api/v1/reliability/overview for a user with no tasks returns clean empty state."""
    res = await client.get("/api/v1/reliability/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "overall_system_status" in data
    assert data["overall_system_status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE", "UNKNOWN")
    assert "subsystems" in data
    assert len(data["subsystems"]) >= 7

    subsystem_names = [s["name"] for s in data["subsystems"]]
    assert "workflow" in subsystem_names
    assert "agent" in subsystem_names
    assert "sandbox" in subsystem_names
    assert "tester" in subsystem_names
    assert "flaky" in subsystem_names
    assert "recovery" in subsystem_names
    assert "gateway" in subsystem_names
    assert "github" in subsystem_names

    # Verify honest process-local disclosure for Model Gateway
    gw = data["model_gateway"]
    assert gw["multi_worker_shared_state"] is False
    assert gw["deployment_topology"] == "PROCESS_LOCAL_WITH_DB_SYNC"

    # Verify workflow & recovery summaries
    assert data["workflows"]["total_tasks"] == 0
    assert data["sandbox"]["total_runs"] == 0
    assert data["test_stability"]["total_tracked_tests"] == 0
    assert data["recovery"]["interrupted_tasks_count"] == 0


@pytest.mark.asyncio
async def test_get_reliability_overview_with_aggregated_data(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test GET /api/v1/reliability/overview aggregates workflow, sandbox, testing, and recovery metrics."""
    # 1. Create project and repository
    proj = Project(name="Overview Project", slug=f"ov-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="overview-repo",
        full_name="org/overview-repo",
        clone_url="https://github.com/org/overview-repo.git",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    # 2. Create tasks: 2 completed, 1 failed, 1 interrupted
    task_comp1 = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Completed Task 1",
        prompt="Fix calculation",
        status="COMPLETED",
        iterations_count=1,
    )
    task_comp2 = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Completed Task 2",
        prompt="Fix formatting",
        status="COMPLETED",
        iterations_count=2,
    )
    task_failed = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Failed Task",
        prompt="Complex change",
        status="FAILED",
        iterations_count=3,
    )
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    task_interrupted = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Interrupted Task",
        prompt="Hanging job",
        status="IN_PROGRESS",
        recovery_status="INTERRUPTED",
        recovery_attempts=1,
        last_heartbeat_at=expired_time,
    )
    db_session.add_all([task_comp1, task_comp2, task_failed, task_interrupted])
    await db_session.flush()

    # Add checkpoint for interrupted task so it is recoverable
    cp = WorkflowCheckpoint(
        task_id=task_interrupted.id,
        thread_id=str(task_interrupted.id),
        checkpoint_ns="",
        checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
        node_name="coder",
        step_number=4,
        version=1,
        state_blob={"task_id": str(task_interrupted.id), "current_agent": "coder"},
    )
    db_session.add(cp)

    # 3. Create TestRuns: 1 passed, 1 OOM, 1 Timeout
    tr_pass = TestRun(
        task_id=task_comp1.id,
        iteration=1,
        command="pytest",
        exit_code=0,
        passed=True,
        total_tests=10,
        passed_tests=10,
        failed_tests=0,
        duration_seconds=4.5,
        peak_memory_rss_mb=128.0,
        exit_classification="SUCCESS",
        resource_telemetry_available=True,
    )
    tr_oom = TestRun(
        task_id=task_failed.id,
        iteration=1,
        command="pytest -k heavy",
        exit_code=137,
        passed=False,
        total_tests=5,
        passed_tests=2,
        failed_tests=1,
        duration_seconds=12.0,
        peak_memory_rss_mb=2048.0,
        oom_killed=True,
        exit_classification="OOM_KILLED",
        resource_telemetry_available=True,
    )
    tr_timeout = TestRun(
        task_id=task_failed.id,
        iteration=2,
        command="pytest -k slow",
        exit_code=124,
        passed=False,
        total_tests=5,
        passed_tests=0,
        failed_tests=1,
        duration_seconds=120.0,
        peak_memory_rss_mb=256.0,
        exit_classification="TIMEOUT",
        resource_telemetry_available=True,
    )
    db_session.add_all([tr_pass, tr_oom, tr_timeout])

    # 4. Create FlakyTestRecord
    flaky_rec = FlakyTestRecord(
        repository_id=repo.id,
        task_id=task_failed.id,
        test_identifier="tests/test_async.py::test_race_condition",
        test_file="tests/test_async.py",
        test_command="pytest tests/test_async.py",
        framework="pytest",
        language="python",
        classification="FLAKY",
        stability_score=45.0,
        total_runs=6,
        passed_runs=3,
        failed_runs=3,
    )
    db_session.add(flaky_rec)

    # 5. Create ModelGatewayHealth
    gw_health = ModelGatewayHealth(
        provider_name="gemini",
        model_name="gemini-2.5-pro",
        circuit_state="CLOSED",
        consecutive_failures=0,
        consecutive_successes=42,
        total_calls=42,
        total_failures=0,
        total_retries=2,
        total_fallbacks=1,
    )
    db_session.add(gw_health)
    await db_session.commit()

    # 6. Execute GET /api/v1/reliability/overview
    res = await client.get("/api/v1/reliability/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    wf = data["workflows"]
    assert wf["total_tasks"] == 4
    assert wf["completed_tasks"] == 2
    assert wf["failed_tasks"] == 1
    assert wf["interrupted_tasks"] == 1

    sb = data["sandbox"]
    assert sb["total_runs"] == 3
    assert sb["passed_runs"] == 1
    assert sb["oom_terminations"] == 1
    assert sb["timeouts"] == 1

    ts = data["test_stability"]
    assert ts["total_tracked_tests"] == 1
    assert ts["flaky_count"] == 1
    assert ts["avg_stability_score"] == 45.0

    rec = data["recovery"]
    assert rec["interrupted_tasks_count"] >= 1
    assert rec["recovery_eligible_count"] >= 1
    assert len(rec["interrupted_tasks"]) >= 1

    interrupted_item = next((t for t in rec["interrupted_tasks"] if t["task_id"] == str(task_interrupted.id)), None)
    assert interrupted_item is not None
    assert interrupted_item["eligible"] is True
    assert interrupted_item["latest_node"] == "coder"


@pytest.mark.asyncio
async def test_get_reliability_overview_repository_scoping(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test GET /api/v1/reliability/overview filters correctly by repository_id."""
    proj = Project(name="Scoping Project", slug=f"sc-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo1 = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="repo-one",
        full_name="org/repo-one",
        clone_url="https://github.com/org/repo-one.git",
    )
    repo2 = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="repo-two",
        full_name="org/repo-two",
        clone_url="https://github.com/org/repo-two.git",
    )
    db_session.add_all([repo1, repo2])
    await db_session.flush()

    # Tasks for repo1
    for i in range(3):
        t = Task(
            project_id=proj.id,
            repository_id=repo1.id,
            created_by=test_user.id,
            title=f"Repo 1 Task {i}",
            prompt="Task prompt",
            status="COMPLETED",
        )
        db_session.add(t)

    # Task for repo2
    t2 = Task(
        project_id=proj.id,
        repository_id=repo2.id,
        created_by=test_user.id,
        title="Repo 2 Task",
        prompt="Task prompt",
        status="FAILED",
    )
    db_session.add(t2)
    await db_session.commit()

    # Query with repo1 scoping
    res1 = await client.get(f"/api/v1/reliability/overview?repository_id={repo1.id}", headers=auth_headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["workflows"]["total_tasks"] == 3
    assert data1["workflows"]["completed_tasks"] == 3
    assert data1["workflows"]["failed_tasks"] == 0

    # Query with repo2 scoping
    res2 = await client.get(f"/api/v1/reliability/overview?repository_id={repo2.id}", headers=auth_headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["workflows"]["total_tasks"] == 1
    assert data2["workflows"]["completed_tasks"] == 0
    assert data2["workflows"]["failed_tasks"] == 1


@pytest.mark.asyncio
async def test_get_reliability_events_filtering_and_scrubbing(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test GET /api/v1/reliability/events filtering, pagination, and credential scrubbing."""
    proj = Project(name="Events Project", slug=f"ev-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="events-repo",
        full_name="org/events-repo",
        clone_url="https://github.com/org/events-repo.git",
    )
    db_session.add(repo)
    await db_session.flush()

    task = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Events Task",
        prompt="Test events",
        status="IN_PROGRESS",
    )
    db_session.add(task)
    await db_session.flush()

    # Event 1: Sandbox info
    ev1 = WorkflowEvent(
        task_id=task.id,
        event_type="test_run_completed",
        agent_name="tester",
        message="Sandbox test run completed successfully",
        payload={"exit_code": 0, "passed": True},
    )
    # Event 2: Workflow error with sensitive tokens in message and payload
    from tests.fixtures.synthetic_credentials import get_synthetic_google_api_key, get_synthetic_github_pat
    secret_ghp = get_synthetic_github_pat()
    secret_aiza = get_synthetic_google_api_key()
    ev2 = WorkflowEvent(
        task_id=task.id,
        event_type="workflow_failed",
        agent_name="orchestrator",
        message=f"Model Gateway call failed with token {secret_ghp} and key {secret_aiza}",
        payload={"api_key": secret_aiza, "error": "Provider 500"},
    )
    # Event 3: Recovery event
    ev3 = WorkflowEvent(
        task_id=task.id,
        event_type="workflow_resumed",
        agent_name="recovery_manager",
        message="Workflow resumed safely from step 3",
        payload={"step": 3},
    )
    db_session.add_all([ev1, ev2, ev3])
    await db_session.commit()

    # Query all events
    res = await client.get("/api/v1/reliability/events", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["events"]) == 3

    # Verify credential scrubbing
    failed_ev = next((e for e in data["events"] if e["event_type"] == "workflow_failed"), None)
    assert failed_ev is not None
    assert secret_ghp not in failed_ev["message"]
    assert secret_aiza not in failed_ev["message"]
    assert "[REDACTED_TOKEN]" in failed_ev["message"]
    assert "[REDACTED_API_KEY]" in failed_ev["message"]
    assert secret_aiza not in str(failed_ev["payload"])

    # Query with subsystem filter
    res_sb = await client.get("/api/v1/reliability/events?subsystem=Sandbox", headers=auth_headers)
    assert res_sb.status_code == 200
    data_sb = res_sb.json()
    assert len(data_sb["events"]) >= 1
    assert all(e["subsystem"] == "Sandbox" for e in data_sb["events"])

    # Query with severity filter
    res_err = await client.get("/api/v1/reliability/events?severity=ERROR", headers=auth_headers)
    assert res_err.status_code == 200
    data_err = res_err.json()
    assert len(data_err["events"]) >= 1
    assert all(e["severity"] == "ERROR" for e in data_err["events"])

    # Query with pagination
    res_pag = await client.get("/api/v1/reliability/events?limit=1&offset=0", headers=auth_headers)
    assert res_pag.status_code == 200
    data_pag = res_pag.json()
    assert data_pag["total"] == 3
    assert len(data_pag["events"]) == 1


@pytest.mark.asyncio
async def test_get_reliability_trends_timeframes(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test GET /api/v1/reliability/trends across bounded timeframes (24h, 7d, 30d)."""
    proj = Project(name="Trends Project", slug=f"tr-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="trends-repo",
        full_name="org/trends-repo",
        clone_url="https://github.com/org/trends-repo.git",
    )
    db_session.add(repo)
    await db_session.flush()

    t_comp = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Completed Trend Task",
        prompt="Work",
        status="COMPLETED",
    )
    db_session.add(t_comp)
    await db_session.commit()

    # Query 7d trends
    res_7d = await client.get("/api/v1/reliability/trends?timeframe=7d", headers=auth_headers)
    assert res_7d.status_code == 200
    data_7d = res_7d.json()
    assert data_7d["timeframe"] == "7d"
    assert len(data_7d["trends"]) >= 7

    # Query 24h trends
    res_24h = await client.get("/api/v1/reliability/trends?timeframe=24h", headers=auth_headers)
    assert res_24h.status_code == 200
    data_24h = res_24h.json()
    assert data_24h["timeframe"] == "24h"
    assert len(data_24h["trends"]) >= 1

    # Query 30d trends
    res_30d = await client.get("/api/v1/reliability/trends?timeframe=30d", headers=auth_headers)
    assert res_30d.status_code == 200
    data_30d = res_30d.json()
    assert data_30d["timeframe"] == "30d"
    assert len(data_30d["trends"]) >= 30


@pytest.mark.asyncio
async def test_recovery_state_consistency_and_approval_invariants(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test state consistency: terminal or waiting approval tasks are never marked recoverable or resumable."""
    proj = Project(name="Invariants Project", slug=f"inv-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="inv-repo",
        full_name="org/inv-repo",
        clone_url="https://github.com/org/inv-repo.git",
    )
    db_session.add(repo)
    await db_session.flush()

    # Task waiting for approval
    t_waiting = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Waiting Approval Task",
        prompt="Check diff",
        status="WAITING_APPROVAL",
    )
    # Completed task
    t_comp = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Completed Task",
        prompt="Finished",
        status="COMPLETED",
    )
    db_session.add_all([t_waiting, t_comp])
    await db_session.commit()

    # Check overview: neither should be marked interrupted
    res = await client.get("/api/v1/reliability/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    interrupted_ids = [t["task_id"] for t in data["recovery"]["interrupted_tasks"]]
    assert str(t_waiting.id) not in interrupted_ids
    assert str(t_comp.id) not in interrupted_ids

    # Attempting to resume t_waiting or t_comp via /tasks/{id}/resume must return 400
    res_waiting = await client.post(f"/api/v1/tasks/{t_waiting.id}/resume", json={"force": False}, headers=auth_headers)
    assert res_waiting.status_code == 400

    res_comp = await client.post(f"/api/v1/tasks/{t_comp.id}/resume", json={"force": False}, headers=auth_headers)
    assert res_comp.status_code == 400
