"""RepositoryArchitectureDrift database model."""

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryArchitectureDrift(Base, UUIDMixin, TimestampMixin):
    """Represents an architectural drift analysis snapshot comparing current state to baseline."""
    __tablename__ = "repository_architecture_drift"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commit_sha: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    baseline_commit_sha: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    drift_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="HEALTHY",
    )  # HEALTHY, DRIFT_DETECTED, CRITICAL_DRIFT
    total_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    critical_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    high_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    medium_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    low_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    violations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    resolved_violations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    summary: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="architecture_drifts")
