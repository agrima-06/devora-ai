"""RepositoryMemory database model for project conventions and engineering knowledge."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin, VectorType

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.memory_feedback import MemoryFeedback


class RepositoryMemory(Base, UUIDMixin, TimestampMixin):
    """Semantic vector memory unit capturing project conventions, decisions, and patterns."""
    __tablename__ = "repository_memories"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        # categories: 'architecture', 'coding_conventions', 'naming_conventions',
        # 'framework_usage', 'module_relationships', 'testing_patterns',
        # 'common_errors', 'engineering_decisions', 'task_outcome'
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(VectorType(768), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # Verification status: 'observed_fact', 'ai_hypothesis', 'developer_confirmed', 'verified_outcome'
    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="observed_fact",
        nullable=False,
        index=True,
    )
    # Scope: 'repository', 'project', 'tenant'
    access_scope: Mapped[str] = mapped_column(String(50), default="repository", nullable=False)

    # Lifecycle & feedback
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    stale_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unhelpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_info: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="memories")
    feedback_entries: Mapped[List["MemoryFeedback"]] = relationship(
        "MemoryFeedback",
        back_populates="memory",
        cascade="all, delete-orphan",
    )
