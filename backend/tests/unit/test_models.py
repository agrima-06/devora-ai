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
