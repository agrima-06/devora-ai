"""RefactoringExecution database model for Phase 10 Stage 10.6."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.refactoring_plan import RefactoringPlan
    from app.models.repository import Repository


class RefactoringExecution(Base, UUIDMixin, TimestampMixin):
    """Represents an isolated execution attempt of an approved refactoring plan."""
    __tablename__ = "refactoring_executions"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repository_refactoring_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )  # PENDING, IN_PROGRESS, VALIDATING, COMPLETED, FAILED, ROLLED_BACK

    source_commit_sha: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    target_branch: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    diff_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    diff_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    files_changed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    lines_added: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    lines_removed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    baseline_tests_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    post_tests_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    tests_executed: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    before_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    after_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    new_violations_detected: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    plan: Mapped["RefactoringPlan"] = relationship(
        "RefactoringPlan",
        back_populates="executions",
    )
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="refactoring_executions",
    )
