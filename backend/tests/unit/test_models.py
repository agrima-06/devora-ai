"""Unit tests for SQLAlchemy models structure and instantiation."""
import uuid
import pytest
from app.models.user import User
from app.models.project import Project
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_plan import TaskPlan
from app.models.test_run import TestRun
from app.models.report import Report
from app.models.github_installation import GitHubInstallation
from app.models.github_pull_request import GitHubPullRequest
from app.models.git_branch import GitBranch
from app.models.flaky_test_record import FlakyTestRecord
from sqlalchemy.ext.asyncio import AsyncSession


def test_user_model_instantiation():
    user = User(
        email="test@devora.ai",
        full_name="Tester",
        hashed_password="hash",
        is_active=True,
    )
    assert user.email == "test@devora.ai"
    assert user.full_name == "Tester"
    assert user.is_active is True


def test_project_model_instantiation():
    owner_id = uuid.uuid4()
    project = Project(
        owner_id=owner_id,
        name="Platform Core",
        slug="platform-core",
        description="Main workspace",
    )
    assert project.name == "Platform Core"
    assert project.slug == "platform-core"
    assert project.owner_id == owner_id


def test_task_model_instantiation():
    task = Task(
        project_id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        title="Fix NullPointerException",
        prompt="Investigate traceback in auth service",
        task_type="bug_fix",
        status="PENDING",
        iterations_count=0,
        target_branch="main",
    )
    assert task.title == "Fix NullPointerException"
    assert task.task_type == "bug_fix"
    assert task.status == "PENDING"
    assert task.iterations_count == 0
    assert task.target_branch == "main"


@pytest.mark.asyncio
async def test_model_defaults_on_db_persist(db_session: AsyncSession):
    # Verify that database defaults are properly populated upon insert
    user = User(
        email="defaults_test@devora.ai",
        full_name="Defaults Tester",
        hashed_password="hashed_secret",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


def test_github_native_models_instantiation():
    """Verify Phase 8 GitHubInstallation, GitHubPullRequest, and GitBranch instantiations."""
    user_id = uuid.uuid4()
    inst = GitHubInstallation(
        user_id=user_id,
        installation_id=12345678,
        account_login="devora-org",
        account_type="Organization",
        account_avatar_url="https://avatars.githubusercontent.com/u/123456",
        repository_selection="selected",
        permissions={"contents": "write", "pull_requests": "write"},
        is_active=True,
    )
    assert inst.installation_id == 12345678
    assert inst.account_login == "devora-org"
    assert inst.permissions["contents"] == "write"

    repo_id = uuid.uuid4()
    task_id = uuid.uuid4()
    branch = GitBranch(
        task_id=task_id,
        repository_id=repo_id,
        branch_name="devora/bugfix-4a2b1c",
        base_branch="main",
        commit_sha="a1b2c3d4e5",
        is_pushed=True,
    )
    assert branch.branch_name == "devora/bugfix-4a2b1c"
    assert branch.is_pushed is True

    pr = GitHubPullRequest(
        task_id=task_id,
        repository_id=repo_id,
        pr_number=42,
        title="[Devora] Fix ZeroDivisionError in invoice calculator",
        body="## Summary\nFixed zero division with defensive guard.",
        html_url="https://github.com/devora-org/billing/pull/42",
        head_branch="devora/bugfix-4a2b1c",
        base_branch="main",
        state="open",
        is_merged=False,
    )
    assert pr.pr_number == 42
    assert pr.head_branch == "devora/bugfix-4a2b1c"
    assert pr.state == "open"


def test_flaky_test_record_instantiation():
    """Verify Phase 9 Stage 9.2 FlakyTestRecord model instantiation."""
    repo_id = uuid.uuid4()
    task_id = uuid.uuid4()
    rec = FlakyTestRecord(
        repository_id=repo_id,
        task_id=task_id,
        test_identifier="tests/test_auth.py::test_token_expiry",
        test_file="tests/test_auth.py",
        framework="pytest",
        language="python",
        test_command="pytest -v tests/test_auth.py::test_token_expiry",
        classification="FLAKY",
        stability_score=66.7,
        total_runs=3,
        passed_runs=2,
        failed_runs=1,
        infrastructure_error_runs=0,
        timeout_runs=0,
        execution_history={"runs": [{"run": 1, "passed": False}, {"run": 2, "passed": True}, {"run": 3, "passed": True}]},
    )
    assert rec.test_identifier == "tests/test_auth.py::test_token_expiry"
    assert rec.classification == "FLAKY"
    assert rec.stability_score == 66.7
    assert rec.passed_runs == 2
    assert rec.failed_runs == 1
