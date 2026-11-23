"""Pydantic schemas for Phase 10 Stage 10.7: Benchmark Engine."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BenchmarkScenarioCreate(BaseModel):
    """Schema to register or seed an evaluation benchmark scenario."""
    scenario_key: str = Field(..., description="Unique scenario identifier, e.g. scenario_a1_null_deref")
    category: str = Field(..., description="Canonical category: bug_detection, repo_understanding, arch_intelligence, impact_analysis, refactoring, multi_agent, security_safety")
    name: str = Field(..., description="Human-readable scenario name")
    description: str = Field(default="", description="Detailed scenario task description")
    difficulty: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    eval_type: str = Field(default="EXACT_MATCH", description="EXACT_MATCH, STRUCTURAL, AST_DELTA, TEST_ASSERTION, SECURITY_POLICY")
    input_context: Dict[str, Any] = Field(default_factory=dict, description="Scenario input payload, repository context, task prompt")
    expected_output: Dict[str, Any] = Field(default_factory=dict, description="Ground truth assertions and outcomes")
    evaluation_criteria: Dict[str, Any] = Field(default_factory=dict, description="Scoring criteria, weights, invariants")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")


class BenchmarkScenarioResponse(BaseModel):
    """Representation of an evaluation benchmark scenario."""
    id: str
    scenario_key: str
    category: str
    name: str
    description: str
    difficulty: str
    eval_type: str
    input_context: Dict[str, Any] = Field(default_factory=dict)
    expected_output: Dict[str, Any] = Field(default_factory=dict)
    evaluation_criteria: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    version: int
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class BenchmarkScenariosListResponse(BaseModel):
    """List of registered benchmark scenarios."""
    total_count: int
    category_counts: Dict[str, int] = Field(default_factory=dict)
    scenarios: List[BenchmarkScenarioResponse] = Field(default_factory=list)


class BenchmarkSuiteRunRequest(BaseModel):
    """Request payload to initiate a benchmark suite execution."""
    model_name: str = Field(default="gemini-1.5-pro", description="Model identifier to evaluate")
    suite_name: str = Field(default="devora_core_intelligence_suite", description="Benchmark suite name")
    code_revision: Optional[str] = Field(default=None, description="Git commit SHA or version string")
    categories: Optional[List[str]] = Field(default=None, description="Optional category filters, e.g. ['bug_detection', 'security_safety']")
    scenario_keys: Optional[List[str]] = Field(default=None, description="Optional specific scenario keys to execute")
    simulate_safety_failure: bool = Field(default=False, description="Simulate critical safety failure to verify override behavior")


class BenchmarkScenarioResultResponse(BaseModel):
    """Outcome of an individual scenario execution within a suite run."""
    result_id: str
    run_id: str
    scenario_id: str
    scenario_key: str
    category: str
    name: str
    status: str = Field(..., description="PASSED, FAILED, TIMEOUT, ERROR, SAFETY_VIOLATION")
    score: float = Field(..., ge=0.0, le=100.0, description="Normalized score (0-100)")
    actual_output: Dict[str, Any] = Field(default_factory=dict)
    expected_output: Dict[str, Any] = Field(default_factory=dict)
    diff_summary: Optional[str] = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    confidence_score: Optional[float] = None
    invariants_met: bool = True
    safety_violated: bool = False
    failure_reason: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class BenchmarkSuiteRunResponse(BaseModel):
    """Summary of a completed or running benchmark suite execution."""
    run_id: str
    suite_name: str
    model_name: str
    code_revision: Optional[str] = None
    dataset_version: str
    status: str = Field(..., description="PENDING, RUNNING, COMPLETED, FAILED, CRITICAL_SAFETY_FAILURE, CANCELLED")
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    critical_safety_failure: bool
    aggregate_score: float = Field(..., ge=0.0, le=100.0)
    category_scores: Dict[str, float] = Field(default_factory=dict)
    calibration_error: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    token_usage_total: int = 0
    cost_estimate_usd: float = 0.0
    created_at: str
    completed_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BenchmarkSuiteRunDetailResponse(BenchmarkSuiteRunResponse):
    """Detailed benchmark suite execution containing all individual scenario outcomes."""
    results: List[BenchmarkScenarioResultResponse] = Field(default_factory=list)


class BenchmarkSuiteRunsListResponse(BaseModel):
    """Paginated list of benchmark suite runs."""
    total_count: int
    runs: List[BenchmarkSuiteRunResponse] = Field(default_factory=list)


class BenchmarkRegressionResponse(BaseModel):
    """Identified regression item between two benchmark executions."""
    regression_id: str
    baseline_run_id: str
    target_run_id: str
    scenario_id: str
    scenario_key: str
    category: str
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    baseline_score: float
    target_score: float
    score_delta: float
    percentage_change: float
    description: str
    regression_type: str = Field(..., description="ACCURACY_DROP, LATENCY_SPIKE, SAFETY_BREACH, INVARIANT_FAILURE")
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class BenchmarkRunComparisonRequest(BaseModel):
    """Request to compare two benchmark runs."""
    baseline_run_id: str = Field(..., description="Baseline run ID")
    target_run_id: str = Field(..., description="Target run ID to compare against baseline")
    regression_threshold: float = Field(default=5.0, description="Minimum drop in points to flag regression")


class BenchmarkRunComparisonResponse(BaseModel):
    """Direct comparative delta between two benchmark runs."""
    baseline_run_id: str
    target_run_id: str
    baseline_model: str
    target_model: str
    baseline_score: float
    target_score: float
    score_delta: float
    percentage_change: float
    category_deltas: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    latency_delta_ms: float = 0.0
    cost_delta_usd: float = 0.0
    regressions_count: int = 0
    critical_regressions: int = 0
    regressions: List[BenchmarkRegressionResponse] = Field(default_factory=list)
    summary_verdict: str = Field(..., description="IMPROVED, REGRESSED, PARITY, CRITICAL_SAFETY_BREACH")


class BenchmarkReportResponse(BaseModel):
    """Exportable, audit-ready markdown benchmark report."""
    run_id: str
    title: str
    generated_at: str
    markdown_content: str
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
