"""RepositoryTechnicalDebt database model."""

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryTechnicalDebt(Base, UUIDMixin, TimestampMixin):
    """Represents a quantitative technical debt measurement and findings snapshot for a repository."""
    __tablename__ = "repository_technical_debt"

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
    overall_debt_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="CLEAN",
    )  # CRITICAL, HIGH, MEDIUM, LOW, CLEAN
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    dimension_scores: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    summary_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    findings: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="technical_debts")
