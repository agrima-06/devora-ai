"""Pydantic schemas for semantic vector memories and feedback."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

MemoryCategory = Literal[
    "architecture",
    "coding_conventions",
    "naming_conventions",
    "framework_usage",
    "module_relationships",
    "testing_patterns",
    "common_errors",
    "engineering_decisions",
    "task_outcome",
]

VerificationStatus = Literal[
    "observed_fact",
    "ai_hypothesis",
    "developer_confirmed",
    "verified_outcome",
]


class MemoryBase(BaseModel):
    category: str = Field(..., description="Category of engineering memory")
    title: Optional[str] = Field(None, max_length=255, description="Short summary title")
    content: str = Field(..., description="Descriptive knowledge content or convention rule")
    source_reference: Optional[str] = Field(None, max_length=255, description="File path, symbol, or task reference")
    commit_sha: Optional[str] = Field(None, max_length=40, description="Commit SHA where observed")
    verification_status: str = Field(default="observed_fact", description="Verification confidence status")
    access_scope: str = Field(default="repository", description="Scope: repository, project, or tenant")


class MemoryCreate(MemoryBase):
    meta_info: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    verification_status: Optional[str] = None
    is_stale: Optional[bool] = None
    stale_reason: Optional[str] = None


class MemoryResponse(MemoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    is_stale: bool
    stale_reason: Optional[str] = None
    helpful_count: int
    unhelpful_count: int
    meta_info: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class MemorySearchQuery(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search prompt or query")
    category: Optional[str] = Field(None, description="Optional category filter")
    verification_status: Optional[str] = Field(None, description="Optional verification filter")
    include_stale: bool = Field(default=False, description="Whether to include stale memories")
    limit: int = Field(default=5, ge=1, le=50, description="Max results to return")
    threshold: Optional[float] = Field(default=0.15, ge=0.0, le=1.0, description="Minimum cosine similarity")


class MemorySearchResult(BaseModel):
    id: str
    repository_id: str
    category: str
    title: Optional[str]
    content: str
    source_reference: Optional[str]
    commit_sha: Optional[str]
    verification_status: str
    is_stale: bool
    stale_reason: Optional[str]
    helpful_count: int
    unhelpful_count: int
    raw_similarity: float
    score: float
    created_at: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryFeedbackCreate(BaseModel):
    is_helpful: bool = Field(..., description="Whether this retrieved memory helped complete the task")
    notes: Optional[str] = Field(None, description="Developer feedback or correction notes")
    task_id: Optional[uuid.UUID] = Field(None, description="Optional associated task ID")


class MemoryFeedbackResponse(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    user_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    is_helpful: bool
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryStatsResponse(BaseModel):
    repository_id: str
    total_memories: int
    verified_count: int
    stale_count: int
    categories: Dict[str, int]
    verification_statuses: Dict[str, int]
