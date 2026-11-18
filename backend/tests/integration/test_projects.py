"""Integration tests for project endpoints and tenant isolation."""
import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_and_get_project(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "Backend Microservices",
        "description": "Core payment and ledger backend",
        "slug": "backend-microservices",
    }
    response = await client.post("/api/v1/projects", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Backend Microservices"
    assert data["slug"] == "backend-microservices"
    project_id = data["id"]

    # Retrieve by ID
    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id


@pytest.mark.asyncio
async def test_duplicate_slug_conflict(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "Unique Slug Project",
        "slug": "unique-slug",
    }
    resp1 = await client.post("/api/v1/projects", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/projects", json=payload, headers=auth_headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "RESOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_project_tenant_isolation(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    # Create User 1 Project
    payload = {"name": "User 1 Confidential Project", "slug": "user-1-confidential"}
    resp1 = await client.post("/api/v1/projects", json=payload, headers=auth_headers)
    assert resp1.status_code == 201
    project_id = resp1.json()["id"]

    # Create User 2
    user2 = User(
        email="user2@devora.ai",
        full_name="User Two",
        hashed_password=get_password_hash("Pass123!"),
        is_active=True,
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    user2_token = create_access_token(subject=str(user2.id))
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # User 2 attempts to fetch User 1's project -> Must be 404 (or 403, treated as not found for tenant secrecy)
    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=user2_headers)
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_and_delete_project(client: AsyncClient, auth_headers: dict):
    # Create project
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Initial Name", "slug": "temp-project"},
        headers=auth_headers,
    )
    project_id = create_resp.json()["id"]

    # Update project
    update_resp = await client.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Name", "description": "New description"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Name"

    # Delete project
    del_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Verify deleted
    verify_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert verify_resp.status_code == 404
