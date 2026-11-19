"""TaskFailureRecord database model for structured failure learning."""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task


class TaskFailureRecord(Base, UUIDMixin, TimestampMixin):
    """Captures specific execution stage failures and diagnostic lessons to prevent recurrence."""
    __tablename__ = "task_failure_records"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'TESTING', 'CODE_REVIEW', 'SECURITY_AUDIT', 'DEVELOPER_REVIEW'
    failure_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'INCORRECT_ASSUMPTION', 'IMPLEMENTATION_DEFECT', 'DEPENDENCY_ISSUE', 'ENVIRONMENT_PROBLEM'
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    failed_strategy: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    error_log: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    review_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    lessons_learned: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", backref="failure_records")
