"""Integration tests for user registration and authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    payload = {
        "email": "newdev@devora.ai",
        "full_name": "New Developer",
        "password": "StrongPassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "newdev@devora.ai"
    assert data["user"]["full_name"] == "New Developer"


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(client: AsyncClient):
    payload = {
        "email": "duplicate@devora.ai",
        "full_name": "Duplicate Dev",
        "password": "StrongPassword123!",
    }
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    error = resp2.json()["error"]
    assert error["code"] == "RESOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login_test@devora.ai", "full_name": "Login Dev", "password": "Password123!"},
    )

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_test@devora.ai", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login_test@devora.ai"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrong_pwd@devora.ai", "full_name": "Wrong Pwd", "password": "CorrectPassword123!"},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong_pwd@devora.ai", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_current_user_profile(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "developer@devora.ai"
    assert data["full_name"] == "Devora Test Engineer"


@pytest.mark.asyncio
async def test_current_user_unauthorized_without_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
