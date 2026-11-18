"""Integration tests for repository metadata endpoints and tenant isolation."""
import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def sample_project_id(client: AsyncClient, auth_headers: dict) -> str:
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "slug": f"test-project-{uuid.uuid4().hex[:6]}"},
        headers=auth_headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_and_get_repository(client: AsyncClient, auth_headers: dict, sample_project_id: str):
    payload = {
        "project_id": sample_project_id,
        "name": "payment-gateway",
        "full_name": "org/payment-gateway",
        "clone_url": "https://github.com/org/payment-gateway.git",
        "default_branch": "main",
        "language": "python",
        "meta_info": {"ci_enabled": True},
    }
    response = await client.post("/api/v1/repositories", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "payment-gateway"
    assert data["full_name"] == "org/payment-gateway"
    repo_id = data["id"]

    # Get by ID
    get_resp = await client.get(f"/api/v1/repositories/{repo_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == repo_id


@pytest.mark.asyncio
async def test_duplicate_repository_conflict(client: AsyncClient, auth_headers: dict, sample_project_id: str):
    payload = {
        "project_id": sample_project_id,
        "name": "auth-service",
        "full_name": "org/auth-service",
        "clone_url": "https://github.com/org/auth-service.git",
    }
    resp1 = await client.post("/api/v1/repositories", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/repositories", json=payload, headers=auth_headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "RESOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_repository_sync_endpoint(client: AsyncClient, auth_headers: dict, sample_project_id: str):
    create_resp = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": sample_project_id,
            "name": "sync-repo",
            "full_name": "org/sync-repo",
            "clone_url": "https://github.com/org/sync-repo.git",
        },
        headers=auth_headers,
    )
    repo_id = create_resp.json()["id"]

    sync_resp = await client.post(f"/api/v1/repositories/{repo_id}/sync", headers=auth_headers)
    assert sync_resp.status_code == 200
    assert sync_resp.json()["status"] == "SYNCED"


@pytest.mark.asyncio
async def test_repository_tenant_isolation(
    client: AsyncClient, auth_headers: dict, sample_project_id: str, db_session: AsyncSession
):
    # User 1 creates repo
    create_resp = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": sample_project_id,
            "name": "private-repo",
            "full_name": "org/private-repo",
            "clone_url": "https://github.com/org/private-repo.git",
        },
        headers=auth_headers,
    )
    repo_id = create_resp.json()["id"]

    # User 2
    user2 = User(
        email="unauth_repo_user@devora.ai",
        full_name="Unauth User",
        hashed_password=get_password_hash("Pass123!"),
        is_active=True,
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    user2_token = create_access_token(subject=str(user2.id))
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # User 2 attempts to access User 1 repo -> 404
    resp = await client.get(f"/api/v1/repositories/{repo_id}", headers=user2_headers)
    assert resp.status_code == 404
