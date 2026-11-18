"""Task schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskPlanStepSchema(BaseModel):
    step_number: int
    description: str
    target_files: List[str] = Field(default_factory=list)
    verification_check: Optional[str] = None
    status: str = "PENDING"


class TaskPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    test_criteria: List[Any] = Field(default_factory=list)
    risk_level: str
    created_at: datetime


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    repository_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1)
    error_traceback: Optional[str] = None
    task_type: str = Field(default="bug_fix", max_length=50)
    target_branch: str = Field(default="main", max_length=255)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = None
    pull_request_url: Optional[str] = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    repository_id: uuid.UUID
    created_by: uuid.UUID
    title: str
    prompt: str
    error_traceback: Optional[str] = None
    task_type: str
    status: str
    iterations_count: int
    target_branch: str
    pull_request_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskDetailResponse(TaskResponse):
    plans: List[TaskPlanResponse] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    agent_name: str
    step_number: int
    output_state: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: int
    created_at: datetime


class FileChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    file_path: str
    change_type: str
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff: str
    created_at: datetime


class TestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    iteration: int
    command: str
    exit_code: int
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_seconds: float
    created_at: datetime


class StartWorkflowResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    message: str
