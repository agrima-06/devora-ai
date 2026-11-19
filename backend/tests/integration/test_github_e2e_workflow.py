"""End-to-end integration test for Phase 8 GitHub-Native Autonomous Engineering Workflow."""
import tempfile
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.git_branch import GitBranch
from app.models.github_pull_request import GitHubPullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.services.sandbox_service import LocalIsolatedRunner, SandboxService
from app.services.workflow_service import WorkflowService


@pytest.mark.asyncio
async def test_full_github_native_workflow_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
):
    """Verify end-to-end: Branch creation -> Execution -> Approval -> Git Commit -> Push -> PR Creation."""
    # 1. Create Project
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "E2E GitHub Project", "slug": f"e2e-gh-{uuid.uuid4().hex[:6]}"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 2. Setup local sample git repo on disk
    repo_dir = Path(tempfile.mkdtemp(prefix="devora_e2e_repo_"))
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "math_utils.py").write_text("def divide(a, b):\n    return a / b\n")
    (repo_dir / "tests").mkdir()
    (repo_dir / "tests" / "test_math.py").write_text(
        "from src.math_utils import divide\ndef test_divide():\n    assert divide(10, 2) == 5\n"
    )

    import subprocess
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test Engineer"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "engineer@test.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    # 3. Register Repository
    repo_resp = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": proj_id,
            "name": "math-service",
            "full_name": "devora-org/math-service",
            "clone_url": f"file://{repo_dir}",
            "default_branch": "main",
            "language": "python",
        },
        headers=auth_headers,
    )
    assert repo_resp.status_code == 201
    repo_id = repo_resp.json()["id"]

    # Index repository
    await client.post(f"/api/v1/repositories/{repo_id}/index", headers=auth_headers)

    # 4. Create Task
    task_resp = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "repository_id": repo_id,
            "title": "Fix division by zero when denominator is zero",
            "prompt": "Raise ValueError('Denominator cannot be zero') in divide function",
            "task_type": "bug_fix",
            "target_branch": "main",
        },
        headers=auth_headers,
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    # 5. Start workflow with local runner
    wf_service = WorkflowService(sandbox=SandboxService(runner=LocalIsolatedRunner()))
    # Retrieve user from db
    from app.models.user import User
    from app.core.security import decode_access_token
    token = auth_headers["Authorization"].split(" ")[1]
    token_sub = decode_access_token(token)["sub"]
    u_res = await db_session.execute(select(User).where(User.id == uuid.UUID(token_sub)))
    user = u_res.scalar_one()

    start_res = await wf_service.start_task_workflow(task_id=uuid.UUID(task_id), user=user, db=db_session)
    assert start_res["status"] == "WAITING_APPROVAL"

    # 6. Verify Task Branch was allocated and recorded
    t_res = await db_session.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
    task_entity = t_res.scalar_one()
    assert task_entity.task_branch is not None
    assert task_entity.task_branch.startswith("devora/bugfix-")

    b_res = await db_session.execute(select(GitBranch).where(GitBranch.task_id == task_entity.id))
    branch_entity = b_res.scalar_one_or_none()
    assert branch_entity is not None
    assert branch_entity.branch_name == task_entity.task_branch

    # 7. Submit Developer Approval -> Triggers Git commit, push, and PR creation
    appr_res = await wf_service.submit_approval_action(
        task_id=task_entity.id,
        user=user,
        action="APPROVE",
        notes="Verified fix handles zero division cleanly. Approved for PR.",
        db=db_session,
    )
    assert appr_res["status"] == "COMPLETED"
    assert "pull_request" in appr_res
    pr_data = appr_res["pull_request"]
    assert pr_data is not None
    assert pr_data["pr_number"] >= 1
    assert "https://github.com/" in pr_data["html_url"]

    # 8. Verify Task entity has pull_request_url and commit_sha
    await db_session.refresh(task_entity)
    assert task_entity.status == "COMPLETED"
    assert task_entity.commit_sha is not None
    assert task_entity.pull_request_url == pr_data["html_url"]

    # 9. Verify GitHubPullRequest entity in DB
    pr_stmt = select(GitHubPullRequest).where(GitHubPullRequest.task_id == task_entity.id)
    pr_res = await db_session.execute(pr_stmt)
    gh_pr = pr_res.scalar_one_or_none()
    assert gh_pr is not None
    assert gh_pr.pr_number == pr_data["pr_number"]
    assert gh_pr.head_branch == task_entity.task_branch
    assert gh_pr.base_branch == "main"
    assert gh_pr.state == "open"
