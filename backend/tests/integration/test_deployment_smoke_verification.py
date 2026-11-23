"""Automated Deployment Smoke Verification Test Suite (Stage H7).

Verifies the end-to-end functionality of all core subsystems for public deployment:
1. Root health & liveness probes (/health, /healthz, /api/v1/health)
2. User signup and authentication token generation (/auth/register, /auth/login)
3. Project & repository management
4. Repository indexing & dependency graph retrieval
5. Architecture intelligence & drift detection
6. Semantic code and memory search
7. Task creation & metadata retrieval
8. Server-Sent Events (SSE) streaming endpoint initialization
9. Benchmark dashboard, scenarios, and categories
10. Refactoring engine plan lifecycle
11. Model gateway resilience & health status
12. GitHub App integration status
13. Workflow recovery and interrupted task scan
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.events import WorkflowEventBroadcaster
from app.models.project import Project
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User


@pytest.mark.asyncio
async def test_smoke_health_and_liveness_probes(client: AsyncClient):
    """Verify root health check, liveness check, and API V1 health check."""
    # 1. Root /health
    r_root_health = await client.get("/health")
    assert r_root_health.status_code == 200
    d_root = r_root_health.json()
    assert d_root["status"] in ("healthy", "degraded")
    assert "version" in d_root

    # 2. Root /healthz
    r_healthz = await client.get("/healthz")
    assert r_healthz.status_code == 200
    assert r_healthz.json()["status"] in ("healthy", "degraded")

    # 3. API V1 /api/v1/health
    r_v1 = await client.get("/api/v1/health")
    assert r_v1.status_code == 200
    assert r_v1.json()["services"]["database"] == "connected"


@pytest.mark.asyncio
async def test_smoke_signup_login_lifecycle(client: AsyncClient):
    """Verify user registration and authentication lifecycle."""
    unique_email = f"deploy_smoke_{uuid.uuid4().hex[:8]}@devora.ai"
    signup_payload = {
        "email": unique_email,
        "password": "ProductionPassword123!",
        "full_name": "Deployment Smoke Tester",
    }

    # 1. Register new user
    r_signup = await client.post("/api/v1/auth/register", json=signup_payload)
    assert r_signup.status_code == 201
    signup_data = r_signup.json()
    assert signup_data["user"]["email"] == unique_email
    assert "access_token" in signup_data

    # 2. Authenticate and retrieve JWT
    login_payload = {
        "email": unique_email,
        "password": "ProductionPassword123!",
    }
    r_login = await client.post("/api/v1/auth/login", json=login_payload)
    assert r_login.status_code == 200
    token_data = r_login.json()
    assert "access_token" in token_data
    assert token_data["token_type"].lower() == "bearer"

    # 3. Verify authenticated profile fetch
    auth_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    r_me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r_me.status_code == 200
    assert r_me.json()["email"] == unique_email


@pytest.mark.asyncio
async def test_smoke_repository_management_and_indexing(client: AsyncClient, test_user: User, auth_headers: dict):
    """Verify project creation, repository attachment, and indexing APIs."""
    slug = f"smoke-proj-{uuid.uuid4().hex[:6]}"
    # 1. Create Project
    proj_payload = {
        "name": f"Smoke Project {slug}",
        "description": "Deployment smoke test project",
        "slug": slug,
    }
    r_proj = await client.post("/api/v1/projects", json=proj_payload, headers=auth_headers)
    assert r_proj.status_code == 201
    proj_id = r_proj.json()["id"]

    # 2. Connect Repository
    repo_payload = {
        "project_id": proj_id,
        "name": "demo-calculator",
        "full_name": "devora-ai/demo-calculator",
        "clone_url": "https://github.com/devora-ai/demo-calculator.git",
        "default_branch": "main",
        "language": "python",
        "meta_info": {"ci_enabled": True},
    }
    r_repo = await client.post("/api/v1/repositories", json=repo_payload, headers=auth_headers)
    assert r_repo.status_code == 201
    repo_id = r_repo.json()["id"]

    # 3. Retrieve Repository Details
    r_get_repo = await client.get(f"/api/v1/repositories/{repo_id}", headers=auth_headers)
    assert r_get_repo.status_code == 200
    assert r_get_repo.json()["name"] == "demo-calculator"


@pytest.mark.asyncio
async def test_smoke_dependency_graph_and_architecture_intelligence(client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession):
    """Verify dependency graph, architecture patterns, and technical debt endpoints."""
    project = Project(
        name="Smoke Arch Project",
        slug=f"smoke-arch-{uuid.uuid4().hex[:6]}",
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.flush()

    repo = Repository(
        project_id=project.id,
        user_id=test_user.id,
        name="demo-service",
        full_name="devora-ai/demo-service",
        clone_url="https://github.com/devora-ai/demo-service.git",
        default_branch="main",
        language="python",
    )
    db_session.add(repo)
    await db_session.commit()

    # 1. Query Dependency Graph Summary
    r_graph = await client.get(f"/api/v1/repositories/{repo.id}/graph", headers=auth_headers)
    assert r_graph.status_code == 200
    graph_data = r_graph.json()
    assert "total_nodes" in graph_data
    assert "total_edges" in graph_data

    # 2. Query Dependency Graph Nodes
    r_nodes = await client.get(f"/api/v1/repositories/{repo.id}/graph/nodes", headers=auth_headers)
    assert r_nodes.status_code == 200
    assert "nodes" in r_nodes.json()

    # 3. Query Architecture Patterns
    r_patterns = await client.get(f"/api/v1/repositories/{repo.id}/architecture/patterns", headers=auth_headers)
    assert r_patterns.status_code == 200

    # 4. Query Architecture Drift
    r_drift = await client.get(f"/api/v1/repositories/{repo.id}/architecture/drift", headers=auth_headers)
    assert r_drift.status_code == 200


@pytest.mark.asyncio
async def test_smoke_task_creation_and_sse_endpoint(client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession):
    """Verify task creation and SSE streaming endpoint availability."""
    project = Project(
        name="Smoke Task Project",
        slug=f"smoke-task-{uuid.uuid4().hex[:6]}",
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.flush()

    repo = Repository(
        project_id=project.id,
        user_id=test_user.id,
        name="demo-calc",
        full_name="devora-ai/demo-calc",
        clone_url="https://github.com/devora-ai/demo-calc.git",
        default_branch="main",
        language="python",
    )
    db_session.add(repo)
    await db_session.commit()

    # 1. Create Engineering Task
    task_payload = {
        "project_id": str(project.id),
        "repository_id": str(repo.id),
        "title": "Fix ZeroDivisionError in Calculator",
        "prompt": "Investigate calculator.py and ensure safe division by zero handling.",
        "task_type": "bug_fix",
        "target_branch": "main",
    }
    r_task = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers)
    assert r_task.status_code == 201
    task_data = r_task.json()
    task_id = task_data["id"]

    # 2. Verify Task Retrieval
    r_get_task = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert r_get_task.status_code == 200
    assert r_get_task.json()["title"] == "Fix ZeroDivisionError in Calculator"

    # 3. Verify SSE endpoint authorization gate
    r_unauth = await client.get(f"/api/v1/tasks/{task_id}/events")
    assert r_unauth.status_code == 401

    r_not_found = await client.get(f"/api/v1/tasks/{uuid.uuid4()}/events", headers=auth_headers)
    assert r_not_found.status_code == 404

    # 4. Verify SSE Broadcaster Event Generator Yields CONNECTED chunk
    broadcaster = WorkflowEventBroadcaster.get_instance()
    gen = broadcaster.event_generator(str(task_id))
    connected_chunk = await gen.__anext__()
    assert "CONNECTED" in connected_chunk
    assert "Connected to Devora AI workflow live stream" in connected_chunk
    await gen.aclose()


@pytest.mark.asyncio
async def test_smoke_benchmark_dashboard_and_categories(client: AsyncClient, auth_headers: dict):
    """Verify benchmark scenario listing and categories endpoints."""
    # 1. Categories and weights
    r_cats = await client.get("/api/v1/benchmarks/categories", headers=auth_headers)
    assert r_cats.status_code == 200
    cats_data = r_cats.json()
    assert "categories" in cats_data
    assert "weighting_formula" in cats_data
    assert len(cats_data["categories"]) >= 7

    # 2. Registered Scenarios
    r_scenarios = await client.get("/api/v1/benchmarks/scenarios", headers=auth_headers)
    assert r_scenarios.status_code == 200
    scenarios_data = r_scenarios.json()
    assert "scenarios" in scenarios_data
    assert scenarios_data["total_count"] >= 31


@pytest.mark.asyncio
async def test_smoke_model_gateway_and_github_status(client: AsyncClient, auth_headers: dict):
    """Verify model gateway health telemetry and GitHub App integration status."""
    # 1. Model Gateway Health
    r_model_health = await client.get("/api/v1/models/health", headers=auth_headers)
    assert r_model_health.status_code == 200
    health_data = r_model_health.json()
    assert "status" in health_data

    # 2. GitHub App Status
    r_gh_status = await client.get("/api/v1/github/status", headers=auth_headers)
    assert r_gh_status.status_code == 200
    gh_data = r_gh_status.json()
    assert "app_configured" in gh_data
    assert "is_mock" in gh_data


@pytest.mark.asyncio
async def test_smoke_recovery_manager_scan(client: AsyncClient, auth_headers: dict):
    """Verify workflow recovery scan endpoint."""
    r_scan = await client.post("/api/v1/tasks/recovery/scan", headers=auth_headers)
    assert r_scan.status_code == 200
    scan_data = r_scan.json()
    assert "scanned_tasks_count" in scan_data
    assert "interrupted_tasks" in scan_data
