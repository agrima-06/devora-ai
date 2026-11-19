"""Integration tests for Phase 9 Stage 9.4: Workflow Recovery Manager & Safe Autonomous Task Resumption."""
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.models.approval import Approval
from app.models.project import Project
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.services.git_workspace_manager import GitWorkspaceManager
from app.services.recovery_manager import WorkflowRecoveryManager
from app.services.workflow_service import WorkflowService


@pytest.fixture
def test_git_repo():
    """Create a real git repository fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)

        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "calculator.py").write_text('''def add(a: int, b: int) -> int:
    return a + b
''')

        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calculator.py").write_text('''from src.calculator import add

def test_add():
    assert add(1, 2) == 3
''')

        (repo_dir / "requirements.txt").write_text("pytest\n")
        (repo_dir / "README.md").write_text("# Test Repo\n")

        subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "config", "user.email", "tester@devora.ai"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

        yield str(repo_dir)


@pytest.mark.asyncio
async def test_workspace_preservation_avoids_clobbering_changes(tmp_path: Path):
    """GitWorkspaceManager must preserve uncommitted working tree edits when preserve_existing=True."""
    manager = GitWorkspaceManager(base_tasks_dir=tmp_path)
    task_id = str(uuid.uuid4())

    # 1. Initial setup
    ws = manager.prepare_task_workspace(
        task_id=task_id,
        repo_clone_url="",
        base_branch="main",
        preserve_existing=False,
    )
    assert ws.exists()
    assert (ws / ".git").exists()

    # 2. Simulate coder modifying workspace
    patch_file = ws / "patch.py"
    patch_file.write_text("# precision patch created by coder\ndef fix(): pass\n")
    assert patch_file.exists()

    # 3. Resume workspace with preserve_existing=True
    ws_resumed = manager.prepare_task_workspace(
        task_id=task_id,
        repo_clone_url="",
        base_branch="main",
        preserve_existing=True,
    )
    assert ws_resumed == ws
    # File must still be intact!
    assert patch_file.exists()
    assert "precision patch" in patch_file.read_text()


@pytest.mark.asyncio
async def test_workflow_creates_intermediate_checkpoints_at_each_node(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    test_git_repo: str,
):
    """Workflow execution must persist granular checkpoints with node_name and step_number."""
    mock_prov = MockLLMProvider()
    ModelGateway.set_instance(ModelGateway(provider=mock_prov))

    # 1. Create Project and Repository
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Checkpoint Test Project", "slug": f"cp-proj-{uuid.uuid4().hex[:6]}"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["id"]

    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "calc-service",
            "full_name": "local/calc-service",
            "clone_url": f"file://{test_git_repo}",
            "default_branch": "main",
        },
        headers=auth_headers,
    )
    repo_id = repo_res.json()["id"]

    # Index repo
    await client.post(f"/api/v1/repositories/{repo_id}/index", headers=auth_headers)

    # 2. Create and run task
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "repository_id": repo_id,
            "title": "Verify intermediate checkpointing",
            "prompt": "Test calculation logic",
            "task_type": "bug_fix",
            "target_branch": "main",
        },
        headers=auth_headers,
    )
    task_id = task_res.json()["id"]

    start_res = await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth_headers)
    assert start_res.status_code == 202

    # 3. Query checkpoints from PostgreSQL
    cp_stmt = (
        select(WorkflowCheckpoint)
        .where(WorkflowCheckpoint.task_id == uuid.UUID(task_id))
        .order_by(WorkflowCheckpoint.step_number.asc())
    )
    cp_res = await db_session.execute(cp_stmt)
    checkpoints = cp_res.scalars().all()

    # Must have multiple checkpoints recorded across agent steps
    assert len(checkpoints) >= 3
    nodes = [cp.node_name for cp in checkpoints if cp.node_name]
    assert "orchestrator" in nodes or "codebase_analyst" in nodes


@pytest.mark.asyncio
async def test_recovery_stops_at_human_approval_gate_without_side_effects(
    db_session: AsyncSession,
    test_user: User,
    test_git_repo: str,
):
    """Resuming at security_reviewer must pause at WAITING_APPROVAL without committing or pushing."""
    mock_prov = MockLLMProvider()
    ModelGateway.set_instance(ModelGateway(provider=mock_prov))

    # 1. Setup project, repo, and task directly in DB
    proj = Project(name="Safety Gate Project", slug=f"safety-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="safety-repo",
        full_name="local/safety-repo",
        clone_url=f"file://{test_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    task = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Check human approval safety invariant",
        prompt="Ensure no premature push occurs",
        task_type="bug_fix",
        status="IN_PROGRESS",
        recovery_status="INTERRUPTED",
        recovery_attempts=0,
    )
    db_session.add(task)
    await db_session.flush()

    # 2. Inject checkpoint at security_reviewer
    checkpoint_state = {
        "task_id": str(task.id),
        "user_id": str(test_user.id),
        "repository_id": str(repo.id),
        "target_branch": "main",
        "task_branch": f"devora/fix-{str(task.id)[:8]}",
        "task_description": task.title,
        "task_type": "bug_fix",
        "security_results": {"passed": True, "vulnerabilities": []},
        "current_agent": "security_reviewer",
        "retry_count": 0,
        "maximum_retries": 3,
        "execution_status": "ANALYZING",
    }
    cp = WorkflowCheckpoint(
        task_id=task.id,
        thread_id=str(task.id),
        checkpoint_ns="",
        checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
        node_name="security_reviewer",
        step_number=7,
        version=1,
        state_blob=checkpoint_state,
    )
    db_session.add(cp)
    await db_session.commit()

    # 3. Resume workflow
    service = WorkflowService()
    res = await service.resume_task_workflow(task.id, test_user, db_session)

    # 4. Verify paused safely at WAITING_APPROVAL
    await db_session.refresh(task)
    assert task.status == "WAITING_APPROVAL"
    assert res["status"] == "WAITING_APPROVAL"

    # Verify pending Approval record was created
    appr_stmt = select(Approval).where(Approval.task_id == task.id)
    appr_res = await db_session.execute(appr_stmt)
    approvals = appr_res.scalars().all()
    assert len(approvals) >= 1
    assert approvals[0].status == "PENDING"

    # Invariant: No PR URL or commit sha set yet
    assert task.pull_request_url is None


@pytest.mark.asyncio
async def test_recovery_api_endpoints_and_lease_conflict(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    test_user: User,
    test_git_repo: str,
):
    """Test /tasks/{id}/recovery, /tasks/recovery/scan, and /tasks/{id}/resume endpoints."""
    # 1. Setup project, repo, task
    proj = Project(name="API Test Project", slug=f"api-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="api-repo",
        full_name="local/api-repo",
        clone_url=f"file://{test_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    # Task interrupted with expired heartbeat
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    task = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="API recovery test task",
        prompt="Testing API endpoints",
        task_type="bug_fix",
        status="IN_PROGRESS",
        recovery_status="INTERRUPTED",
        recovery_attempts=0,
        last_heartbeat_at=expired_time,
    )
    db_session.add(task)
    await db_session.flush()

    # Add a valid checkpoint
    cp = WorkflowCheckpoint(
        task_id=task.id,
        thread_id=str(task.id),
        checkpoint_ns="",
        checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
        node_name="security_reviewer",
        step_number=6,
        version=1,
        state_blob={
            "task_id": str(task.id),
            "user_id": str(test_user.id),
            "repository_id": str(repo.id),
            "target_branch": "main",
            "security_results": {"passed": True},
            "current_agent": "security_reviewer",
        },
    )
    db_session.add(cp)
    await db_session.commit()

    # 2. Test GET /{task_id}/recovery
    rec_resp = await client.get(f"/api/v1/tasks/{task.id}/recovery", headers=auth_headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["task_id"] == str(task.id)
    assert rec_data["is_interrupted"] is True
    assert rec_data["is_eligible_for_recovery"] is True
    assert rec_data["latest_checkpoint"]["node_name"] == "security_reviewer"
    assert rec_data["latest_checkpoint"]["step_number"] == 6

    # 3. Test POST /tasks/recovery/scan
    scan_resp = await client.post("/api/v1/tasks/recovery/scan", headers=auth_headers)
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["scanned_tasks_count"] >= 1
    found = any(item["task_id"] == str(task.id) for item in scan_data["interrupted_tasks"])
    assert found is True

    # 4. Test lease conflict: inject active unexpired lease held by another worker
    task.recovery_lease_owner = "competing-worker-888"
    task.recovery_lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    await db_session.commit()

    resume_conflict = await client.post(f"/api/v1/tasks/{task.id}/resume", json={"force": False}, headers=auth_headers)
    assert resume_conflict.status_code == 400
    assert "Active recovery lease" in resume_conflict.text

    # 5. Clear lease and resume successfully
    task.recovery_lease_owner = None
    task.recovery_lease_expires_at = None
    await db_session.commit()

    resume_resp = await client.post(f"/api/v1/tasks/{task.id}/resume", json={"force": False}, headers=auth_headers)
    assert resume_resp.status_code == 200
    res_data = resume_resp.json()
    assert res_data["task_id"] == str(task.id)
    assert res_data["status"] == "WAITING_APPROVAL"
    assert res_data["resumed_from_node"] == "security_reviewer"
