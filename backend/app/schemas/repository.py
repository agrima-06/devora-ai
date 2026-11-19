"""Repository schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    clone_url: str = Field(..., min_length=1)
    default_branch: str = Field(default="main", max_length=100)
    language: Optional[str] = Field(None, max_length=100)
    meta_info: Dict[str, Any] = Field(default_factory=dict)


class RepositoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    default_branch: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    full_name: str
    clone_url: str
    default_branch: str
    language: Optional[str] = None
    installation_id: Optional[int] = None
    is_private: bool = False
    permissions: Dict[str, Any] = Field(default_factory=dict)
    current_commit_sha: Optional[str] = None
    indexing_status: str = "NOT_INDEXED"
    last_indexed_at: Optional[datetime] = None
    meta_info: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RepositorySyncResponse(BaseModel):
    repository_id: uuid.UUID
    status: str
    message: str


class IndexRepositoryRequest(BaseModel):
    branch: Optional[str] = None
    force_reindex: bool = False


class IndexingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    branch: str
    status: str
    files_count: int
    symbols_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class RepositoryFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    file_path: str
    language: Optional[str] = None
    size_bytes: int
    lines_count: int
    commit_sha: str
    summary: Optional[str] = None
    meta_info: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")


class RepositorySymbolResponse(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None


class RepositoryArchitectureResponse(BaseModel):
    repository_id: uuid.UUID
    primary_language: Optional[str] = None
    current_commit_sha: Optional[str] = None
    frameworks: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    manifests: List[str] = Field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    architecture_summary: str = ""
    coding_conventions: str = ""


class CodeSearchResultItem(BaseModel):
    file_path: str
    match_type: str
    line_number: Optional[int] = None
    snippet: str
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    score: float = 1.0


class CodeSearchResponse(BaseModel):
    repository_id: uuid.UUID
    query: str
    search_type: str
    results: List[CodeSearchResultItem]
    total_matches: int
