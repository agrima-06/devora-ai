"""GitHub Pull Request schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PullRequestResponse(BaseModel):
    """Details of a GitHub Pull Request opened by Devora AI."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    repository_id: uuid.UUID
    pr_number: int
    title: str
    body: str
    html_url: str
    head_branch: str
    base_branch: str
    state: str
    is_merged: bool
    merge_commit_sha: Optional[str] = None
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CreatePullRequestRequest(BaseModel):
    """Request payload to manually publish a PR for an approved task."""
    task_id: uuid.UUID
    installation_id: Optional[int] = None


class SyncPullRequestResponse(BaseModel):
    """Response returned upon synchronizing PR state from GitHub."""
    success: bool
    message: str
    pull_request: PullRequestResponse
