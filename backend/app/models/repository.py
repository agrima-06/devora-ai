"""Repository database model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project
    from app.models.task import Task
    from app.models.repository_knowledge import RepositoryKnowledge
    from app.models.indexing_job import IndexingJob
    from app.models.repository_file import RepositoryFile
    from app.models.repository_memory import RepositoryMemory
    from app.models.github_installation import GitHubInstallation
    from app.models.github_pull_request import GitHubPullRequest
    from app.models.git_branch import GitBranch
    from app.models.flaky_test_record import FlakyTestRecord


class Repository(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "repositories"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("github_installations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    github_repo_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    clone_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    meta_info: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_commit_sha: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    indexing_status: Mapped[str] = mapped_column(String(50), default="NOT_INDEXED", nullable=False)
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="repositories")
    user: Mapped["User"] = relationship("User", back_populates="repositories")
    installation: Mapped[Optional["GitHubInstallation"]] = relationship("GitHubInstallation", back_populates="repositories")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="repository", cascade="all, delete-orphan")
    knowledge_entries: Mapped[List["RepositoryKnowledge"]] = relationship("RepositoryKnowledge", back_populates="repository", cascade="all, delete-orphan")
    indexing_jobs: Mapped[List["IndexingJob"]] = relationship("IndexingJob", back_populates="repository", cascade="all, delete-orphan")
    indexed_files: Mapped[List["RepositoryFile"]] = relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")
    memories: Mapped[List["RepositoryMemory"]] = relationship("RepositoryMemory", back_populates="repository", cascade="all, delete-orphan")
    pull_requests: Mapped[List["GitHubPullRequest"]] = relationship("GitHubPullRequest", back_populates="repository", cascade="all, delete-orphan")
    git_branches: Mapped[List["GitBranch"]] = relationship("GitBranch", back_populates="repository", cascade="all, delete-orphan")
    flaky_tests: Mapped[List["FlakyTestRecord"]] = relationship("FlakyTestRecord", back_populates="repository", cascade="all, delete-orphan")
