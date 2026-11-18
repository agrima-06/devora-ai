"""EngineeringExperience database model."""
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin, VectorType

if TYPE_CHECKING:
    from app.models.repository import Repository


class EngineeringExperience(Base, UUIDMixin, TimestampMixin):
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

    # Relationships
    repository: Mapped[Optional["Repository"]] = relationship("Repository")
