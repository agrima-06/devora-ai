"""Workflow Recovery and Resumption schemas (Phase 9 Stage 9.4)."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskResumeRequest(BaseModel):
    """Request payload to resume an interrupted task."""
    force: bool = Field(default=False, description="Force resumption even if max attempts reached or marked failed")
    custom_branch: Optional[str] = Field(default=None, description="Optional custom branch override")


class CheckpointSummary(BaseModel):
    """Summary of a persisted workflow checkpoint."""
    checkpoint_id: str
    node_name: Optional[str] = None
    step_number: int
    thread_id: str
    created_at: Optional[datetime] = None


class TaskResumeResponse(BaseModel):
    """Response returned upon initiating task resumption."""
    task_id: str
    status: str
    recovery_status: str
    resumed_from_node: str
    step_number: int
    recovery_attempts: int
    message: str


class TaskRecoveryStatusResponse(BaseModel):
    """Detailed recovery diagnostics and eligibility for a specific task."""
    task_id: str
    status: str
    recovery_status: str
    is_interrupted: bool
    interruption_reason: Optional[str] = None
    is_eligible_for_recovery: bool
    eligibility_reason: str
    recovery_attempts: int
    max_recovery_attempts: int
    last_heartbeat_at: Optional[datetime] = None
    recovery_lease_owner: Optional[str] = None
    recovery_lease_expires_at: Optional[datetime] = None
    recovery_error: Optional[str] = None
    latest_checkpoint: Optional[CheckpointSummary] = None


class InterruptedTaskItem(BaseModel):
    """Summary of an interrupted task identified by recovery scan."""
    task_id: str
    title: str
    status: str
    recovery_status: str
    interruption_reason: str
    eligible: bool
    recovery_attempts: int
    last_heartbeat_at: Optional[datetime] = None
    latest_node: Optional[str] = None


class InterruptedTaskScanResponse(BaseModel):
    """Response containing list of all interrupted tasks detected."""
    scanned_tasks_count: int
    interrupted_tasks: List[InterruptedTaskItem] = Field(default_factory=list)
