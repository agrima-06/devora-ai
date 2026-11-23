"""Integration tests for Phase 10 Stage 10.6: Architecture-Aware Refactoring REST APIs."""

import hashlib
import uuid
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
def refactoring_seed_data():
    """Setup test codebase data for architectural refactoring recommendations."""
    return [
        {
            "file_path": "backend/app/api/v1/orders.py",
            "symbol_name": "create_order",
            "symbol_type": "function",
            "content": """from fastapi import APIRouter
router = APIRouter()
@router.post("/orders")
async def create_order(db, payload):
    res = await db.execute("INSERT INTO orders ...")
    return res
""",
            "embedding": [0.1] * 768,
        },
        {
            "file_path": "backend/app/services/order_service.py",
            "symbol_name": "OrderService",
            "symbol_type": "class",
            "content": "class OrderService:\n    async def process_order(self):\n        pass\n",
            "embedding": [0.2] * 768,
        },
        {
            "file_path": "backend/app/utils/date_helper.py",
            "symbol_name": "format_iso",
            "symbol_type": "function",
            "content": """def format_iso(dt):
    # TODO: tech debt refactor
    return dt.isoformat()
""",
            "embedding": [0.3] * 768,
        },
    ]


@pytest.mark.asyncio
async def test_refactoring_api_lifecycle(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    refactoring_seed_data: list,
):
    """Test complete API lifecycle for Architecture-Aware Refactoring Engine:
    1. GET recommendations
    2. POST create plan
    3. GET plans list & plan details
    4. POST reject plan
    5. POST create 2nd plan & approve plan
    6. POST execute plan with mismatched diff hash -> 400 & invalidated
    7. POST execute plan with matching diff hash -> 200 completed
    8. GET execution details & before/after comparison
    9. Multi-tenant isolation verification
    """
    # 1. Setup project and repository
    proj = Project(name="Refactoring Test Project", slug=f"refact-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="refactor-test-repo",
        full_name="testuser/refactor-test-repo",
        clone_url="https://github.com/testuser/refactor-test-repo.git",
        default_branch="main",
        current_commit_sha="abcdef1234567890",
        language="python",
        is_private=False,
    )
    db_session.add(repo)
    await db_session.flush()

    # Seed files and knowledge
    for item in refactoring_seed_data:
        k = RepositoryKnowledge(
            repository_id=repo.id,
            file_path=item["file_path"],
            symbol_name=item["symbol_name"],
            symbol_type=item["symbol_type"],
            content=item["content"],
            embedding=item["embedding"],
            meta_info={"start_line": 1, "end_line": 20},
        )
        f = RepositoryFile(
            repository_id=repo.id,
            file_path=item["file_path"],
            language="python",
            size_bytes=len(item["content"]),
            lines_count=10,
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
            end_line=20,
        )
        db_session.add_all([k, f, node])

    await db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 1: GET recommendations
    # -------------------------------------------------------------------------
    recs_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/recommendations",
        headers=auth_headers,
    )
    assert recs_resp.status_code == 200
    recs_data = recs_resp.json()
    assert recs_data["repository_id"] == str(repo.id)
    assert "recommendations" in recs_data
    assert isinstance(recs_data["recommendations"], list)
    assert recs_data["total_recommendations"] >= 1

    rec_ids = [r["recommendation_id"] for r in recs_data["recommendations"][:2]]

    # -------------------------------------------------------------------------
    # STEP 2: POST create refactoring plan
    # -------------------------------------------------------------------------
    create_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans",
        headers=auth_headers,
        json={
            "recommendation_ids": rec_ids,
            "title": "Decouple Layering and Utilities",
            "description": "Refactor routes to use dedicated domain services",
        },
    )
    assert create_resp.status_code == 201
    plan_data = create_resp.json()
    assert plan_data["repository_id"] == str(repo.id)
    assert plan_data["title"] == "Decouple Layering and Utilities"
    assert len(plan_data["ordered_steps"]) >= 1
    plan_id = plan_data["plan_id"]

    # -------------------------------------------------------------------------
    # STEP 3: GET plans list & plan details
    # -------------------------------------------------------------------------
    list_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/plans",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total_count"] >= 1

    detail_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan_id}",
        headers=auth_headers,
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["plan_id"] == plan_id

    # -------------------------------------------------------------------------
    # STEP 4: POST reject plan
    # -------------------------------------------------------------------------
    reject_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan_id}/reject",
        headers=auth_headers,
        json={"reason": "Testing rejection flow"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["approval_status"] == "REJECTED"

    # -------------------------------------------------------------------------
    # STEP 5: Create a second plan and approve it
    # -------------------------------------------------------------------------
    create2_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans",
        headers=auth_headers,
        json={
            "recommendation_ids": [rec_ids[0]],
            "title": "Decouple Order Route",
        },
    )
    assert create2_resp.status_code == 201
    plan2_id = create2_resp.json()["plan_id"]

    simulated_diff = "--- a/orders.py\n+++ b/orders.py\n@@ -1 +1 @@\n-raw db\n+service call"
    expected_hash = hashlib.sha256(simulated_diff.encode("utf-8")).hexdigest()

    approve_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan2_id}/approve",
        headers=auth_headers,
        json={
            "diff_hash": expected_hash,
            "notes": "Verified against staging tests",
        },
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["approval_status"] == "APPROVED"
    assert approve_resp.json()["approved_diff_hash"] == expected_hash

    # -------------------------------------------------------------------------
    # STEP 6: Execute with mismatched diff hash -> 400 & invalidation
    # -------------------------------------------------------------------------
    mismatch_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    mismatch_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan2_id}/execute",
        headers=auth_headers,
        json={"diff_hash": mismatch_hash},
    )
    assert mismatch_resp.status_code == 400
    err_body = mismatch_resp.json()
    err_msg = err_body.get("error", {}).get("message") or err_body.get("detail", "")
    assert "does not match the approved diff hash" in err_msg

    # Re-verify plan is now INVALIDATED
    check_invalid = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan2_id}",
        headers=auth_headers,
    )
    assert check_invalid.json()["approval_status"] == "INVALIDATED"

    # Re-approve plan with expected hash
    await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan2_id}/approve",
        headers=auth_headers,
        json={"diff_hash": expected_hash},
    )

    # -------------------------------------------------------------------------
    # STEP 7: Execute with matching diff hash -> 200 COMPLETED
    # -------------------------------------------------------------------------
    exec_resp = await client.post(
        f"/api/v1/repositories/{repo.id}/refactoring/plans/{plan2_id}/execute",
        headers=auth_headers,
        json={"diff_hash": expected_hash},
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["status"] == "COMPLETED"
    assert exec_data["baseline_tests_passed"] is True
    assert exec_data["post_tests_passed"] is True
    execution_id = exec_data["execution_id"]

    # -------------------------------------------------------------------------
    # STEP 8: GET execution details & comparison
    # -------------------------------------------------------------------------
    get_exec_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/executions/{execution_id}",
        headers=auth_headers,
    )
    assert get_exec_resp.status_code == 200
    assert get_exec_resp.json()["execution_id"] == execution_id

    comp_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/executions/{execution_id}/comparison",
        headers=auth_headers,
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["summary_verdict"] == "SUCCESSFUL_REFACTOR"
    assert comp_data["public_api_compatible"] is True

    # -------------------------------------------------------------------------
    # STEP 9: Multi-tenant security check (Foreign User)
    # -------------------------------------------------------------------------
    foreign_user = User(
        email=f"foreign_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Foreign Test User",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(foreign_user)
    await db_session.commit()

    # Generate token for foreign user using security helper or direct auth
    from app.core.security import create_access_token
    foreign_token = create_access_token(subject=str(foreign_user.id))
    foreign_headers = {"Authorization": f"Bearer {foreign_token}"}

    # Foreign user attempting to access repo's refactoring endpoints -> 404
    foreign_recs = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/recommendations",
        headers=foreign_headers,
    )
    assert foreign_recs.status_code == 404

    foreign_plans = await client.get(
        f"/api/v1/repositories/{repo.id}/refactoring/plans",
        headers=foreign_headers,
    )
    assert foreign_plans.status_code == 404
