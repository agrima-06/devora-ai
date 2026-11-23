"""Unit tests for Phase 10 Stage 10.5: Technical Debt Service."""

import uuid
from typing import Any, Dict, List
import pytest

from app.models.flaky_test_record import FlakyTestRecord
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.services.technical_debt_service import TechnicalDebtService


def test_composite_score_formula_and_bands():
    """Verify deterministic 0-100 technical debt scoring formula and severity bands."""
    service = TechnicalDebtService()

    # Zero debt -> CLEAN
    scores_clean = service._calculate_composite_score(
        complexity=0.0,
        duplication=0.0,
        dependency=0.0,
        test_debt=0.0,
        maintainability=0.0,
    )
    assert scores_clean["score"] == 0.0
    assert scores_clean["severity"] == "CLEAN"

    # Low band (16-35): 0.25*40 + 0.20*30 + 0.20*20 = 10 + 6 + 4 = 20.0 -> LOW
    scores_low = service._calculate_composite_score(
        complexity=40.0,
        duplication=30.0,
        dependency=20.0,
        test_debt=0.0,
        maintainability=0.0,
    )
    assert 16.0 <= scores_low["score"] <= 35.0
    assert scores_low["severity"] == "LOW"

    # Medium band (36-60): 0.25*50 + 0.20*50 + 0.20*50 + 0.20*50 + 0.15*50 = 50.0 -> MEDIUM
    scores_med = service._calculate_composite_score(
        complexity=50.0,
        duplication=50.0,
        dependency=50.0,
        test_debt=50.0,
        maintainability=50.0,
    )
    assert scores_med["score"] == 50.0
    assert scores_med["severity"] == "MEDIUM"

    # High band (61-80): 0.25*70 + 0.20*70 + 0.20*70 + 0.20*70 + 0.15*70 = 70.0 -> HIGH
    scores_high = service._calculate_composite_score(
        complexity=70.0,
        duplication=70.0,
        dependency=70.0,
        test_debt=70.0,
        maintainability=70.0,
    )
    assert scores_high["score"] == 70.0
    assert scores_high["severity"] == "HIGH"

    # Critical band (81-100): 0.25*90 + 0.20*90 + 0.20*90 + 0.20*90 + 0.15*90 = 90.0 -> CRITICAL
    scores_crit = service._calculate_composite_score(
        complexity=90.0,
        duplication=90.0,
        dependency=90.0,
        test_debt=90.0,
        maintainability=90.0,
    )
    assert scores_crit["score"] == 90.0
    assert scores_crit["severity"] == "CRITICAL"

    # Max clamp at 100.0
    scores_clamped = service._calculate_composite_score(
        complexity=150.0,
        duplication=150.0,
        dependency=150.0,
        test_debt=150.0,
        maintainability=150.0,
    )
    assert scores_clamped["score"] == 100.0


def test_evaluate_complexity_dimension():
    """Verify detection of oversized functions and classes."""
    service = TechnicalDebtService()
    repo_id = uuid.uuid4()

    node_fn = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="process_huge_batch",
        node_type="FUNCTION",
        file_path="backend/app/services/processor.py",
        start_line=1,
        end_line=121,
    )
    node_cls = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="GodManager",
        node_type="CLASS",
        file_path="backend/app/services/god_manager.py",
        start_line=1,
        end_line=550,
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "nodes": [node_fn, node_cls],
        "edges": [],
        "files": [],
        "knowledge": [],
    }

    findings, score = service._evaluate_complexity(ev)
    assert score > 0.0
    assert len(findings) == 2
    f_names = [f.symbol_name for f in findings]
    assert "process_huge_batch" in f_names
    assert "GodManager" in f_names


def test_evaluate_duplication_dimension():
    """Verify detection of duplicated code blocks."""
    service = TechnicalDebtService()
    repo_id = uuid.uuid4()

    block = """
    val = input_data.strip()
    if not val:
        raise ValueError("empty")
    res = compute_hash(val)
    cache.set(val, res)
    return res
"""
    func_a = f"def helper_one(input_data, cache):{block}"
    func_b = f"def helper_two(input_data, cache):{block}"

    k1 = RepositoryKnowledge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="backend/app/utils/hash_one.py",
        symbol_name="helper_one",
        symbol_type="function",
        content=func_a,
        embedding=[0.0] * 768,
        meta_info={"start_line": 1},
    )
    k2 = RepositoryKnowledge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="backend/app/utils/hash_two.py",
        symbol_name="helper_two",
        symbol_type="function",
        content=func_b,
        embedding=[0.0] * 768,
        meta_info={"start_line": 1},
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "knowledge": [k1, k2],
        "nodes": [],
        "edges": [],
        "files": [],
    }

    findings, score = service._evaluate_duplication(ev)
    assert score > 0.0
    assert len(findings) >= 1
    f = findings[0]
    assert f.category == "duplication"
    assert "TOKEN_SIMILARITY" in f.detection_method


def test_evaluate_maintainability_markers():
    """Verify detection of TODO accumulations and bare exception handling."""
    service = TechnicalDebtService()
    repo_id = uuid.uuid4()

    code = """def execute_work():
    # TODO: fix this technical debt
    # FIXME: hacky workaround
    # TODO: refactor query
    # TODO: add validation
    # TODO: deprecate this
    try:
        call_subsystem()
    except:
        pass
    try:
        other_call()
    except Exception: pass
"""
    k = RepositoryKnowledge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="backend/app/legacy/worker.py",
        symbol_name="execute_work",
        symbol_type="function",
        content=code,
        embedding=[0.0] * 768,
        meta_info={"start_line": 1},
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "knowledge": [k],
        "nodes": [],
        "edges": [],
        "files": [],
    }

    findings, score = service._evaluate_maintainability(ev)
    assert score > 0.0
    assert len(findings) >= 1
    categories = [f.category for f in findings]
    assert "maintainability" in categories
    explanations = " ".join(f.explanation.lower() for f in findings)
    assert "todo" in explanations or "exception" in explanations


def test_evaluate_test_debt():
    """Verify evaluation of test deficits and flaky test impacts."""
    service = TechnicalDebtService()
    repo_id = uuid.uuid4()

    f_svc = RepositoryFile(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="backend/app/services/payment_service.py",
        language="python",
        size_bytes=1000,
        lines_count=50,
        commit_sha="abc12345",
    )
    flaky = FlakyTestRecord(
        id=uuid.uuid4(),
        repository_id=repo_id,
        task_id=uuid.uuid4(),
        test_identifier="test_charge_retry",
        test_file="backend/tests/test_payment.py",
        test_command="pytest backend/tests/test_payment.py",
        framework="pytest",
        classification="FLAKY",
        stability_score=0.45,
        total_runs=10,
        passed_runs=7,
        failed_runs=3,
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "files": [f_svc],
        "flaky_records": [flaky],
        "nodes": [],
        "edges": [],
        "knowledge": [],
    }

    findings, score = service._evaluate_test_debt(ev)
    assert score > 0.0
    assert len(findings) >= 1
    f_categories = [f.category for f in findings]
    assert "test" in f_categories
