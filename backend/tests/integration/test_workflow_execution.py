"""End-to-end integration tests for Multi-Agent Workflow Execution, LangGraph pipeline, and Human Approval."""
import subprocess
import tempfile
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.core.security import create_access_token, get_password_hash
from app.models.project import Project
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User


@pytest.fixture
def test_git_repo_with_bug():
    """Create a real git repository fixture containing code with a bug and test suite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)

        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "calculator.py").write_text('''"""Calculator module with bug."""

def calculate_ratio(a: float, b: float) -> float:
    """Calculate ratio between two numbers."""
    return a / b
''')

        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calculator.py").write_text('''from src.calculator import calculate_ratio

def test_calculate_ratio():
    assert calculate_ratio(10, 2) == 5.0
''')

        (repo_dir / "requirements.txt").write_text("pytest\n")
        (repo_dir / "README.md").write_text("# Test Repo\n")

        subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "config", "user.email", "tester@devora.ai"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "commit", "-m", "Initial bug commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

        yield str(repo_dir)


@pytest.mark.asyncio
async def test_end_to_end_bug_fix_workflow_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    test_git_repo_with_bug: str,
):
    # Setup deterministic mock LLM provider for tests
    mock_prov = MockLLMProvider()
    ModelGateway.set_instance(ModelGateway(provider=mock_prov))

    # 1. Create Project
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "E2E Workflow Project", "slug": "e2e-workflow-project"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Connect Repository
    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "calc-service",
            "full_name": "local/calc-service",
            "clone_url": f"file://{test_git_repo_with_bug}",
            "default_branch": "main",
        },
        headers=auth_headers,
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]

    # 3. Index Repository
    idx_res = await client.post(f"/api/v1/repositories/{repo_id}/index", headers=auth_headers)
    assert idx_res.status_code == 202

    # 4. Create Bug-Fix Task
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "repository_id": repo_id,
            "title": "Fix ZeroDivisionError in calculate_ratio",
            "prompt": "When denominator is zero, function should return 0.0 instead of crashing.",
            "error_traceback": "ZeroDivisionError: float division by zero in calculate_ratio",
            "task_type": "bug_fix",
            "target_branch": "main",
        },
        headers=auth_headers,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    # 5. Start LangGraph Multi-Agent Workflow
    start_res = await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth_headers)
    assert start_res.status_code == 202
    assert start_res.json()["status"] in ("WAITING_APPROVAL", "COMPLETED")

    # 6. Verify Task Reached WAITING_APPROVAL
    get_task_res = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert get_task_res.status_code == 200
    task_data = get_task_res.json()
    assert task_data["status"] == "WAITING_APPROVAL"
    assert len(task_data["plans"]) >= 1

    # 7. Check Agent Execution History
    runs_res = await client.get(f"/api/v1/tasks/{task_id}/runs", headers=auth_headers)
    assert runs_res.status_code == 200
    runs = runs_res.json()
    agent_names = [r["agent_name"] for r in runs]
    assert "orchestrator" in agent_names
    assert "codebase_analyst" in agent_names
    assert "bug_investigator" in agent_names
    assert "planner" in agent_names
    assert "coder" in agent_names
    assert "tester" in agent_names
    assert "code_reviewer" in agent_names
    assert "security_reviewer" in agent_names

    # 8. Check Proposed File Diff
    diff_res = await client.get(f"/api/v1/tasks/{task_id}/diff", headers=auth_headers)
    assert diff_res.status_code == 200
    diffs = diff_res.json()
    assert len(diffs) >= 1
    assert "diff" in diffs[0]

    # 9. Check Test Runs
    tests_res = await client.get(f"/api/v1/tasks/{task_id}/tests", headers=auth_headers)
    assert tests_res.status_code == 200
    test_runs = tests_res.json()
    assert len(test_runs) >= 1
    assert test_runs[0]["passed"] is True

    # 10. Submit Human Approval (APPROVE)
    appr_res = await client.post(
        f"/api/v1/tasks/{task_id}/approval",
        json={"action": "APPROVE", "notes": "LGTM, verified tests pass"},
        headers=auth_headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # 11. Verify Task Completed and Final Engineering Report Exists
    final_task_res = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert final_task_res.json()["status"] == "COMPLETED"

    report_res = await client.get(f"/api/v1/tasks/{task_id}/report", headers=auth_headers)
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["title"] is not None
    assert len(report_data["markdown_content"]) > 0


@pytest.mark.asyncio
async def test_end_to_end_exploration_workflow(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    test_git_repo_with_bug: str,
):
    """Exploration tasks must run Orchestrator -> Codebase Analyst -> Reporter -> COMPLETED without modifying files."""
    # 1. Create Project & Repo
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Exploration Project", "slug": "exploration-project"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["id"]

    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "calc-service-exp",
            "full_name": "local/calc-service-exp",
            "clone_url": f"file://{test_git_repo_with_bug}",
        },
        headers=auth_headers,
    )
    repo_id = repo_res.json()["id"]
    await client.post(f"/api/v1/repositories/{repo_id}/index", headers=auth_headers)

    # 2. Create Exploration Task
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "repository_id": repo_id,
            "title": "Explain calculator architecture",
            "prompt": "Explain the architecture of calculator.py without making changes.",
            "task_type": "exploration",
        },
        headers=auth_headers,
    )
    task_id = task_res.json()["id"]

    # 3. Start Workflow
    start_res = await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth_headers)
    assert start_res.status_code == 202

    # 4. Verify completed without diffs
    diff_res = await client.get(f"/api/v1/tasks/{task_id}/diff", headers=auth_headers)
    assert diff_res.status_code == 200
    assert len(diff_res.json()) == 0  # No code diffs created!


@pytest.mark.asyncio
async def test_workflow_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """User B must not be able to start, view, or approve User A's tasks."""
    other_user = User(
        email="unauthorized@devora.ai",
        full_name="Unauthorized User",
        hashed_password=get_password_hash("ValidPass123!"),
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.flush()

    other_token = create_access_token(subject=str(other_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # User A creates a project & repo & task
    proj = Project(name="Private Proj", slug="private-proj", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="private-repo",
        full_name="org/private-repo",
        clone_url="https://github.com/org/private-repo",
    )
    db_session.add(repo)
    await db_session.flush()

    task = Task(
        project_id=proj.id,
        repository_id=repo.id,
        created_by=test_user.id,
        title="Secret Task",
        prompt="Secret work",
    )
    db_session.add(task)
    await db_session.flush()

    # User B tries to start task
    start_res = await client.post(f"/api/v1/tasks/{task.id}/start", headers=other_headers)
    assert start_res.status_code == 404

    # User B tries to view diff
    diff_res = await client.get(f"/api/v1/tasks/{task.id}/diff", headers=other_headers)
    assert diff_res.status_code == 404

    # User B tries to approve
    appr_res = await client.post(
        f"/api/v1/tasks/{task.id}/approval",
        json={"action": "APPROVE"},
        headers=other_headers,
    )
    assert appr_res.status_code == 404
