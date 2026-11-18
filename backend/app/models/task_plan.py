"""TaskPlan database model."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task


class TaskPlan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "task_plans"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    test_criteria: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="plans")
