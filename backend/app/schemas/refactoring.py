"""Pydantic schemas for Phase 10 Stage 10.6: Architecture-Aware Refactoring & Safe Remediation Engine."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RefactoringRecommendationItem(BaseModel):
    """Specific evidence-grounded refactoring recommendation."""
    recommendation_id: str = Field(..., description="Unique recommendation ID (e.g. rec_layer_12345678)")
    category: str = Field(..., description="layering, dependency, duplication, complexity, convention, testability")
    title: str = Field(..., description="Human-readable title of the refactoring proposal")
    finding_ids: List[str] = Field(default_factory=list, description="IDs of originating drift or technical debt findings")
    target_files: List[str] = Field(default_factory=list, description="Primary files to be modified or created")
    target_symbols: List[str] = Field(default_factory=list, description="Primary symbols (functions/classes) targeted")
    current_problem: str = Field(..., description="Concrete architectural problem grounded in repository evidence")
    proposed_architecture: str = Field(..., description="Target architectural design and patterns to establish")
    reason: str = Field(..., description="Engineering rationale for why this refactoring improves codebase health")
    expected_benefits: List[str] = Field(default_factory=list, description="Concrete benefits (e.g. decouples layer, breaks cycle)")
    potential_risks: List[str] = Field(default_factory=list, description="Potential risks or regressions to safeguard against")
    affected_packages: List[str] = Field(default_factory=list, description="Monorepo packages impacted by this change")
    dependency_path_evidence: List[str] = Field(default_factory=list, description="Supporting dependency hops from graph")
    recommended_tests: List[str] = Field(default_factory=list, description="Targeted test files to validate before & after")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the recommendation grounded in evidence")
    estimated_complexity: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH")
    requires_human_approval: bool = Field(default=False, description="Whether plan requires explicit human sign-off")


class RefactoringRecommendationsResponse(BaseModel):
    """List of evidence-backed refactoring recommendations for a repository."""
    repository_id: str
    total_recommendations: int
    recommendations: List[RefactoringRecommendationItem]


class RefactoringStepItem(BaseModel):
    """Granular, ordered step within an engineering refactoring plan."""
    step_id: str = Field(..., description="Unique step ID within plan")
    order_index: int = Field(..., description="1-based execution order index")
    action: str = Field(..., description="EXTRACT_SERVICE, BREAK_CYCLE, DECOMPOSE_FUNCTION, CONSOLIDATE_DUPLICATE, ALIGN_NAMING, ADD_TEST")
    file_path: str = Field(..., description="Target file path for this step")
    target_symbols: List[str] = Field(default_factory=list, description="Target functions, classes, or modules")
    description: str = Field(..., description="Precise instruction for the refactoring action")
    code_transform_prompt: Optional[str] = Field(default=None, description="Detailed transformation instruction for coder agent")
    dependency_constraints: List[str] = Field(default_factory=list, description="Prerequisite step IDs or symbol dependencies")


class RefactoringPlanCreateRequest(BaseModel):
    """Request payload to synthesize a structured refactoring plan from recommendations."""
    recommendation_ids: List[str] = Field(..., min_length=1, description="List of recommendation IDs to combine into plan")
    title: Optional[str] = Field(default=None, description="Custom plan title")
    description: Optional[str] = Field(default=None, description="Custom plan description")


class RefactoringPlanResponse(BaseModel):
    """Complete, ordered refactoring plan with risk assessment and approval state."""
    plan_id: str
    repository_id: str
    source_revision: Optional[str] = None
    title: str
    description: str
    category: str
    risk_level: str = Field(..., description="LOW, MEDIUM, HIGH")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Calculated implementation risk score (0-100)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Grounding confidence")
    requires_human_approval: bool
    approval_status: str = Field(..., description="PENDING, APPROVED, REJECTED, EXPIRED, INVALIDATED")
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approved_diff_hash: Optional[str] = None
    execution_status: str = Field(..., description="DRAFT, READY, EXECUTING, COMPLETED, FAILED, ROLLED_BACK")
    target_files: List[str] = Field(default_factory=list)
    target_symbols: List[str] = Field(default_factory=list)
    finding_ids: List[str] = Field(default_factory=list)
    affected_packages: List[str] = Field(default_factory=list)
    ordered_steps: List[RefactoringStepItem] = Field(default_factory=list)
    recommended_tests: List[str] = Field(default_factory=list)
    expected_outcomes: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class RefactoringPlansListResponse(BaseModel):
    """Paginated or listed refactoring plans."""
    repository_id: str
    total_count: int
    plans: List[RefactoringPlanResponse]


class RefactoringApproveRequest(BaseModel):
    """Request payload to approve a refactoring plan, cryptographically binding to diff hash."""
    diff_hash: Optional[str] = Field(default=None, description="SHA-256 hash of the previewed diff to bind approval to")
    notes: Optional[str] = Field(default=None, description="Reviewer notes or approval rationale")


class RefactoringExecuteRequest(BaseModel):
    """Request payload to initiate execution of an approved refactoring plan."""
    diff_hash: Optional[str] = Field(default=None, description="SHA-256 diff hash for replay / tamper protection")
    dry_run: bool = Field(default=False, description="Simulate execution without writing final working tree")
    simulate_regression: bool = Field(default=False, description="Simulate a test suite regression to trigger and verify automated rollback")


class RefactoringExecutionResponse(BaseModel):
    """Record of an isolated refactoring execution and behavioral preservation outcome."""
    execution_id: str
    plan_id: str
    repository_id: str
    status: str = Field(..., description="PENDING, IN_PROGRESS, VALIDATING, COMPLETED, FAILED, ROLLED_BACK")
    source_commit_sha: Optional[str] = None
    target_branch: Optional[str] = None
    diff_content: Optional[str] = Field(default=None, description="Sanitized unified diff")
    diff_hash: Optional[str] = Field(default=None, description="SHA-256 hash of diff_content")
    files_changed_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    baseline_tests_passed: bool = True
    post_tests_passed: bool = True
    tests_executed: List[str] = Field(default_factory=list)
    passed_test_ids_before: List[str] = Field(default_factory=list, description="Explicit test identifiers passing in baseline")
    passed_test_ids_after: List[str] = Field(default_factory=list, description="Explicit test identifiers passing after refactoring")
    newly_failed_tests: List[str] = Field(default_factory=list, description="Tests that passed before but failed after refactoring")
    removed_tests: List[str] = Field(default_factory=list, description="Tests removed during refactoring")
    test_coverage_delta: float = Field(default=0.0, description="Change in test coverage percentage")
    rollback_occurred: bool = Field(default=False, description="True if automatic rollback was executed due to regression")
    rollback_reason: Optional[str] = Field(default=None, description="Detailed explanation if rollback occurred")
    before_metrics: Dict[str, Any] = Field(default_factory=dict)
    after_metrics: Dict[str, Any] = Field(default_factory=dict)
    new_violations_detected: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class BeforeAfterComparisonResponse(BaseModel):
    """Direct comparative assessment between baseline and post-refactoring state."""
    plan_id: str
    execution_id: str
    repository_id: str
    debt_score_before: float
    debt_score_after: float
    debt_score_delta: float
    drift_violations_before: int
    drift_violations_after: int
    drift_violations_delta: int
    public_api_compatible: bool
    tests_baseline_passed: bool
    tests_post_passed: bool
    passed_test_ids_before: List[str] = Field(default_factory=list)
    passed_test_ids_after: List[str] = Field(default_factory=list)
    newly_failed_tests: List[str] = Field(default_factory=list)
    rollback_occurred: bool = False
    rollback_reason: Optional[str] = None
    new_violations: List[Dict[str, Any]] = Field(default_factory=list)
    summary_verdict: str = Field(..., description="SUCCESSFUL_REFACTOR, BEHAVIOR_CHANGED, REGRESSION_DETECTED, ROLLED_BACK")
