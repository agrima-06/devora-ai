"""Integration tests for Phase 10 Stage 10.7: Benchmark Engine REST APIs."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


@pytest.mark.asyncio
async def test_benchmark_api_lifecycle(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test full lifecycle of Benchmark Engine REST APIs."""

    # 1. GET /api/v1/benchmarks/categories
    cat_resp = await client.get("/api/v1/benchmarks/categories", headers=auth_headers)
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert "categories" in cat_data
    assert len(cat_data["categories"]) == 7
    assert "weighting_formula" in cat_data

    # 2. GET /api/v1/benchmarks/models
    models_resp = await client.get("/api/v1/benchmarks/models", headers=auth_headers)
    assert models_resp.status_code == 200
    models_data = models_resp.json()
    assert len(models_data) >= 3
    assert any(m["model_id"] == "gemini-1.5-pro" for m in models_data)

    # 3. POST /api/v1/benchmarks/seed
    seed_resp = await client.post("/api/v1/benchmarks/seed", headers=auth_headers)
    assert seed_resp.status_code == 200
    seed_data = seed_resp.json()
    assert seed_data["total_scenarios"] >= 30

    # 4. GET /api/v1/benchmarks/scenarios
    sc_resp = await client.get("/api/v1/benchmarks/scenarios", headers=auth_headers)
    assert sc_resp.status_code == 200
    sc_data = sc_resp.json()
    assert sc_data["total_count"] >= 30
    assert "bug_detection" in sc_data["category_counts"]
    assert "security_safety" in sc_data["category_counts"]

    # 5. GET /api/v1/benchmarks/scenarios/scenario_a1_null_dereference
    one_sc = await client.get("/api/v1/benchmarks/scenarios/scenario_a1_null_dereference", headers=auth_headers)
    assert one_sc.status_code == 200
    assert one_sc.json()["scenario_key"] == "scenario_a1_null_dereference"
    assert one_sc.json()["category"] == "bug_detection"

    # 6. POST /api/v1/benchmarks/runs (Nominal execution)
    run_req = {
        "model_name": "gemini-1.5-pro",
        "suite_name": "devora_core_intelligence_suite",
        "code_revision": "HEAD",
        "categories": ["bug_detection", "security_safety"],
    }
    run_resp = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=auth_headers)
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    baseline_run_id = run_data["run_id"]
    assert run_data["status"] == "COMPLETED"
    assert run_data["critical_safety_failure"] is False
    assert run_data["aggregate_score"] > 0.0
    assert len(run_data["results"]) >= 9

    # 7. GET /api/v1/benchmarks/runs
    list_runs_resp = await client.get("/api/v1/benchmarks/runs", headers=auth_headers)
    assert list_runs_resp.status_code == 200
    assert list_runs_resp.json()["total_count"] >= 1

    # 8. GET /api/v1/benchmarks/runs/{run_id}
    detail_resp = await client.get(f"/api/v1/benchmarks/runs/{baseline_run_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["run_id"] == baseline_run_id
    assert len(detail_resp.json()["results"]) >= 9

    # 9. POST /api/v1/benchmarks/runs (Simulating safety breach)
    safety_breach_req = {
        "model_name": "test-experimental-model",
        "suite_name": "devora_core_intelligence_suite",
        "categories": ["security_safety"],
        "simulate_safety_failure": True,
    }
    safety_resp = await client.post("/api/v1/benchmarks/runs", json=safety_breach_req, headers=auth_headers)
    assert safety_resp.status_code == 201
    safety_data = safety_resp.json()
    target_run_id = safety_data["run_id"]
    # Critical Safety Override Verification
    assert safety_data["status"] == "CRITICAL_SAFETY_FAILURE"
    assert safety_data["critical_safety_failure"] is True
    assert safety_data["aggregate_score"] == 0.0

    # 10. POST /api/v1/benchmarks/compare
    compare_req = {
        "baseline_run_id": baseline_run_id,
        "target_run_id": target_run_id,
        "regression_threshold": 5.0,
    }
    comp_resp = await client.post("/api/v1/benchmarks/compare", json=compare_req, headers=auth_headers)
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["summary_verdict"] == "CRITICAL_SAFETY_BREACH"
    assert comp_data["critical_regressions"] >= 1

    # 11. GET /api/v1/benchmarks/runs/{run_id}/report
    report_resp = await client.get(f"/api/v1/benchmarks/runs/{baseline_run_id}/report", headers=auth_headers)
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert "Devora AI — Benchmark Evaluation Report" in report_data["markdown_content"]
    assert "Aggregate Intelligence Score" in report_data["markdown_content"]
