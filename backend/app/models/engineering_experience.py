"""EngineeringExperience database model for adaptive engineering intelligence."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin, VectorType

if TYPE_CHECKING:
    from app.models.repository import Repository


class EngineeringExperience(Base, UUIDMixin, TimestampMixin):
    """Encapsulates verified historical engineering task experiences for adaptive intelligence."""
    __tablename__ = "engineering_experiences"

    repository_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bug_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    problem_summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    diff_patch: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(VectorType(768), nullable=False)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Adaptive Intelligence Extensions
    status_type: Mapped[str] = mapped_column(
        String(50),
        default="verified_successful",
        nullable=False,
        index=True,
    )  # 'verified_successful', 'verified_failed', 'incomplete_attempt', 'unverified_hypothesis'
    technology_stack: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    files_involved: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    failed_approaches: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    successful_approach: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    test_results: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    review_findings: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    security_findings: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    failure_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )  # 'INCORRECT_ASSUMPTION', 'IMPLEMENTATION_DEFECT', 'DEPENDENCY_ISSUE', 'ENVIRONMENT_PROBLEM'
    commit_sha: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )

    # Relationships
    repository: Mapped[Optional["Repository"]] = relationship("Repository")
