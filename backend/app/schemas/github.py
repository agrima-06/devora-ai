"""GitHub App, installation, and Git branch schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GitHubStatusResponse(BaseModel):
    """Configuration and connectivity status of the GitHub App integration."""
    app_configured: bool
    app_id: Optional[str] = None
    has_private_key: bool
    is_mock: bool


class GitHubInstallationResponse(BaseModel):
    """Metadata for an authorized GitHub App installation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    installation_id: int
    account_login: str
    account_type: str
    repository_selection: str
    permissions: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GitHubInstallationConnectRequest(BaseModel):
    """Payload to connect an installed GitHub App instance."""
    installation_id: int
    account_login: Optional[str] = None
    account_type: str = "User"
    repository_selection: str = "selected"
    permissions: Dict[str, Any] = Field(default_factory=dict)


class GitHubRepositoryItem(BaseModel):
    """Remote repository accessible via an authorized GitHub installation."""
    id: int
    name: str
    full_name: str
    private: bool
    clone_url: str
    default_branch: str
    language: Optional[str] = None
    permissions: Dict[str, bool] = Field(default_factory=dict)


class GitBranchResponse(BaseModel):
    """Branch tracked for a task and repository."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    repository_id: uuid.UUID
    branch_name: str
    base_branch: str
    commit_sha: Optional[str] = None
    is_pushed: bool
    pushed_at: Optional[datetime] = None
    created_at: datetime
