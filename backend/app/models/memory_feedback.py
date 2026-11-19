"""MemoryFeedback database model for user and task feedback on retrieved memories."""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository_memory import RepositoryMemory
    from app.models.user import User
    from app.models.task import Task


class MemoryFeedback(Base, UUIDMixin, TimestampMixin):
    """User or task feedback recording utility of retrieved engineering memory."""
    __tablename__ = "memory_feedback"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repository_memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    memory: Mapped["RepositoryMemory"] = relationship("RepositoryMemory", back_populates="feedback_entries")
    user: Mapped["User"] = relationship("User")
    task: Mapped[Optional["Task"]] = relationship("Task")
