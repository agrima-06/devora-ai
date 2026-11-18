"""RepositoryFile database model."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryFile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "repository_files"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lines_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_info: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="indexed_files")
