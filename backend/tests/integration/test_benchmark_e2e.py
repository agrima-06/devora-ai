"""End-to-end tests for Phase 10 Stage 10.7: Benchmark Engine 10 Required Evaluation Flows."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


@pytest.mark.asyncio
async def test_benchmark_e2e_all_ten_flows(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify all 10 core evaluation and benchmarking flows."""

    # -------------------------------------------------------------------------
    # Flow 1: Ground truth scenario registration across all 7 categories
    # -------------------------------------------------------------------------
    seed_res = await client.post("/api/v1/benchmarks/seed", headers=auth_headers)
    assert seed_res.status_code == 200
    sc_list_res = await client.get("/api/v1/benchmarks/scenarios", headers=auth_headers)
    assert sc_list_res.status_code == 200
    sc_data = sc_list_res.json()
    assert sc_data["total_count"] >= 30
    counts = sc_data["category_counts"]
    assert counts.get("bug_detection", 0) >= 5
    assert counts.get("repo_understanding", 0) >= 5
    assert counts.get("arch_intelligence", 0) >= 4
    assert counts.get("impact_analysis", 0) >= 4
    assert counts.get("refactoring", 0) >= 5
    assert counts.get("multi_agent", 0) >= 4
    assert counts.get("security_safety", 0) >= 4

    # -------------------------------------------------------------------------
    # Flow 2: Suite execution trigger with model selection (gemini-1.5-pro)
    # -------------------------------------------------------------------------
    trigger_payload = {
        "model_name": "gemini-1.5-pro",
        "suite_name": "devora_core_intelligence_suite",
        "code_revision": "HEAD",
    }
    run_res = await client.post("/api/v1/benchmarks/runs", json=trigger_payload, headers=auth_headers)
    assert run_res.status_code == 201
    baseline_run = run_res.json()
    baseline_id = baseline_run["run_id"]
    assert baseline_run["model_name"] == "gemini-1.5-pro"
    assert baseline_run["status"] == "COMPLETED"

    # -------------------------------------------------------------------------
    # Flow 3: Individual scenario evaluation across evaluation types
    # -------------------------------------------------------------------------
    results = baseline_run["results"]
    assert len(results) >= 30
    eval_types_tested = {r["scenario_key"]: r["status"] for r in results}
    assert "scenario_a1_null_dereference" in eval_types_tested
    assert "scenario_b1_symbol_resolution_hierarchy" in eval_types_tested
    assert "scenario_c1_layered_architecture_inference" in eval_types_tested
    assert "scenario_d1_public_api_breaking_signature" in eval_types_tested
    assert "scenario_e1_decompose_oversized_function" in eval_types_tested
    assert "scenario_f1_planner_to_coder_handoff" in eval_types_tested
    assert "scenario_g1_sql_injection_remediation" in eval_types_tested

    # -------------------------------------------------------------------------
    # Flow 4: Automated calculation of normalized category scores (0-100)
    # -------------------------------------------------------------------------
    cat_scores = baseline_run["category_scores"]
    for cat in ["bug_detection", "repo_understanding", "arch_intelligence", "impact_analysis", "refactoring", "multi_agent", "security_safety"]:
        assert cat in cat_scores
        assert 0.0 <= cat_scores[cat] <= 100.0

    # -------------------------------------------------------------------------
    # Flow 5: Aggregate intelligence score computation using weighted formula
    # -------------------------------------------------------------------------
    expected_weighted = (
        cat_scores["bug_detection"] * 0.30
        + cat_scores["repo_understanding"] * 0.15
        + cat_scores["arch_intelligence"] * 0.15
        + cat_scores["refactoring"] * 0.15
        + cat_scores["security_safety"] * 0.15
        + cat_scores["multi_agent"] * 0.05
        + cat_scores["impact_analysis"] * 0.05
    )
    assert abs(baseline_run["aggregate_score"] - round(expected_weighted, 1)) <= 0.2

    # -------------------------------------------------------------------------
    # Flow 6: Expected Calibration Error (ECE) between confidence & accuracy
    # -------------------------------------------------------------------------
    assert "calibration_error" in baseline_run
    assert 0.0 <= baseline_run["calibration_error"] <= 0.20

    # -------------------------------------------------------------------------
    # Flow 7: Critical safety override invariant enforcement
    # -------------------------------------------------------------------------
    safety_override_payload = {
        "model_name": "unsafe-candidate-model",
        "suite_name": "devora_safety_audit_suite",
        "categories": ["security_safety"],
        "simulate_safety_failure": True,
    }
    safety_run_res = await client.post("/api/v1/benchmarks/runs", json=safety_override_payload, headers=auth_headers)
    assert safety_run_res.status_code == 201
    safety_run = safety_run_res.json()
    assert safety_run["status"] == "CRITICAL_SAFETY_FAILURE"
    assert safety_run["critical_safety_failure"] is True
    assert safety_run["aggregate_score"] == 0.0

    # -------------------------------------------------------------------------
    # Flow 8: Side-by-side run comparison identifying metric deltas & regressions
    # -------------------------------------------------------------------------
    compare_payload = {
        "baseline_run_id": baseline_id,
        "target_run_id": safety_run["run_id"],
        "regression_threshold": 5.0,
    }
    comp_res = await client.post("/api/v1/benchmarks/compare", json=compare_payload, headers=auth_headers)
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["summary_verdict"] == "CRITICAL_SAFETY_BREACH"
    assert comp_data["critical_regressions"] >= 1
    assert comp_data["score_delta"] < 0

    # -------------------------------------------------------------------------
    # Flow 9: Audit-ready markdown report generation with complete evidence
    # -------------------------------------------------------------------------
    report_res = await client.get(f"/api/v1/benchmarks/runs/{baseline_id}/report", headers=auth_headers)
    assert report_res.status_code == 200
    report_data = report_res.json()
    md = report_data["markdown_content"]
    assert "# Devora AI — Benchmark Evaluation Report" in md
    assert "Executive Summary & Aggregate Intelligence Score" in md
    assert "Canonical Category Scores & Weighting Breakdown" in md
    assert "Scenario Evaluation Results Detail" in md

    # -------------------------------------------------------------------------
    # Flow 10: Run cancellation safety check
    # -------------------------------------------------------------------------
    # Attempting to cancel an already completed run should return 400 Bad Request
    cancel_res = await client.post(f"/api/v1/benchmarks/runs/{baseline_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 400
