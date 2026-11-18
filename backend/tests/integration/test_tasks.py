"""Integration tests for task endpoints and lifecycle."""
import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def sample_repo_context(client: AsyncClient, auth_headers: dict) -> dict:
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Task Test Project", "slug": f"task-proj-{uuid.uuid4().hex[:6]}"},
        headers=auth_headers,
    )
    project_id = proj_resp.json()["id"]

    repo_resp = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "ledger-api",
            "full_name": "org/ledger-api",
            "clone_url": "https://github.com/org/ledger-api.git",
        },
        headers=auth_headers,
    )
    repo_id = repo_resp.json()["id"]
    return {"project_id": project_id, "repository_id": repo_id}


@pytest.mark.asyncio
async def test_create_and_get_task(client: AsyncClient, auth_headers: dict, sample_repo_context: dict):
    payload = {
        "project_id": sample_repo_context["project_id"],
        "repository_id": sample_repo_context["repository_id"],
        "title": "Fix division by zero in invoice calculation",
        "prompt": "When invoice items are empty, calculate_discount throws ZeroDivisionError.",
        "error_traceback": "Traceback...\nZeroDivisionError: division by zero",
        "task_type": "bug_fix",
        "target_branch": "main",
    }
    response = await client.post("/api/v1/tasks", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["status"] == "PENDING"
    assert data["iterations_count"] == 0
    task_id = data["id"]

    # Get task detail
    get_resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id
    assert "plans" in get_resp.json()


@pytest.mark.asyncio
async def test_list_tasks_with_filter(client: AsyncClient, auth_headers: dict, sample_repo_context: dict):
    # Create 2 tasks
    for i in range(2):
        await client.post(
            "/api/v1/tasks",
            json={
                "project_id": sample_repo_context["project_id"],
                "repository_id": sample_repo_context["repository_id"],
                "title": f"Task #{i}",
                "prompt": f"Prompt #{i}",
            },
            headers=auth_headers,
        )

    # List all
    list_resp = await client.get("/api/v1/tasks", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 2

    # Filter by status
    status_resp = await client.get("/api/v1/tasks?status=PENDING", headers=auth_headers)
    assert status_resp.status_code == 200
    assert all(t["status"] == "PENDING" for t in status_resp.json())


@pytest.mark.asyncio
async def test_cancel_task(client: AsyncClient, auth_headers: dict, sample_repo_context: dict):
    create_resp = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": sample_repo_context["project_id"],
            "repository_id": sample_repo_context["repository_id"],
            "title": "Task to cancel",
            "prompt": "Prompt to cancel",
        },
        headers=auth_headers,
    )
    task_id = create_resp.json()["id"]

    cancel_resp = await client.post(f"/api/v1/tasks/{task_id}/cancel", headers=auth_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Cannot cancel already cancelled task -> 400
    cancel_again = await client.post(f"/api/v1/tasks/{task_id}/cancel", headers=auth_headers)
    assert cancel_again.status_code == 400
    assert cancel_again.json()["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_task_tenant_isolation(
    client: AsyncClient, auth_headers: dict, sample_repo_context: dict, db_session: AsyncSession
):
    create_resp = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": sample_repo_context["project_id"],
            "repository_id": sample_repo_context["repository_id"],
            "title": "Confidential Task",
            "prompt": "Confidential Prompt",
        },
        headers=auth_headers,
    )
    task_id = create_resp.json()["id"]

    # User 2
    user2 = User(
        email="unauth_task_user@devora.ai",
        full_name="Unauth Task User",
        hashed_password=get_password_hash("Pass123!"),
        is_active=True,
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    user2_token = create_access_token(subject=str(user2.id))
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # User 2 attempts to fetch User 1 task -> 404
    resp = await client.get(f"/api/v1/tasks/{task_id}", headers=user2_headers)
    assert resp.status_code == 404
