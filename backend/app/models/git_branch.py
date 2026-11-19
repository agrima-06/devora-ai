"""Git branch tracking database model."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.repository import Repository


class GitBranch(Base, UUIDMixin):
    """Git branch allocated for autonomous task execution."""
    __tablename__ = "git_branches"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), default="main", nullable=False)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="git_branches")
    repository: Mapped["Repository"] = relationship("Repository", back_populates="git_branches")
