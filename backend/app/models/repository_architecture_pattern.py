"""RepositoryArchitecturePattern database model."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryArchitecturePattern(Base, UUIDMixin, TimestampMixin):
    """Represents an inferred architectural pattern or engineering convention for a repository."""
    __tablename__ = "repository_architecture_patterns"
    __table_args__ = (
        UniqueConstraint("repository_id", "pattern_id", name="uq_repo_architecture_pattern"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pattern_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # e.g. service_layer, layered_architecture, modular_monolith
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # application, backend, frontend, ai_agent, data
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    evidence_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # CONFIRMED, STRONGLY_SUPPORTED, POSSIBLE, INSUFFICIENT_EVIDENCE
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    supporting_files: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    supporting_symbols: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    supporting_relationships: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    supporting_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    counterexamples: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    conventions: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    analysis_version: Mapped[str] = mapped_column(
        String(50),
        default="1.0.0",
        nullable=False,
    )
    commit_sha: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="architecture_patterns")
