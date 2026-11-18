"""RepositoryKnowledge database model."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin, VectorType

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryKnowledge(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "repository_knowledge"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    symbol_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'class', 'function', 'module'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(VectorType(768), nullable=False)
    meta_info: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="knowledge_entries")
