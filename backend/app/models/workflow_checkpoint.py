"""WorkflowCheckpoint database model for LangGraph workflow state persistence."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task


class WorkflowCheckpoint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_checkpoints"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    checkpoint_ns: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parent_checkpoint_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state_blob: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    task: Mapped["Task"] = relationship("Task")
