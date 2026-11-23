"""Unit tests for Phase 10 Stage 10.6: Architecture-Aware Refactoring Service."""

import hashlib
import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.core.exceptions import BadRequestException
from app.models.refactoring_execution import RefactoringExecution
from app.models.refactoring_plan import RefactoringPlan
from app.models.repository import Repository
from app.models.user import User
from app.schemas.refactoring import (
    RefactoringRecommendationItem,
    RefactoringStepItem,
)
from app.services.refactoring_service import ArchitectureAwareRefactoringService


def test_risk_score_deterministic_formula():
    """Verify deterministic risk scoring formula and levels (LOW, MEDIUM, HIGH)."""
    service = ArchitectureAwareRefactoringService()

    # Minimal scope: 1 file, 1 symbol, convention category -> LOW risk
    score_low, level_low, approval_low = service._calculate_plan_risk(
        files=["app/models/user.py"],
        symbols=["userModel"],
        packages=["backend"],
        category="convention",
        steps=[],
    )
    assert 0.0 <= score_low < 35.0
    assert level_low == "LOW"
    assert approval_low is False

    # Moderate scope: 2 files, 2 symbols, complexity category -> MEDIUM risk
    score_med, level_med, approval_med = service._calculate_plan_risk(
        files=["app/services/a.py", "app/services/b.py"],
        symbols=["func_a", "func_b"],
        packages=["backend"],
        category="complexity",
        steps=[],
    )
    assert 35.0 <= score_med < 66.0
    assert level_med == "MEDIUM"

    # High scope: security sensitive files or multi-package -> HIGH risk & approval required
    score_high, level_high, approval_high = service._calculate_plan_risk(
        files=["app/security/auth.py", "app/security/tokens.py", "app/api/v1/auth.py"],
        symbols=["verify_token", "issue_token"],
        packages=["backend", "frontend"],
        category="dependency",
        steps=[],
    )
    assert score_high >= 66.0
    assert level_high == "HIGH"
    assert approval_high is True


def test_topological_step_generation():
    """Verify topological generation and dependency ordering of refactoring steps across categories."""
    service = ArchitectureAwareRefactoringService()

    # Test LAYERING steps
    rec_layering = RefactoringRecommendationItem(
        recommendation_id="rec_l1",
        category="layering",
        title="Extract User Service",
        finding_ids=["f_l1"],
        target_files=["app/services/user_service.py", "app/api/v1/users.py"],
        target_symbols=["get_user"],
        current_problem="Direct DB query in route",
        proposed_architecture="Extract domain service",
        reason="Preserve clean architecture layering",
        expected_benefits=["Testability"],
        potential_risks=["Import path changes"],
        affected_packages=["backend"],
        dependency_path_evidence=["users.py -> user_service.py"],
        recommended_tests=["test_users.py"],
        confidence=0.9,
        estimated_complexity="MEDIUM",
        requires_human_approval=False,
    )

    steps = service._synthesize_ordered_steps([rec_layering])
    assert len(steps) >= 2
    assert steps[0].action == "EXTRACT_SERVICE"
    assert steps[1].action == "DELEGATE_CALL"
    assert steps[1].dependency_constraints == ["step_1"]

    # Test DEPENDENCY cycle breaking steps
    rec_dep = RefactoringRecommendationItem(
        recommendation_id="rec_d1",
        category="dependency",
        title="Break Circular Dependency",
        finding_ids=["f_d1"],
        target_files=["app/auth.py", "app/user.py"],
        target_symbols=[],
        current_problem="Cycle between auth and user",
        proposed_architecture="Decouple via interface",
        reason="Avoid circular imports",
        expected_benefits=["Cleaner DAG"],
        potential_risks=[],
        affected_packages=["backend"],
        dependency_path_evidence=[],
        recommended_tests=[],
        confidence=0.85,
        estimated_complexity="HIGH",
        requires_human_approval=True,
    )
    dep_steps = service._synthesize_ordered_steps([rec_dep])
    assert len(dep_steps) >= 1
    assert dep_steps[0].action == "BREAK_CYCLE"

    # Test DUPLICATION steps
    rec_dup = RefactoringRecommendationItem(
        recommendation_id="rec_u1",
        category="duplication",
        title="Consolidate duplicate utils",
        finding_ids=["f_u1"],
        target_files=["app/utils/a.py", "app/utils/b.py"],
        target_symbols=["fmt_date"],
        current_problem="Duplicate date formatting",
        proposed_architecture="Extract to shared utils",
        reason="DRY",
        expected_benefits=[],
        potential_risks=[],
        affected_packages=["backend"],
        dependency_path_evidence=[],
        recommended_tests=[],
        confidence=0.9,
        estimated_complexity="LOW",
        requires_human_approval=False,
    )
    dup_steps = service._synthesize_ordered_steps([rec_dup])
    assert dup_steps[0].action == "CONSOLIDATE_DUPLICATE"

    # Test COMPLEXITY steps
    rec_comp = RefactoringRecommendationItem(
        recommendation_id="rec_c1",
        category="complexity",
        title="Decompose function",
        finding_ids=["f_c1"],
        target_files=["app/processor.py"],
        target_symbols=["process_events"],
        current_problem="500 line function",
        proposed_architecture="Decompose helpers",
        reason="Single responsibility",
        expected_benefits=[],
        potential_risks=[],
        affected_packages=["backend"],
        dependency_path_evidence=[],
        recommended_tests=[],
        confidence=0.95,
        estimated_complexity="MEDIUM",
        requires_human_approval=False,
    )
    comp_steps = service._synthesize_ordered_steps([rec_comp])
    assert comp_steps[0].action == "DECOMPOSE_FUNCTION"

    # Test CONVENTION steps
    rec_conv = RefactoringRecommendationItem(
        recommendation_id="rec_n1",
        category="convention",
        title="Align Naming",
        finding_ids=["f_n1"],
        target_files=["app/models/user.py"],
        target_symbols=["userModel"],
        current_problem="CamelCase in python",
        proposed_architecture="Rename to snake_case",
        reason="PEP 8",
        expected_benefits=[],
        potential_risks=[],
        affected_packages=["backend"],
        dependency_path_evidence=[],
        recommended_tests=[],
        confidence=0.88,
        estimated_complexity="LOW",
        requires_human_approval=False,
    )
    conv_steps = service._synthesize_ordered_steps([rec_conv])
    assert conv_steps[0].action == "ALIGN_NAMING"

    # Test TESTABILITY steps
    rec_test = RefactoringRecommendationItem(
        recommendation_id="rec_t1",
        category="testability",
        title="Add tests",
        finding_ids=["f_t1"],
        target_files=["tests/test_payment.py"],
        target_symbols=["charge"],
        current_problem="Untested service",
        proposed_architecture="Add unit tests",
        reason="Regression protection",
        expected_benefits=[],
        potential_risks=[],
        affected_packages=["backend"],
        dependency_path_evidence=[],
        recommended_tests=[],
        confidence=0.9,
        estimated_complexity="LOW",
        requires_human_approval=False,
    )
    test_steps = service._synthesize_ordered_steps([rec_test])
    assert test_steps[0].action == "ADD_TEST"


@pytest.mark.asyncio
async def test_human_approval_diff_hash_binding():
    """Verify human approval binds cryptographic SHA-256 diff hash."""
    service = ArchitectureAwareRefactoringService()
    db = AsyncMock()

    plan_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    user_id = uuid.uuid4()

    user = User(id=user_id, email="lead@example.com")
    repo = Repository(id=repo_id, user_id=user_id, name="test-repo")

    plan = RefactoringPlan(
        id=plan_id,
        repository_id=repo_id,
        title="Decouple payment gateway",
        description="Extract interface",
        category="layering",
        risk_level="MEDIUM",
        risk_score=55.0,
        confidence=0.9,
        requires_human_approval=True,
        approval_status="PENDING",
        execution_status="DRAFT",
        target_files=["app/payment.py"],
        target_symbols=["charge"],
        finding_ids=["f1"],
        affected_packages=["backend"],
        ordered_steps=[],
        recommended_tests=[],
        expected_outcomes={},
    )

    service.get_repository_for_user = AsyncMock(return_value=repo)

    # Mock db.execute for select(RefactoringPlan)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = plan
    db.execute.return_value = exec_result

    valid_diff = "--- a/payment.py\n+++ b/payment.py\n@@ -1 +1 @@\n-old\n+new"
    valid_hash = hashlib.sha256(valid_diff.encode("utf-8")).hexdigest()

    approved_res = await service.approve_plan(
        repository_id=repo_id,
        plan_id=plan_id,
        user=user,
        db=db,
        diff_hash=valid_hash,
        notes="Approved by Tech Lead",
    )

    assert approved_res.approval_status == "APPROVED"
    assert approved_res.approved_by == str(user_id)
    assert approved_res.approved_diff_hash == valid_hash
    assert plan.execution_status == "READY"
    assert db.commit.called


@pytest.mark.asyncio
async def test_execution_diff_hash_invalidation():
    """Verify execution fails and marks plan INVALIDATED when diff hash does not match approved hash."""
    service = ArchitectureAwareRefactoringService()
    db = AsyncMock()

    plan_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    user_id = uuid.uuid4()
    approved_hash = "sha256:1111111111111111111111111111111111111111111111111111111111111111"

    user = User(id=user_id, email="actor@example.com")
    repo = Repository(id=repo_id, user_id=user_id, name="test-repo")

    plan = RefactoringPlan(
        id=plan_id,
        repository_id=repo_id,
        title="Refactor auth",
        description="Break cycle",
        category="dependency",
        risk_level="HIGH",
        risk_score=75.0,
        confidence=0.9,
        requires_human_approval=True,
        approval_status="APPROVED",
        approved_diff_hash=approved_hash,
        execution_status="READY",
        target_files=["app/auth.py"],
        target_symbols=[],
        finding_ids=[],
        affected_packages=["backend"],
        ordered_steps=[],
        recommended_tests=[],
        expected_outcomes={},
    )

    service.get_repository_for_user = AsyncMock(return_value=repo)

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = plan
    db.execute.return_value = exec_result

    altered_hash = "sha256:9999999999999999999999999999999999999999999999999999999999999999"

    with pytest.raises(BadRequestException) as exc:
        await service.execute_plan(
            repository_id=repo_id,
            plan_id=plan_id,
            user=user,
            db=db,
            diff_hash=altered_hash,
        )

    assert "does not match the approved diff hash" in str(exc.value)
    # Plan must be invalidated
    assert plan.approval_status == "INVALIDATED"
    assert plan.execution_status == "FAILED"
    assert db.commit.called


@pytest.mark.asyncio
async def test_execution_simulation_and_before_after_comparison():
    """Verify safe execution simulation, behavioral preservation metrics, and comparison endpoint."""
    service = ArchitectureAwareRefactoringService()
    db = AsyncMock()

    plan_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    user_id = uuid.uuid4()
    exec_id = uuid.uuid4()
    approved_hash = "sha256:exact_approved_hash"

    user = User(id=user_id, email="actor@example.com")
    repo = Repository(id=repo_id, user_id=user_id, name="test-repo", current_commit_sha="a1b2c3d")

    plan = RefactoringPlan(
        id=plan_id,
        repository_id=repo_id,
        title="Decompose monolith function",
        description="Extract helpers",
        category="complexity",
        risk_level="MEDIUM",
        risk_score=45.0,
        confidence=0.95,
        requires_human_approval=False,
        approval_status="APPROVED",
        approved_diff_hash=approved_hash,
        execution_status="READY",
        target_files=["app/monolith.py"],
        target_symbols=["monolith_func"],
        finding_ids=["find_1", "find_2"],
        affected_packages=["backend"],
        ordered_steps=[{"step_id": "step_1", "order_index": 1, "action": "DECOMPOSE_FUNCTION", "file_path": "app/monolith.py"}],
        recommended_tests=["test_monolith.py"],
        expected_outcomes={},
    )

    service.get_repository_for_user = AsyncMock(return_value=repo)

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = plan
    db.execute.return_value = exec_result

    # Mock debt & drift summaries
    debt_mock = MagicMock(overall_debt_score=42.0)
    drift_mock = MagicMock(total_violations=3, drift_status="DRIFT_DETECTED")
    service.debt_service.get_technical_debt_summary = AsyncMock(return_value=debt_mock)
    service.drift_service.get_drift_summary = AsyncMock(return_value=drift_mock)

    execution_res = await service.execute_plan(
        repository_id=repo_id,
        plan_id=plan_id,
        user=user,
        db=db,
        diff_hash=approved_hash,
    )

    assert execution_res.status == "COMPLETED"
    assert execution_res.baseline_tests_passed is True
    assert execution_res.post_tests_passed is True
    assert plan.execution_status == "COMPLETED"

    # Now verify get_comparison
    exec_record = RefactoringExecution(
        id=exec_id,
        plan_id=plan_id,
        repository_id=repo_id,
        status="COMPLETED",
        source_commit_sha="a1b2c3d",
        target_branch="devora/refactor/test",
        diff_content="diff",
        diff_hash="hash",
        files_changed_count=1,
        lines_added=15,
        lines_removed=10,
        baseline_tests_passed=True,
        post_tests_passed=True,
        before_metrics={"overall_debt_score": 42.0, "drift_violations_count": 3},
        after_metrics={"overall_debt_score": 26.0, "drift_violations_count": 1},
        new_violations_detected=[],
    )

    exec_result2 = MagicMock()
    exec_result2.scalar_one_or_none.return_value = exec_record
    db.execute.return_value = exec_result2

    comp_res = await service.get_comparison(
        repository_id=repo_id,
        execution_id=exec_id,
        user=user,
        db=db,
    )

    assert comp_res.debt_score_before == 42.0
    assert comp_res.debt_score_after == 26.0
    assert comp_res.debt_score_delta == -16.0
    assert comp_res.drift_violations_delta == -2
    assert comp_res.public_api_compatible is True
    assert comp_res.summary_verdict == "SUCCESSFUL_REFACTOR"


@pytest.mark.asyncio
async def test_execution_regression_triggers_automated_rollback():
    """Verify that induced test regression triggers automated rollback, preserving baseline."""
    service = ArchitectureAwareRefactoringService()

    repo_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="engineer@devora.ai")
    db = AsyncMock()

    repo = Repository(id=repo_id, name="demo-repo", user_id=user.id, current_commit_sha="a1b2c3d")
    service.get_repository_for_user = AsyncMock(return_value=repo)

    plan = RefactoringPlan(
        id=plan_id,
        repository_id=repo_id,
        title="Refactor Critical Module",
        description="Extract helpers",
        category="complexity",
        risk_level="MEDIUM",
        risk_score=50.0,
        confidence=0.9,
        requires_human_approval=True,
        approval_status="APPROVED",
        execution_status="READY",
        target_files=["backend/app/critical.py"],
        target_symbols=["handle_request"],
        finding_ids=["finding_1"],
        affected_packages=["backend"],
        ordered_steps=[{"step_id": "step_1", "action": "DECOMPOSE_FUNCTION", "file_path": "backend/app/critical.py"}],
        recommended_tests=["tests/unit/test_critical.py"],
        expected_outcomes={},
    )
    plan.approved_diff_hash = service._compute_snapshot_hash(plan)

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan
    db.execute.return_value = plan_result

    debt_mock = MagicMock(overall_debt_score=55.0)
    drift_mock = MagicMock(total_violations=4, drift_status="DRIFT_DETECTED")
    service.debt_service.get_technical_debt_summary = AsyncMock(return_value=debt_mock)
    service.drift_service.get_drift_summary = AsyncMock(return_value=drift_mock)

    # Execute with simulate_regression=True
    exec_res = await service.execute_plan(
        repository_id=repo_id,
        plan_id=plan_id,
        user=user,
        db=db,
        diff_hash=plan.approved_diff_hash,
        simulate_regression=True,
    )

    # Invariants for automated rollback
    assert exec_res.status == "ROLLED_BACK"
    assert exec_res.baseline_tests_passed is True
    assert exec_res.post_tests_passed is False
    assert exec_res.rollback_occurred is True
    assert "Automated rollback triggered" in (exec_res.rollback_reason or "")
    assert len(exec_res.newly_failed_tests) > 0
    assert plan.execution_status == "ROLLED_BACK"

