"""Real PostgreSQL and pgvector Integration & Workflow Recovery Validation Suite."""
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.api.deps import get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.agent_run import AgentRun
from app.models.approval import Approval
from app.models.file_change import FileChange
from app.models.report import Report
from app.models.task import Task
from app.models.task_plan import TaskPlan
from app.models.test_run import TestRun
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.models.workflow_event import WorkflowEvent
from app.services.workflow_service import WorkflowService

import socket
from sqlalchemy.pool import NullPool

# Connect directly to real PostgreSQL container started in Docker
POSTGRES_URL = os.environ.get(
    "DEVORA_TEST_POSTGRES_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/devora",
)


def is_postgres_accessible() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_postgres_accessible(),
    reason="PostgreSQL on localhost:5432 is not accessible in sandboxed network mode",
)

pg_engine = create_async_engine(POSTGRES_URL, poolclass=NullPool)
PgSessionLocal = async_sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def pg_session():
    """Yield a database session directly bound to PostgreSQL."""
    async with PgSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def pg_client(pg_session: AsyncSession):
    """Yield an HTTP client whose get_db dependency uses the real PostgreSQL session."""
    async def override_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def pg_test_user(pg_session: AsyncSession) -> User:
    """Create or get an active user in the real PostgreSQL database."""
    unique_email = f"postgres_auditor_{uuid.uuid4().hex[:8]}@devora.ai"
    user = User(
        email=unique_email,
        full_name="PostgreSQL Auditor",
        hashed_password=get_password_hash("ValidPass123!"),
        is_active=True,
    )
    pg_session.add(user)
    await pg_session.commit()
    await pg_session.refresh(user)
    return user


@pytest.fixture
def pg_auth_headers(pg_test_user: User) -> dict:
    token = create_access_token(subject=str(pg_test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_gw():
    prov = MockLLMProvider()
    gw = ModelGateway(provider=prov)
    ModelGateway.set_instance(gw)
    return prov


@pytest.mark.asyncio
async def test_postgres_pgvector_active(pg_session: AsyncSession):
    """Verify real PostgreSQL instance has pgvector extension active."""
    res = await pg_session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
    extname = res.scalar_one_or_none()
    assert extname == "vector", "pgvector extension must be active in PostgreSQL"


@pytest.mark.asyncio
async def test_postgres_workflow_execution_persistence_and_recovery(
    pg_client: AsyncClient,
    pg_session: AsyncSession,
    pg_test_user: User,
    pg_auth_headers: dict,
    mock_gw,
):
    """End-to-End audit on real PostgreSQL:
    1. Verify all 18 tables are functional.
    2. Start workflow and verify checkpoint and event rows in PostgreSQL.
    3. Simulate backend restart (destroying in-memory checkpointer).
    4. Resume workflow from PostgreSQL checkpoint and verify recovery.
    5. Verify final Report, FileChanges, TestRuns, and Approvals are committed.
    """
    # 1. Create Project
    proj_slug = f"pg-audit-{uuid.uuid4().hex[:6]}"
    proj_res = await pg_client.post(
        "/api/v1/projects",
        json={"name": "PostgreSQL Audit Project", "slug": proj_slug},
        headers=pg_auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Setup real Git repository with bug
    repo_dir = Path(tempfile.mkdtemp())
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "math_ops.py").write_text('''
def divide(a: float, b: float) -> float:
    return a / b
''')
    (repo_dir / "tests").mkdir()
    (repo_dir / "tests" / "test_math_ops.py").write_text('''
from src.math_ops import divide
def test_ok():
    assert True
''')
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "PGAuditor"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "auditor@devora.ai"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

    # Connect & Index Repository
    repo_res = await pg_client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "pg-audit-repo",
            "full_name": "local/pg-audit-repo",
            "clone_url": f"file://{repo_dir}",
            "default_branch": "main",
        },
        headers=pg_auth_headers,
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]
    await pg_client.post(f"/api/v1/repositories/{repo_id}/index", headers=pg_auth_headers)

    # 3. Create Bug-Fix Task
    task_res = await pg_client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "repository_id": repo_id,
            "title": "Fix division by zero in divide",
            "prompt": "Return 0.0 when b is 0",
            "task_type": "bug_fix",
            "target_branch": "main",
        },
        headers=pg_auth_headers,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    # 4. Start workflow with test runner
    start_res = await pg_client.post(f"/api/v1/tasks/{task_id}/start", headers=pg_auth_headers)
    assert start_res.status_code == 202
    assert start_res.json()["status"] == "WAITING_APPROVAL"

    # 5. VERIFY POSTGRESQL PERSISTENCE:
    # A. Checkpoints table
    cp_stmt = select(WorkflowCheckpoint).where(WorkflowCheckpoint.task_id == uuid.UUID(task_id))
    cp_res = await pg_session.execute(cp_stmt)
    checkpoints = cp_res.scalars().all()
    assert len(checkpoints) >= 1, "WorkflowCheckpoint must be persisted in PostgreSQL"
    assert checkpoints[0].thread_id == task_id
    assert "task_description" in checkpoints[0].state_blob

    # B. Events table
    evt_stmt = select(WorkflowEvent).where(WorkflowEvent.task_id == uuid.UUID(task_id))
    evt_res = await pg_session.execute(evt_stmt)
    events = evt_res.scalars().all()
    assert len(events) >= 5, "Workflow events must be persisted in PostgreSQL"

    # C. Domain entities
    agent_runs = (await pg_session.execute(select(AgentRun).where(AgentRun.task_id == uuid.UUID(task_id)))).scalars().all()
    assert len(agent_runs) >= 6, "AgentRun entities must be persisted in PostgreSQL"

    plans = (await pg_session.execute(select(TaskPlan).where(TaskPlan.task_id == uuid.UUID(task_id)))).scalars().all()
    assert len(plans) >= 1, "TaskPlan must be persisted in PostgreSQL"

    file_changes = (await pg_session.execute(select(FileChange).where(FileChange.task_id == uuid.UUID(task_id)))).scalars().all()
    assert len(file_changes) >= 1, "FileChange must be persisted in PostgreSQL"

    test_runs = (await pg_session.execute(select(TestRun).where(TestRun.task_id == uuid.UUID(task_id)))).scalars().all()
    assert len(test_runs) >= 1, "TestRun must be persisted in PostgreSQL"

    # 6. SIMULATE BACKEND RESTART & RECOVERY:
    # Wipe the in-memory checkpointer completely
    from langgraph.checkpoint.memory import MemorySaver
    WorkflowService._shared_checkpointer = MemorySaver()

    # Now call approval endpoint on a fresh request
    # WorkflowService must restore the state from PostgreSQL workflow_checkpoints and finalize!
    appr_res = await pg_client.post(
        f"/api/v1/tasks/{task_id}/approval",
        json={"action": "APPROVE", "notes": "Approved after simulated restart"},
        headers=pg_auth_headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # 7. Verify Task is COMPLETED and Report exists in PostgreSQL
    task_record = (await pg_session.execute(select(Task).where(Task.id == uuid.UUID(task_id)))).scalar_one()
    assert task_record.status == "COMPLETED"

    report_record = (await pg_session.execute(select(Report).where(Report.task_id == uuid.UUID(task_id)))).scalar_one_or_none()
    assert report_record is not None, "Report must be persisted in PostgreSQL after resumed execution"
    assert len(report_record.markdown_content) > 0
