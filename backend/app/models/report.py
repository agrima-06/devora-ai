"""Report database model."""
import uuid
from typing import TYPE_CHECKING, Any, Dict
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task


class Report(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reports"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    test_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="reports")
