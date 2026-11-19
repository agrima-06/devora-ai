"""Integration tests for Semantic Vector Memory API endpoints."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.user import User


@pytest.fixture
async def second_user(db_session: AsyncSession) -> User:
    user = User(
        email="attacker@isolated.com",
        full_name="Attacker User",
        hashed_password=get_password_hash("Secret123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_memory_api_full_lifecycle(
    client: AsyncClient,
    test_user: User,
    test_repository,
    auth_headers: dict,
    second_user: User,
):
    """Test memory creation, semantic search, update, stale marking, stats, and feedback."""
    repo_id = str(test_repository.id)
    other_auth_headers = {"Authorization": f"Bearer {create_access_token(subject=str(second_user.id))}"}

    # 1. Create a memory
    create_res = await client.post(
        f"/api/v1/repositories/{repo_id}/memories",
        json={
            "category": "coding_conventions",
            "title": "Use Pydantic v2 BaseSettings",
            "content": "Configuration settings must inherit from pydantic_settings.BaseSettings with SettingsConfigDict.",
            "source_reference": "app/config.py",
            "verification_status": "developer_confirmed",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    mem_data = create_res.json()
    memory_id = mem_data["id"]
    assert mem_data["title"] == "Use Pydantic v2 BaseSettings"
    assert mem_data["verification_status"] == "developer_confirmed"
    assert mem_data["is_stale"] is False

    # 2. List memories with filter
    list_res = await client.get(
        f"/api/v1/repositories/{repo_id}/memories?category=coding_conventions",
        headers=auth_headers,
    )
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert items[0]["id"] == memory_id

    # 3. Perform semantic search
    search_res = await client.post(
        f"/api/v1/repositories/{repo_id}/memories/search",
        json={
            "query": "Pydantic BaseSettings configuration settings",
            "limit": 5,
            "threshold": 0.20,
        },
        headers=auth_headers,
    )
    assert search_res.status_code == 200
    search_items = search_res.json()
    assert len(search_items) >= 1
    assert any(s["id"] == memory_id for s in search_items)
    assert search_items[0]["score"] > 0

    # 4. Get memory stats
    stats_res = await client.get(
        f"/api/v1/repositories/{repo_id}/memories/stats",
        headers=auth_headers,
    )
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_memories"] >= 1
    assert stats["verified_count"] >= 1
    assert stats["stale_count"] == 0

    # 5. Submit feedback
    fb_res = await client.post(
        f"/api/v1/repositories/{repo_id}/memories/{memory_id}/feedback",
        json={
            "is_helpful": True,
            "notes": "Directly resolved config import mismatch in settings module.",
        },
        headers=auth_headers,
    )
    assert fb_res.status_code == 201
    fb_data = fb_res.json()
    assert fb_data["is_helpful"] is True

    # 6. Mark memory as stale
    stale_res = await client.post(
        f"/api/v1/repositories/{repo_id}/memories/{memory_id}/stale?reason=Migrated+to+Pydantic+v3",
        headers=auth_headers,
    )
    assert stale_res.status_code == 200
    assert stale_res.json()["is_stale"] is True

    # 7. Tenant Isolation: Second unauthorized user must be rejected
    unauth_get = await client.get(
        f"/api/v1/repositories/{repo_id}/memories",
        headers=other_auth_headers,
    )
    assert unauth_get.status_code == 404

    unauth_search = await client.post(
        f"/api/v1/repositories/{repo_id}/memories/search",
        json={"query": "Pydantic settings"},
        headers=other_auth_headers,
    )
    assert unauth_search.status_code == 404

    # 8. Delete memory
    del_res = await client.delete(
        f"/api/v1/repositories/{repo_id}/memories/{memory_id}",
        headers=auth_headers,
    )
    assert del_res.status_code == 204
