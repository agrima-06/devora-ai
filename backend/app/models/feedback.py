"""Feedback database model."""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class Feedback(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "feedback"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[str] = mapped_column(String(50), nullable=False)  # 'ACCEPTED', 'REJECTED', 'NEEDS_CHANGES', etc.
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="feedback")
    user: Mapped["User"] = relationship("User")
