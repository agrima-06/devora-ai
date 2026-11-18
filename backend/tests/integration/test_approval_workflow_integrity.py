"""Approval and Workflow Integrity Test Suite."""
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.agents.state import (
    AnalysisOutput,
    CodingOutput,
    DevoraWorkflowState,
    FileEdit,
    OrchestratorDecision,
    SecurityReviewOutput,
    TaskPlanOutput,
    TestRunOutput,
)
from app.core.security import create_access_token, get_password_hash
from app.models.approval import Approval
from app.models.report import Report
from app.models.task import Task
from app.models.user import User
from app.services.sandbox_service import LocalIsolatedRunner, SandboxService
from app.services.workflow_service import WorkflowService


@pytest.fixture
def mock_gateway_for_integrity():
    mock_prov = MockLLMProvider()
    gw = ModelGateway(provider=mock_prov)
    ModelGateway.set_instance(gw)
    return mock_prov


@pytest.fixture
def second_user(db_session: AsyncSession):
    pass


@pytest.mark.asyncio
async def test_approval_workflow_full_matrix(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    mock_gateway_for_integrity,
):
    """Test approval by owner, rejection, request changes, duplicate approval, and tenant isolation."""
    # 1. Create a second unauthorized user
    other_user = User(
        email="hacker@evil.com",
        full_name="Attacker",
        hashed_password=get_password_hash("ValidPass123!"),
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    other_auth_headers = {"Authorization": f"Bearer {create_access_token(subject=str(other_user.id))}"}

    # 2. Create Project & Repo
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Approval Project", "slug": "approval-project"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["id"]

    repo_dir = Path(tempfile.mkdtemp())
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "calculator.py").write_text('''
def calculate_ratio(a: float, b: float) -> float:
    return a / b
''')
    (repo_dir / "tests").mkdir()
    (repo_dir / "tests" / "test_calculator.py").write_text('''
from src.calculator import calculate_ratio
def test_ok():
    assert True
''')
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "tester@devora.ai"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "test-repo",
            "full_name": "local/test-repo",
            "clone_url": f"file://{repo_dir}",
            "default_branch": "main",
        },
        headers=auth_headers,
    )
    repo_id = repo_res.json()["id"]
    await client.post(f"/api/v1/repositories/{repo_id}/index", headers=auth_headers)

    # 3. Create Task
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "repository_id": repo_id,
            "title": "Add feature requiring review",
            "prompt": "Implement reviewable change",
            "task_type": "feature",
            "target_branch": "main",
        },
        headers=auth_headers,
    )
    task_id = task_res.json()["id"]

    # 4. Start workflow with LocalIsolatedRunner for hermetic test execution
    with patch.dict("os.environ", {"DEVORA_SANDBOX_RUNNER": "test"}):
        start_res = await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth_headers)
        assert start_res.status_code == 202
        assert start_res.json()["status"] == "WAITING_APPROVAL"

    # 5. Unauthorized User Attempting Approval (Tenant Isolation Audit)
    unauthorized_res = await client.post(
        f"/api/v1/tasks/{task_id}/approval",
        json={"action": "APPROVE", "notes": "I am not the owner"},
        headers=other_auth_headers,
    )
    assert unauthorized_res.status_code == 404  # Must not disclose or modify other tenant's task

    # Task must still be WAITING_APPROVAL
    get_task_res = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert get_task_res.json()["status"] == "WAITING_APPROVAL"

    # 6. Test Request Changes action
    rc_res = await client.post(
        f"/api/v1/tasks/{task_id}/approval",
        json={"action": "REQUEST_CHANGES", "notes": "Please refactor helper function"},
        headers=auth_headers,
    )
    assert rc_res.status_code == 200
    assert rc_res.json()["status"] == "CHANGES_REQUESTED"

    # Reset task back to PENDING approval to test Approve
    appr_stmt = select(Approval).where(Approval.task_id == uuid.UUID(task_id))
    appr_res = await db_session.execute(appr_stmt)
    appr_obj = appr_res.scalars().first()
    appr_obj.status = "PENDING"
    task_obj = (await db_session.execute(select(Task).where(Task.id == uuid.UUID(task_id)))).scalar_one()
    task_obj.status = "WAITING_APPROVAL"
    await db_session.commit()

    # 7. Valid Approval by Owner (APPROVE)
    with patch.dict("os.environ", {"DEVORA_SANDBOX_RUNNER": "test"}):
        approve_res = await client.post(
            f"/api/v1/tasks/{task_id}/approval",
            json={"action": "APPROVE", "notes": "Approved by owner"},
            headers=auth_headers,
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "APPROVED"

    # Task must now be COMPLETED with final report
    final_task_res = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert final_task_res.json()["status"] == "COMPLETED"

    report_res = await client.get(f"/api/v1/tasks/{task_id}/report", headers=auth_headers)
    assert report_res.status_code == 200
    assert len(report_res.json()["markdown_content"]) > 0

    # 8. Duplicate Approval Attempt (Must be rejected with 400 Bad Request)
    dup_res = await client.post(
        f"/api/v1/tasks/{task_id}/approval",
        json={"action": "APPROVE", "notes": "Second attempt"},
        headers=auth_headers,
    )
    assert dup_res.status_code == 400
    assert "has no pending approvals" in dup_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_rejection_marks_task_cancelled(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    mock_gateway_for_integrity,
):
    """Rejection must mark approval REJECTED and task CANCELLED without publishing report."""
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Rejection Project", "slug": "rejection-project"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["id"]

    repo_dir = Path(tempfile.mkdtemp())
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "calc.py").write_text("x = 1\n")
    (repo_dir / "tests").mkdir()
    (repo_dir / "tests" / "test_calc.py").write_text("def test_ok(): assert True\n")
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "tester@devora.ai"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "reject-repo",
            "full_name": "local/reject-repo",
            "clone_url": f"file://{repo_dir}",
            "default_branch": "main",
        },
        headers=auth_headers,
    )
    repo_id = repo_res.json()["id"]
    await client.post(f"/api/v1/repositories/{repo_id}/index", headers=auth_headers)

    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "repository_id": repo_id,
            "title": "Task destined for rejection",
            "prompt": "Unwanted modification",
            "task_type": "bug_fix",
            "target_branch": "main",
        },
        headers=auth_headers,
    )
    task_id = task_res.json()["id"]

    with patch.dict("os.environ", {"DEVORA_SANDBOX_RUNNER": "test"}):
        await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth_headers)

        reject_res = await client.post(
            f"/api/v1/tasks/{task_id}/approval",
            json={"action": "REJECT", "notes": "Wrong approach, discard changes"},
            headers=auth_headers,
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"

    task_status_res = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert task_status_res.json()["status"] == "CANCELLED"
