"""Integration tests for Benchmark Multi-Tenant Isolation and Ground-Truth Leakage Protection.

Verifies:
1. Ground-truth leakage prevention: ordinary users cannot retrieve hidden ground-truth outputs or evaluation invariants.
2. Tenant isolation: Tenant B cannot view, cancel, compare, or retrieve reports for Tenant A's benchmark runs.
3. Administrative authorization guards on custom scenario creation.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token
from app.models.user import User


@pytest.fixture
async def tenant_b_user(db_session: AsyncSession) -> User:
    """Create a distinct second tenant for multi-tenant isolation testing."""
    user = User(
        id=uuid.uuid4(),
        email="tenant_b@enterprise.com",
        hashed_password="hashed_pw_b",
        full_name="Tenant B Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def tenant_b_headers(tenant_b_user: User) -> dict:
    """Auth headers for Tenant B."""
    token = create_access_token(subject=str(tenant_b_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def superuser(db_session: AsyncSession) -> User:
    """Create a superuser for admin authorization testing."""
    admin = User(
        id=uuid.uuid4(),
        email="root@devora.ai",
        hashed_password="hashed_admin_pw",
        full_name="System Auditor",
        is_active=True,
    )
    admin.is_superuser = True
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
def superuser_headers(superuser: User) -> dict:
    """Auth headers for superuser."""
    token = create_access_token(subject=str(superuser.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ground_truth_leakage_protection(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    superuser_headers: dict,
    db_session: AsyncSession,
):
    """Verify that unprivileged users cannot view raw ground truth, while authorized evaluators can."""
    # Seed dataset
    seed_res = await client.post("/api/v1/benchmarks/seed", headers=auth_headers)
    assert seed_res.status_code == 200

    # 1. Unprivileged user query
    resp = await client.get("/api/v1/benchmarks/scenarios/scenario_a1_null_dereference", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_key"] == "scenario_a1_null_dereference"
    # Ground truth must be protected and redacted
    assert data["expected_output"].get("_ground_truth_status") == "PROTECTED"
    assert "_redaction_reason" in data["expected_output"]
    assert data["evaluation_criteria"].get("_protected") is True

    # 2. Authorized superuser query
    admin_resp = await client.get("/api/v1/benchmarks/scenarios/scenario_a1_null_dereference", headers=superuser_headers)
    assert admin_resp.status_code == 200
    admin_data = admin_resp.json()
    # Admin gets full ground-truth
    assert "_ground_truth_status" not in admin_data["expected_output"]
    assert "remediated" in admin_data["expected_output"] or len(admin_data["expected_output"]) > 0


@pytest.mark.asyncio
async def test_unauthorized_scenario_creation_blocked(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify that non-admin users cannot inject arbitrary scenarios into the canonical dataset."""
    new_scenario_payload = {
        "scenario_key": "scenario_malicious_injected",
        "category": "security_safety",
        "name": "Malicious Injected Scenario",
        "description": "Unauthorized injection attempt",
        "difficulty": "LOW",
        "eval_type": "EXACT_MATCH",
        "input_context": {"code": "print(1)"},
        "expected_output": {"result": 1},
        "evaluation_criteria": {"pass_threshold": 100.0},
        "tags": ["malicious"],
    }
    resp = await client.post("/api/v1/benchmarks/scenarios", json=new_scenario_payload, headers=auth_headers)
    assert resp.status_code == 403
    err_msg = resp.json().get("error", {}).get("message", "") or resp.text
    assert "Administrative access required" in err_msg


@pytest.mark.asyncio
async def test_multi_tenant_run_isolation(
    client: AsyncClient,
    test_user: User,
    tenant_b_user: User,
    auth_headers: dict,
    tenant_b_headers: dict,
    db_session: AsyncSession,
):
    """Verify that Tenant B cannot access, cancel, compare, or generate reports for Tenant A's runs."""
    # Seed dataset
    await client.post("/api/v1/benchmarks/seed", headers=auth_headers)

    # 1. Tenant A triggers a benchmark suite run
    run_req = {
        "model_name": "gemini-1.5-pro",
        "suite_name": "tenant_a_private_suite",
        "categories": ["bug_detection"],
    }
    run_a_resp = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=auth_headers)
    assert run_a_resp.status_code == 201
    run_a_id = run_a_resp.json()["run_id"]

    # 2. Tenant B attempts to read Tenant A's run details -> 403
    b_get_resp = await client.get(f"/api/v1/benchmarks/runs/{run_a_id}", headers=tenant_b_headers)
    assert b_get_resp.status_code == 403
    assert "Access denied" in (b_get_resp.json().get("error", {}).get("message", "") or b_get_resp.text)

    # 3. Tenant B attempts to cancel Tenant A's run -> 403
    b_cancel_resp = await client.post(f"/api/v1/benchmarks/runs/{run_a_id}/cancel", headers=tenant_b_headers)
    assert b_cancel_resp.status_code == 403

    # 4. Tenant B attempts to generate report for Tenant A's run -> 403
    b_report_resp = await client.get(f"/api/v1/benchmarks/runs/{run_a_id}/report", headers=tenant_b_headers)
    assert b_report_resp.status_code == 403

    # 5. Tenant B triggers their own run
    run_b_resp = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=tenant_b_headers)
    assert run_b_resp.status_code == 201
    run_b_id = run_b_resp.json()["run_id"]

    # 6. Tenant B attempts to compare their run against Tenant A's run -> 403
    comp_req = {
        "baseline_run_id": run_a_id,
        "target_run_id": run_b_id,
    }
    b_comp_resp = await client.post("/api/v1/benchmarks/compare", json=comp_req, headers=tenant_b_headers)
    assert b_comp_resp.status_code == 403
    assert "belonging to your tenant" in (b_comp_resp.json().get("error", {}).get("message", "") or b_comp_resp.text)

    # 7. Tenant B lists runs -> MUST NOT see Tenant A's run
    b_list_resp = await client.get("/api/v1/benchmarks/runs", headers=tenant_b_headers)
    assert b_list_resp.status_code == 200
    b_runs = b_list_resp.json()["runs"]
    assert all(r["run_id"] != run_a_id for r in b_runs)
    assert any(r["run_id"] == run_b_id for r in b_runs)
