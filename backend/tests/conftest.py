"""Pytest global configuration and fixtures."""
import asyncio
import os
from typing import AsyncGenerator
import pytest

# Ensure local isolated runner is the test default if not explicitly specified
os.environ.setdefault("DEVORA_SANDBOX_RUNNER", "local")
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.repository import Repository

# In-memory SQLite engine for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean in-memory database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX async test client with database dependency override."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a verified test user."""
    user = User(
        email="developer@devora.ai",
        full_name="Devora Test Engineer",
        hashed_password=get_password_hash("ValidPass123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Provide authorization headers with a valid JWT for test_user."""
    token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def test_project(db_session: AsyncSession, test_user: User) -> Project:
    """Create a test project owned by test_user."""
    project = Project(
        name="Test Project",
        description="A test project",
        slug="test-project",
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture(scope="function")
async def test_repository(db_session: AsyncSession, test_user: User, test_project: Project) -> Repository:
    """Create an indexed test repository owned by test_user."""
    repo = Repository(
        project_id=test_project.id,
        user_id=test_user.id,
        name="test-repo",
        full_name="devora/test-repo",
        clone_url="https://github.com/devora/test-repo.git",
        default_branch="main",
        language="Python",
        meta_info={},
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)
    return repo
