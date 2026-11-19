"""Workflow state and structured agent input/output schema contracts."""
from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Structured Pydantic Models for Agent Outputs
# ---------------------------------------------------------------------------


class OrchestratorDecision(BaseModel):
    """Decision emitted by the Orchestrator agent."""
    next_agent: str = Field(..., description="Target specialist agent to invoke or END")
    task_type: str = Field(..., description="Classified category: bug_fix, feature, refactor, exploration")
    status: str = Field(..., description="Workflow execution status")
    reasoning: str = Field(..., description="Justification for routing and decision")
    requires_human_approval: bool = Field(default=False, description="Whether human approval is required next")


class AnalysisOutput(BaseModel):
    """Output contract for Codebase Analyst agent."""
    candidate_files: List[str] = Field(default_factory=list, description="Files relevant to the task")
    key_symbols: List[str] = Field(default_factory=list, description="Function/class symbols involved")
    dependencies: List[str] = Field(default_factory=list, description="Internal and external dependencies")
    architectural_summary: str = Field(default="", description="Summary of architectural context surrounding target code")


class BugInvestigationOutput(BaseModel):
    """Output contract for Bug Investigation agent."""
    bug_category: str = Field(
        default="runtime_logic_error",
        description="Canonical category: syntax_error, import_dependency_error, type_error, attribute_null_reference_error, index_key_error, runtime_logic_error, database_network_error, permission_security_error",
    )
    root_cause: str = Field(..., description="Identified or hypothesized root cause of failure")
    trigger_condition: str = Field(..., description="Specific inputs or execution path triggering failure")
    recommended_fix_pattern: str = Field(..., description="Conceptual fix approach")
    hypotheses: List[str] = Field(default_factory=list, description="Evidence-ranked hypotheses")


class PlanStep(BaseModel):
    """Discrete step within a task implementation plan."""
    step_number: int = Field(..., description="Step sequence number")
    description: str = Field(..., description="Actionable modification or verification task")
    target_files: List[str] = Field(default_factory=list, description="Files affected by this step")
    verification_check: str = Field(default="", description="Condition or test asserting step completion")
    status: str = Field(default="PENDING", description="PENDING, IN_PROGRESS, COMPLETED, FAILED")


class TaskPlanOutput(BaseModel):
    """Output contract for Planning agent."""
    objective: str = Field(..., description="Overall technical objective of the plan")
    implementation_strategy: str = Field(default="", description="High-level engineering strategy selected for this plan")
    relevant_historical_experiences: List[str] = Field(default_factory=list, description="IDs or summaries of relevant verified past experiences")
    strategy_rationale: str = Field(default="", description="Evidence-based reasoning for selecting this strategy over alternatives")
    risks_and_assumptions: List[str] = Field(default_factory=list, description="Explicit technical risks, edge cases, and assumptions")
    steps: List[PlanStep] = Field(default_factory=list, description="Numbered implementation steps")
    test_criteria: List[str] = Field(default_factory=list, description="Acceptance criteria and tests to execute")
    risk_level: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH")


class FileEdit(BaseModel):
    """Targeted file edit instruction produced by Coding agent."""
    file_path: str = Field(..., description="Repository-relative file path")
    original_snippet: str = Field(..., description="Original code section being replaced")
    new_snippet: str = Field(..., description="New code section replacing the original")
    explanation: str = Field(..., description="Reasoning for this specific edit")
    change_type: str = Field(default="modified", description="added, modified, deleted")


class CodingOutput(BaseModel):
    """Output contract for Coding agent."""
    changes: List[FileEdit] = Field(default_factory=list, description="Proposed file modifications")
    summary_of_changes: str = Field(..., description="High-level overview of code modifications")
    diff: str = Field(default="", description="Unified git-compatible diff")


class TestRunOutput(BaseModel):
    """Output contract for Testing agent."""
    __test__ = False

    command: str = Field(..., description="Command executed inside isolated sandbox")
    exit_code: int = Field(..., description="Process exit code")
    passed: bool = Field(..., description="True if all tests passed (exit code 0)")
    total_tests: int = Field(default=0, description="Total tests discovered/run")
    passed_tests: int = Field(default=0, description="Count of passing tests")
    failed_tests: int = Field(default=0, description="Count of failing tests")
    skipped_tests: int = Field(default=0, description="Count of skipped or ignored tests")
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    raw_stdout: str = Field(default="", description="Standard output from test runner")
    raw_stderr: str = Field(default="", description="Standard error from test runner")
    failure_details: List[str] = Field(default_factory=list, description="Specific failing test assertions")

    # Multi-language discovery & execution metadata (Phase 9 Stage 9.1)
    detected_languages: List[str] = Field(default_factory=list, description="Languages discovered in repository")
    detected_frameworks: List[str] = Field(default_factory=list, description="Test frameworks detected")
    package_manager: Optional[str] = Field(default=None, description="Package manager used (npm, pip, cargo, etc.)")
    discovery_status: str = Field(default="DISCOVERED", description="DISCOVERED, UNAVAILABLE, TIMED_OUT, DISCOVERY_ERROR")
    execution_status: str = Field(default="PASSED", description="PASSED, FAILED, SKIPPED, UNAVAILABLE, TIMED_OUT")
    selected_test_files: List[str] = Field(default_factory=list, description="Test files selected for execution")
    is_targeted: bool = Field(default=False, description="True if targeted tests were run, False if full suite")
    failure_classification: Optional[str] = Field(default=None, description="ASSERTION_FAILURE, TIMEOUT, MISSING_DEPENDENCY, RUNNER_UNAVAILABLE")
    diagnostic_warning: Optional[str] = Field(default=None, description="Actionable warning or missing tool remediation guidance")

    # Flaky Test Detection & Stability Intelligence (Phase 9 Stage 9.2)
    stability_classification: Optional[str] = Field(default=None, description="STABLE_PASS, CONSISTENT_FAILURE, FLAKY, INCONCLUSIVE, UNVERIFIED")
    stability_score: Optional[float] = Field(default=None, description="Test stability percentage (0.0 - 100.0)")
    is_flaky: bool = Field(default=False, description="True if test failure was determined to be flaky/non-deterministic")
    flaky_repeat_runs: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Execution history of repeat runs")

    # Sandbox Resilience & Resource Telemetry (Phase 9 Stage 9.3)
    peak_memory_rss_bytes: Optional[int] = Field(default=None, description="Peak resident set size memory in bytes")
    peak_memory_rss_mb: Optional[float] = Field(default=None, description="Peak resident set size memory in megabytes")
    cpu_time_seconds: Optional[float] = Field(default=None, description="Total CPU time in seconds consumed by execution")
    wall_time_seconds: Optional[float] = Field(default=None, description="Precise wall-clock duration of process in seconds")
    memory_limit_bytes: Optional[int] = Field(default=None, description="Configured container memory limit in bytes")
    memory_limit_mb: Optional[float] = Field(default=None, description="Configured container memory limit in megabytes")
    cpu_limit: Optional[float] = Field(default=None, description="Configured container CPU quota in cores")
    oom_killed: bool = Field(default=False, description="True if container or process termination was confirmed OOM")
    termination_reason: Optional[str] = Field(default=None, description="Forensic reason for process or container termination")
    exit_classification: str = Field(default="EXECUTION_FAILURE", description="SUCCESS, TIMEOUT, COMMAND_NOT_EXECUTABLE, COMMAND_NOT_FOUND, OOM_KILLED, PROCESS_KILLED, RUNNER_UNAVAILABLE, EXECUTION_FAILURE")
    resource_telemetry_available: bool = Field(default=False, description="True if empirical hardware/cgroup resource metrics were captured")
    timeout_seconds: int = Field(default=60, description="Allocated execution timeout in seconds")
    timeout_scaling_reason: Optional[str] = Field(default=None, description="Scaling formula rationale if timeout was adjusted")


class CodeReviewOutput(BaseModel):
    """Output contract for Code Review agent."""
    approved: bool = Field(..., description="True if changes meet quality and convention standards")
    quality_score: int = Field(default=80, ge=0, le=100, description="Quality score (0-100)")
    comments: List[str] = Field(default_factory=list, description="Specific actionable review observations")
    suggested_refactorings: List[str] = Field(default_factory=list, description="Optional style or efficiency improvements")


class SecurityFinding(BaseModel):
    """Single security vulnerability or risk finding."""
    rule_id: str = Field(..., description="Rule or vulnerability ID (e.g., OWASP-A1, hardcoded-secret)")
    severity: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    file_path: str = Field(..., description="File where finding was identified")
    line_number: int = Field(default=1, description="Line number of finding")
    description: str = Field(..., description="Description of the risk and recommended mitigation")


class SecurityReviewOutput(BaseModel):
    """Output contract for Security Review agent."""
    passed: bool = Field(..., description="True if no high/critical vulnerabilities were identified")
    findings: List[SecurityFinding] = Field(default_factory=list, description="List of identified security findings")
    remediation_required: bool = Field(default=False, description="True if blocking security issues must be corrected")


class FinalReportOutput(BaseModel):
    """Output contract for Reporting agent."""
    title: str = Field(..., description="Descriptive title of the completed task")
    summary: str = Field(..., description="Executive summary of the resolution")
    root_cause_analysis: str = Field(default="", description="Summary of root cause if applicable")
    changes_made: List[str] = Field(default_factory=list, description="Bullet-point list of modifications")
    verification_evidence: str = Field(..., description="Empirical evidence from test execution confirming resolution")
    limitations: Optional[str] = Field(default=None, description="Known caveats, edge cases, or remaining work")
    markdown_report: str = Field(..., description="Full audit-ready Markdown engineering report")


# ---------------------------------------------------------------------------
# Strongly Typed LangGraph Workflow State
# ---------------------------------------------------------------------------


class DevoraWorkflowState(TypedDict, total=False):
    """Shared state dictionary tracked and updated across all LangGraph nodes."""
    # Identification & Tenant Metadata
    task_id: str
    user_id: str
    repository_id: str
    workspace_path: str
    commit_sha: str
    target_branch: str
    task_branch: Optional[str]
    base_branch: Optional[str]
    pull_request_url: Optional[str]
    pull_request_number: Optional[int]
    pull_request_id: Optional[str]
    git_status: Optional[Dict[str, Any]]

    # Developer Input & Categorization
    task_description: str
    task_type: str  # "bug_fix", "feature", "refactor", "exploration"
    error_traceback: Optional[str]

    # Context & Repository Intelligence
    repository_context: Dict[str, Any]
    retrieved_files: List[Dict[str, Any]]
    retrieved_symbols: List[Dict[str, Any]]
    retrieved_memories: List[Dict[str, Any]]
    memory_context_summary: str

    # Adaptive Intelligence & Experience Evidence
    historical_experiences: Optional[List[Dict[str, Any]]]
    historical_failures_to_avoid: Optional[List[Dict[str, Any]]]
    adaptive_strategy_summary: str

    # ML Classifier & Investigation
    ml_bug_prediction: Optional[Dict[str, Any]]
    problem_analysis: Optional[Dict[str, Any]]
    root_cause_analysis: Optional[Dict[str, Any]]
    implementation_plan: Optional[Dict[str, Any]]

    # Coding & Changes
    proposed_file_changes: List[Dict[str, Any]]
    applied_file_changes: List[Dict[str, Any]]
    git_diff: str

    # Verification & Testing
    test_results: Optional[Dict[str, Any]]
    test_discovery_info: Optional[Dict[str, Any]]
    flaky_test_report: Optional[Dict[str, Any]]
    last_test_stdout: Optional[str]
    last_test_stderr: Optional[str]
    last_test_exit_code: Optional[int]

    # Reviews
    review_results: Optional[Dict[str, Any]]
    security_results: Optional[Dict[str, Any]]

    # Retries & Bounded Loops
    retry_count: int
    maximum_retries: int

    # Governance & Approval
    approval_status: str  # "PENDING", "APPROVED", "REJECTED", "CHANGES_REQUESTED"
    approval_notes: Optional[str]
    execution_status: str  # "PLANNING", "IN_PROGRESS", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"

    # Execution History & Outputs
    current_agent: str
    agent_execution_history: List[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    errors: List[str]
