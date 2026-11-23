"""RefactoringPlan database model for Phase 10 Stage 10.6."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.refactoring_execution import RefactoringExecution
    from app.models.user import User


class RefactoringPlan(Base, UUIDMixin, TimestampMixin):
    """Represents a structured, ordered refactoring plan addressing architectural drift or debt."""
    __tablename__ = "repository_refactoring_plans"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_revision: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # layering, dependency, duplication, complexity, convention, testability
    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="LOW",
    )  # LOW, MEDIUM, HIGH
    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    requires_human_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    approval_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )  # PENDING, APPROVED, REJECTED, EXPIRED, INVALIDATED
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_diff_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    execution_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DRAFT",
        index=True,
    )  # DRAFT, READY, EXECUTING, COMPLETED, FAILED, ROLLED_BACK

    target_files: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    target_symbols: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    finding_ids: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    affected_packages: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    ordered_steps: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    recommended_tests: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    expected_outcomes: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="refactoring_plans",
    )
    executions: Mapped[List["RefactoringExecution"]] = relationship(
        "RefactoringExecution",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
