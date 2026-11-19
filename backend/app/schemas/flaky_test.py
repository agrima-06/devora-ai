"""Pydantic schemas for Flaky Test Detection records and stability intelligence."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FlakyTestRecordResponse(BaseModel):
    """Normalized response schema for a persisted flaky test record."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    task_id: uuid.UUID
    test_identifier: str
    test_file: str
    framework: str
    language: str
    test_command: str
    classification: str  # STABLE_PASS, CONSISTENT_FAILURE, FLAKY, INCONCLUSIVE, UNVERIFIED
    stability_score: float
    total_runs: int
    passed_runs: int
    failed_runs: int
    infrastructure_error_runs: int
    timeout_runs: int
    execution_history: Dict[str, Any]
    first_detected_at: datetime
    last_detected_at: datetime
    last_verified_at: datetime
    created_at: datetime


class RepositoryStabilitySummaryResponse(BaseModel):
    """Aggregated repository-level test stability statistics."""
    repository_id: str
    total_tests_tracked: int
    flaky_tests_count: int
    stable_pass_count: int
    consistent_failure_count: int
    average_stability_score: float
    total_repeat_runs_executed: int
