"""Integration tests for Phase 10 Stage 10.4: Semantic Architecture & Pattern Inference REST APIs."""

import json
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User


@pytest.fixture
def test_architecture_repo_data():
    """Setup mock repository files and symbols in database."""
    return [
        {
            "file_path": "backend/app/services/order_service.py",
            "symbol_name": "OrderService",
            "symbol_type": "class",
            "content": "class OrderService: handles order placement and inventory reservation",
            "embedding": [0.7, 0.2, 0.1],
        },
        {
            "file_path": "backend/app/api/v1/orders.py",
            "symbol_name": "create_order",
            "symbol_type": "function",
            "content": "async def create_order(db: AsyncSession = Depends(get_db)): pass",
            "embedding": [0.6, 0.3, 0.1],
        },
        {
            "file_path": "backend/app/models/order.py",
            "symbol_name": "Order",
            "symbol_type": "class",
            "content": "class Order(Base): id = mapped_column(Integer, primary_key=True)",
            "embedding": [0.5, 0.1, 0.4],
        },
    ]


@pytest.mark.asyncio
async def test_architecture_api_full_lifecycle(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    test_architecture_repo_data: list,
):
    """Test full API lifecycle for architecture intelligence:

    1. Trigger analysis / GET architecture summary
    2. List patterns with category and confidence filtering
    3. Get specific pattern details
    4. List coding conventions
    5. Execute multi-modal hybrid search
    6. Ask architecture question grounded in codebase
    7. Verify tenant boundary isolation
    """
    # Create project and repository
    proj = Project(name="Arch Test Project", slug=f"arch-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="arch-test-repo",
        full_name="testuser/arch-test-repo",
        clone_url="https://github.com/testuser/arch-test-repo.git",
        default_branch="main",
        language="python",
        is_private=False,
    )
    db_session.add(repo)
    await db_session.flush()

    # Seed knowledge and files
    for item in test_architecture_repo_data:
        k = RepositoryKnowledge(
            repository_id=repo.id,
            file_path=item["file_path"],
            symbol_name=item["symbol_name"],
            symbol_type=item["symbol_type"],
            content=item["content"],
            embedding=item["embedding"],
            meta_info={"start_line": 1, "end_line": 20, "signature": item["symbol_name"]},
        )
        f = RepositoryFile(
            repository_id=repo.id,
            file_path=item["file_path"],
            language="python",
            size_bytes=100,
            commit_sha="a1b2c3d4",
        )
        node = RepositoryGraphNode(
            repository_id=repo.id,
            node_type="CLASS" if item["symbol_type"] == "class" else "FUNCTION",
            qualified_name=f"{item['file_path']}.{item['symbol_name']}",
            name=item["symbol_name"],
            file_path=item["file_path"],
            language="python",
            start_line=1,
            end_line=20,
        )
        db_session.add_all([k, f, node])

    await db_session.commit()

    # 1. Trigger architecture re-analysis
    analyze_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/architecture/analyze",
        headers=auth_headers,
    )
    assert analyze_resp.status_code == 200
    summary_data = analyze_resp.json()
    assert summary_data["repository_id"] == str(repo.id)
    assert summary_data["total_patterns"] > 0
    assert len(summary_data["patterns"]) > 0

    # 2. Get architecture summary
    summary_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture",
        headers=auth_headers,
    )
    assert summary_resp.status_code == 200
    assert summary_resp.json()["total_patterns"] == summary_data["total_patterns"]

    # 3. List patterns with category filter
    patterns_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture/patterns?category=application",
        headers=auth_headers,
    )
    assert patterns_resp.status_code == 200
    app_patterns = patterns_resp.json()
    assert all(p["category"] == "application" for p in app_patterns)

    # 4. Get specific pattern details
    pattern_id = app_patterns[0]["pattern_id"]
    pattern_detail_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture/patterns/{pattern_id}",
        headers=auth_headers,
    )
    assert pattern_detail_resp.status_code == 200
    assert pattern_detail_resp.json()["pattern_id"] == pattern_id

    # 4b. Non-existent pattern 404
    missing_pattern_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture/patterns/non_existent_pattern_slug",
        headers=auth_headers,
    )
    assert missing_pattern_resp.status_code == 404

    # 5. List conventions
    convs_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture/conventions",
        headers=auth_headers,
    )
    assert convs_resp.status_code == 200
    convs = convs_resp.json()
    assert len(convs) > 0
    assert any(c["category"] == "service" for c in convs)

    # 6. Execute multi-modal hybrid search
    search_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/search/hybrid",
        headers=auth_headers,
        json={
            "query": "OrderService",
            "limit": 5,
            "lexical_weight": 0.4,
            "semantic_weight": 0.4,
            "structural_weight": 0.2,
        },
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total_matches"] > 0
    top_result = search_data["results"][0]
    assert top_result["file_path"] == "backend/app/services/order_service.py"
    assert top_result["symbol_name"] == "OrderService"
    assert top_result["combined_score"] > 0.0
    assert "provenance_explanation" in top_result

    # 7. Ask architecture question
    ask_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/architecture/ask",
        headers=auth_headers,
        json={"question": "How are orders handled in the service layer?"},
    )
    assert ask_resp.status_code == 200
    ask_data = ask_resp.json()
    assert ask_data["confidence"] > 0.0
    assert len(ask_data["relevant_files"]) > 0
    assert "backend/app/services/order_service.py" in ask_data["relevant_files"]

    # 8. Tenant isolation: another user cannot access this repository
    other_user = User(
        email="intruder@example.com",
        full_name="Intruder User",
        hashed_password="hash",
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.flush()

    # Generate token for other_user
    from app.core.security import create_access_token
    other_token = create_access_token(subject=str(other_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    denied_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture",
        headers=other_headers,
    )
    assert denied_resp.status_code == 404
