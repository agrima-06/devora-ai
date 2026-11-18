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
    bug_category: str = Field(default="LogicError", description="Category or taxonomy of the bug")
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
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    raw_stdout: str = Field(default="", description="Standard output from test runner")
    raw_stderr: str = Field(default="", description="Standard error from test runner")
    failure_details: List[str] = Field(default_factory=list, description="Specific failing test assertions")


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

    # Developer Input & Categorization
    task_description: str
    task_type: str  # "bug_fix", "feature", "refactor", "exploration"
    error_traceback: Optional[str]

    # Context & Repository Intelligence
    repository_context: Dict[str, Any]
    retrieved_files: List[Dict[str, Any]]
    retrieved_symbols: List[Dict[str, Any]]

    # Investigation & Planning
    problem_analysis: Optional[Dict[str, Any]]
    root_cause_analysis: Optional[Dict[str, Any]]
    implementation_plan: Optional[Dict[str, Any]]

    # Coding & Changes
    proposed_file_changes: List[Dict[str, Any]]
    applied_file_changes: List[Dict[str, Any]]
    git_diff: str

    # Verification & Testing
    test_results: Optional[Dict[str, Any]]
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
