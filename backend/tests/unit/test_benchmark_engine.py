"""Unit tests for Phase 10 Stage 10.7: Benchmark Engine Service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.models.benchmark_engine import BenchmarkScenario, BenchmarkScenarioResult, BenchmarkSuiteRun
from app.services.benchmark_dataset import BENCHMARK_SCENARIOS_DATASET
from app.services.benchmark_engine_service import (
    BenchmarkEngineService,
    BenchmarkEvaluator,
    BenchmarkScoringService,
)


def test_dataset_scenario_count_and_distribution():
    """Verify that canonical dataset contains at least 30 scenarios across all 7 categories."""
    assert len(BENCHMARK_SCENARIOS_DATASET) >= 30
    categories = [s["category"] for s in BENCHMARK_SCENARIOS_DATASET]
    cat_counts = {c: categories.count(c) for c in set(categories)}

    # Verify minimum required distribution
    assert cat_counts.get("bug_detection", 0) >= 5
    assert cat_counts.get("repo_understanding", 0) >= 5
    assert cat_counts.get("arch_intelligence", 0) >= 4
    assert cat_counts.get("impact_analysis", 0) >= 4
    assert cat_counts.get("refactoring", 0) >= 5
    assert cat_counts.get("multi_agent", 0) >= 4
    assert cat_counts.get("security_safety", 0) >= 4


def test_evaluator_exact_match():
    """Verify exact match evaluation scoring."""
    scenario = BenchmarkScenario(
        id=uuid.uuid4(),
        scenario_key="test_exact",
        category="repo_understanding",
        name="Exact Match Test",
        eval_type="EXACT_MATCH",
        expected_output={"framework": "FastAPI", "entrypoint": "main.py"},
        evaluation_criteria={"required_fields": ["framework", "entrypoint"], "pass_threshold": 80.0},
    )

    actual_success = {"framework": "FastAPI", "entrypoint": "main.py"}
    score, met, safety, reason, ev = BenchmarkEvaluator.evaluate(scenario, actual_success)
    assert score == 100.0
    assert met is True
    assert safety is False

    actual_partial = {"framework": "FastAPI", "entrypoint": "wrong.py"}
    score_p, met_p, _, _, _ = BenchmarkEvaluator.evaluate(scenario, actual_partial)
    assert score_p == 50.0
    assert met_p is False


def test_evaluator_security_policy_enforcement():
    """Verify security policy evaluation detects safety breaches."""
    scenario = BenchmarkScenario(
        id=uuid.uuid4(),
        scenario_key="test_sec",
        category="security_safety",
        name="Security Policy Test",
        eval_type="SECURITY_POLICY",
        expected_output={"vulnerability": "SQL_INJECTION", "safety_passed": True},
        evaluation_criteria={"required_fields": ["vulnerability", "safety_passed"], "pass_threshold": 100.0},
    )

    # Compliant output
    actual_safe = {"vulnerability": "SQL_INJECTION", "safety_passed": True}
    score, met, safety_violated, _, _ = BenchmarkEvaluator.evaluate(scenario, actual_safe)
    assert score == 100.0
    assert met is True
    assert safety_violated is False

    # Safety breach
    actual_unsafe = {"vulnerability": "SQL_INJECTION", "safety_passed": False}
    score_bad, met_bad, safety_violated_bad, reason, _ = BenchmarkEvaluator.evaluate(scenario, actual_unsafe)
    assert score_bad == 0.0
    assert met_bad is False
    assert safety_violated_bad is True
    assert "Security policy violation" in (reason or "")


def test_scoring_formula_deterministic_weights():
    """Verify canonical weighted scoring formula across all 7 categories."""
    category_scores = {
        "bug_detection": 90.0,      # 0.30 -> 27.0
        "repo_understanding": 80.0, # 0.15 -> 12.0
        "arch_intelligence": 80.0,  # 0.15 -> 12.0
        "refactoring": 100.0,       # 0.15 -> 15.0
        "security_safety": 100.0,   # 0.15 -> 15.0
        "multi_agent": 90.0,        # 0.05 -> 4.5
        "impact_analysis": 90.0,    # 0.05 -> 4.5
    }
    # Expected: 27 + 12 + 12 + 15 + 15 + 4.5 + 4.5 = 90.0
    agg = BenchmarkScoringService.calculate_aggregate_score(category_scores, critical_safety_failure=False)
    assert agg == 90.0


def test_critical_safety_override_collapses_score():
    """Verify that any critical safety failure collapses aggregate score to zero."""
    category_scores = {
        "bug_detection": 100.0,
        "repo_understanding": 100.0,
        "arch_intelligence": 100.0,
        "refactoring": 100.0,
        "security_safety": 0.0,
        "multi_agent": 100.0,
        "impact_analysis": 100.0,
    }
    # Safety failure = True -> must force 0.0 regardless of other high scores
    agg_overridden = BenchmarkScoringService.calculate_aggregate_score(
        category_scores,
        critical_safety_failure=True,
    )
    assert agg_overridden == 0.0


def test_calibration_error_calculation():
    """Verify calculation of Expected Calibration Error (ECE)."""
    sc = BenchmarkScenario(id=uuid.uuid4(), scenario_key="s1", category="bug_detection")
    r1 = BenchmarkScenarioResult(scenario=sc, score=80.0, confidence_score=0.85)  # error = |0.85 - 0.80| = 0.05
    r2 = BenchmarkScenarioResult(scenario=sc, score=100.0, confidence_score=0.95) # error = |0.95 - 1.00| = 0.05
    ece = BenchmarkScoringService.calculate_calibration_error([r1, r2])
    assert ece == 0.05
