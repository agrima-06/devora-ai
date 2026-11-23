"""Integration tests for Phase 10 Stage 10.5: Architectural Drift & Technical Debt REST APIs."""

import json
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User


@pytest.fixture
def drift_test_data():
    """Setup test codebase data containing architectural drift and technical debt markers."""
    return [
        {
            "file_path": "backend/app/api/v1/users.py",
            "symbol_name": "get_users",
            "symbol_type": "function",
            "content": """from fastapi import APIRouter
router = APIRouter()
@router.get("/users")
async def get_users(db):
    res = await db.execute(select(User))
    return res
""",
            "embedding": [0.1] * 768,
        },
        {
            "file_path": "backend/app/services/user_service.py",
            "symbol_name": "UserService",
            "symbol_type": "class",
            "content": "class UserService:\n    async def list_users(self):\n        pass\n",
            "embedding": [0.2] * 768,
        },
        {
            "file_path": "backend/app/agents/specialists/rogue_agent.py",
            "symbol_name": "run_agent",
            "symbol_type": "function",
            "content": """import google.generativeai as genai
def run_agent():
    return genai.GenerativeModel("gemini-1.5-pro").generate_content("hello")
""",
            "embedding": [0.3] * 768,
        },
        {
            "file_path": "backend/app/legacy/messy.py",
            "symbol_name": "do_messy_work",
            "symbol_type": "function",
            "content": """def do_messy_work():
    # TODO: fix technical debt
    # FIXME: hacky fix
    # TODO: refactor this
    try:
        do_work()
    except Exception: pass
""",
            "embedding": [0.4] * 768,
        },
    ]


@pytest.mark.asyncio
async def test_drift_and_technical_debt_api_lifecycle(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    drift_test_data: list,
):
    """Test full API lifecycle for Architectural Drift and Technical Debt:
    1. POST /repositories/{id}/architecture/drift/analyze
    2. GET /repositories/{id}/architecture/drift
    3. POST /repositories/{id}/technical-debt/analyze
    4. GET /repositories/{id}/technical-debt
    5. GET /repositories/{id}/technical-debt/findings (with filtering)
    6. GET /repositories/{id}/technical-debt/findings/{finding_id}
    7. GET /repositories/{id}/technical-debt/trends
    8. Multi-tenant security isolation check
    """
    # 1. Setup project and repository
    proj = Project(name="Drift Test Project", slug=f"drift-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="drift-test-repo",
        full_name="testuser/drift-test-repo",
        clone_url="https://github.com/testuser/drift-test-repo.git",
        default_branch="main",
        current_commit_sha="c0ffee1234567890",
        language="python",
        is_private=False,
    )
    db_session.add(repo)
    await db_session.flush()

    # Seed files, knowledge, and graph nodes
    for item in drift_test_data:
        k = RepositoryKnowledge(
            repository_id=repo.id,
            file_path=item["file_path"],
            symbol_name=item["symbol_name"],
            symbol_type=item["symbol_type"],
            content=item["content"],
            embedding=item["embedding"],
            meta_info={"start_line": 1, "end_line": 30},
        )
        f = RepositoryFile(
            repository_id=repo.id,
            file_path=item["file_path"],
            language="python",
            size_bytes=len(item["content"]),
            lines_count=15,
            commit_sha=repo.current_commit_sha,
        )
        node = RepositoryGraphNode(
            repository_id=repo.id,
            node_type="CLASS" if item["symbol_type"] == "class" else "FUNCTION",
            qualified_name=f"{item['file_path']}.{item['symbol_name']}",
            name=item["symbol_name"],
            file_path=item["file_path"],
            language="python",
            start_line=1,
            end_line=30,
        )
        db_session.add_all([k, f, node])

    await db_session.commit()

    # -------------------------------------------------------------------------
    # 1. Trigger Architecture Drift Analysis
    # -------------------------------------------------------------------------
    drift_analyze_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/architecture/drift/analyze",
        headers=auth_headers,
    )
    assert drift_analyze_resp.status_code == 200
    drift_data = drift_analyze_resp.json()
    assert drift_data["repository_id"] == str(repo.id)
    assert drift_data["drift_status"] in ["HEALTHY", "DRIFT_DETECTED", "CRITICAL_DRIFT"]
    assert "violations" in drift_data
    assert drift_data["total_violations"] >= 1

    # Check for layering and security boundary violations in the findings
    rule_ids = [v["rule_id"] for v in drift_data["violations"]]
    assert "layering_violation" in rule_ids or "security_boundary" in rule_ids

    # -------------------------------------------------------------------------
    # 2. Get Architecture Drift Summary (Cached / Read)
    # -------------------------------------------------------------------------
    drift_get_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture/drift",
        headers=auth_headers,
    )
    assert drift_get_resp.status_code == 200
    drift_summary = drift_get_resp.json()
    assert drift_summary["total_violations"] == drift_data["total_violations"]

    # -------------------------------------------------------------------------
    # 3. Trigger Technical Debt Analysis
    # -------------------------------------------------------------------------
    debt_analyze_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/technical-debt/analyze",
        headers=auth_headers,
    )
    assert debt_analyze_resp.status_code == 200
    debt_data = debt_analyze_resp.json()
    assert debt_data["repository_id"] == str(repo.id)
    assert 0.0 <= debt_data["overall_debt_score"] <= 100.0
    assert debt_data["severity"] in ["CLEAN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert "dimension_scores" in debt_data
    assert "top_findings" in debt_data
    assert debt_data["total_findings"] >= 1

    # -------------------------------------------------------------------------
    # 4. Get Technical Debt Summary
    # -------------------------------------------------------------------------
    debt_get_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/technical-debt",
        headers=auth_headers,
    )
    assert debt_get_resp.status_code == 200
    debt_summary = debt_get_resp.json()
    assert debt_summary["overall_debt_score"] == debt_data["overall_debt_score"]

    # -------------------------------------------------------------------------
    # 5. Query Paginated Technical Debt Findings
    # -------------------------------------------------------------------------
    findings_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/technical-debt/findings?limit=10&offset=0",
        headers=auth_headers,
    )
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert findings_data["total_count"] >= 1
    assert len(findings_data["findings"]) >= 1

    # Test filtering by category
    maint_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/technical-debt/findings?category=maintainability",
        headers=auth_headers,
    )
    assert maint_resp.status_code == 200
    maint_data = maint_resp.json()
    for f in maint_data["findings"]:
        assert f["category"] == "maintainability"

    # -------------------------------------------------------------------------
    # 6. Retrieve Single Finding Details
    # -------------------------------------------------------------------------
    sample_finding = findings_data["findings"][0]
    finding_id = sample_finding["finding_id"]
    detail_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/technical-debt/findings/{finding_id}",
        headers=auth_headers,
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["finding_id"] == finding_id
    assert "explanation" in detail_data
    assert "remediation" in detail_data

    # -------------------------------------------------------------------------
    # 7. Query Technical Debt Historical Trends
    # -------------------------------------------------------------------------
    trends_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/technical-debt/trends",
        headers=auth_headers,
    )
    assert trends_resp.status_code == 200
    trends_data = trends_resp.json()
    assert "trends" in trends_data
    assert len(trends_data["trends"]) >= 1
    trend_item = trends_data["trends"][0]
    assert trend_item["commit_sha"] == "c0ffee1234567890"

    # -------------------------------------------------------------------------
    # 8. Multi-Tenant Security Isolation
    # -------------------------------------------------------------------------
    # Create another user and attempt to read repo drift/debt
    other_user = User(
        email=f"other-{uuid.uuid4().hex[:6]}@example.com",
        full_name="Other User",
        hashed_password="fakehashedpassword",
    )
    db_session.add(other_user)
    await db_session.commit()

    # Create token for other user
    from app.core.security import create_access_token
    other_token = create_access_token(subject=str(other_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    forbidden_drift = await client.get(
        f"/api/v1/repositories/{repo.id}/architecture/drift",
        headers=other_headers,
    )
    assert forbidden_drift.status_code == 404

    forbidden_debt = await client.get(
        f"/api/v1/repositories/{repo.id}/technical-debt",
        headers=other_headers,
    )
    assert forbidden_debt.status_code == 404
