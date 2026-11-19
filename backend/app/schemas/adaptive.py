"""Pydantic schemas for Phase 7: Adaptive Engineering Intelligence."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EngineeringExperienceResponse(BaseModel):
    """Schema for returning structured engineering experiences."""
    id: uuid.UUID
    repository_id: Optional[uuid.UUID] = None
    task_category: str
    bug_category: Optional[str] = None
    problem_summary: str
    root_cause: str
    resolution_strategy: str
    diff_patch: str
    status_type: str = "verified_successful"
    technology_stack: List[str] = Field(default_factory=list)
    files_involved: List[str] = Field(default_factory=list)
    attempts_count: int = 1
    failed_approaches: List[Dict[str, Any]] = Field(default_factory=list)
    successful_approach: Optional[str] = None
    test_results: Dict[str, Any] = Field(default_factory=dict)
    review_findings: Dict[str, Any] = Field(default_factory=dict)
    security_findings: Dict[str, Any] = Field(default_factory=dict)
    failure_type: Optional[str] = None
    is_verified: bool = False
    is_anonymized: bool = False
    quality_score: int = 0
    commit_sha: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperienceSearchQuery(BaseModel):
    """Query schema for semantic experience retrieval."""
    query: str = Field(..., description="Problem description, traceback, or task prompt")
    task_category: Optional[str] = None
    bug_category: Optional[str] = None
    technology_stack: Optional[List[str]] = None
    status_type: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.15, ge=0.0, le=1.0)


class ExperienceSearchResult(BaseModel):
    """Ranked experience search result with similarity and weighted confidence."""
    id: uuid.UUID
    task_category: str
    bug_category: Optional[str]
    problem_summary: str
    root_cause: str
    resolution_strategy: str
    status_type: str
    technology_stack: List[str]
    files_involved: List[str]
    similarity: float
    weighted_score: float
    is_positive_guidance: bool  # True if verified_successful, False if verified_failed


class TaskFailureRecordCreate(BaseModel):
    """Schema for recording an engineering task failure."""
    task_id: uuid.UUID
    stage: str = Field(..., description="TESTING, CODE_REVIEW, SECURITY_AUDIT, DEVELOPER_REVIEW")
    failure_type: str = Field(..., description="INCORRECT_ASSUMPTION, IMPLEMENTATION_DEFECT, DEPENDENCY_ISSUE, ENVIRONMENT_PROBLEM")
    attempt_number: int = 1
    failed_strategy: str
    error_log: str = ""
    review_notes: Optional[str] = None
    lessons_learned: str


class TaskFailureRecordResponse(BaseModel):
    """Schema for returning failure analysis records."""
    id: uuid.UUID
    task_id: uuid.UUID
    stage: str
    failure_type: str
    attempt_number: int
    failed_strategy: str
    error_log: str
    review_notes: Optional[str]
    lessons_learned: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentPerformanceMetric(BaseModel):
    """Performance telemetry for a single specialist agent."""
    agent_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    average_duration_ms: float
    retry_frequency: float
    rejection_rate: float
    estimated_tokens_used: int
    estimated_cost_usd: float


class AgentPerformanceResponse(BaseModel):
    """Aggregated agent performance telemetry across all 9 agents."""
    agents: List[AgentPerformanceMetric]
    total_tasks_evaluated: int
    overall_first_pass_rate: float
    average_task_duration_seconds: float
    categories_breakdown: Dict[str, Dict[str, Any]]


class BenchmarkDefinitionResponse(BaseModel):
    """Schema for benchmark specifications."""
    id: str
    name: str
    category: str
    description: str
    initial_repo_snapshot: str
    expected_outcomes: Dict[str, Any]
    evaluation_criteria: Dict[str, Any]
    baseline_pass_rate: float

    model_config = ConfigDict(from_attributes=True)


class BenchmarkRunResponse(BaseModel):
    """Schema for historical benchmark run outcomes."""
    id: uuid.UUID
    benchmark_id: str
    system_version: str
    model_version: str
    task_completed: bool
    tests_passed: bool
    retries_count: int
    planning_efficiency_score: float
    execution_time_ms: int
    tokens_used: int
    estimated_cost_usd: float
    review_passed: bool
    metrics: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchmarkExecutionRequest(BaseModel):
    """Request to trigger benchmark evaluations."""
    benchmark_id: Optional[str] = Field(default=None, description="Run specific benchmark ID or all if omitted")
    system_version: str = Field(default="v1.0.0")
    model_version: str = Field(default="gemini-1.5-pro")


class BenchmarkSummaryResponse(BaseModel):
    """Aggregated benchmark suite results."""
    system_version: str
    total_benchmarks: int
    tasks_completed_count: int
    completion_rate: float
    tests_passed_count: int
    test_pass_rate: float
    average_retries: float
    average_execution_time_ms: float
    total_estimated_cost_usd: float
    runs: List[BenchmarkRunResponse]


class AdaptiveFeedbackCreate(BaseModel):
    """Structured developer feedback for adaptive learning."""
    task_id: uuid.UUID
    rating: str = Field(..., description="ACCEPTED, REJECTED, NEEDS_CHANGES")
    plan_accepted: bool = True
    code_accepted: bool = True
    solution_helpful: bool = True
    comments: Optional[str] = None


class AdaptiveFeedbackResponse(BaseModel):
    """Feedback submission confirmation."""
    id: uuid.UUID
    task_id: uuid.UUID
    rating: str
    solution_accepted: bool
    quality_score_delta: int
    message: str
