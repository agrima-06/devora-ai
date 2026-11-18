"""Task database model."""
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project
    from app.models.repository import Repository
    from app.models.task_plan import TaskPlan
    from app.models.agent_run import AgentRun
    from app.models.file_change import FileChange
    from app.models.test_run import TestRun
    from app.models.approval import Approval
    from app.models.report import Report
    from app.models.feedback import Feedback


class Task(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(50), default="bug_fix", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    iterations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_branch: Mapped[str] = mapped_column(String(255), default="main", nullable=False)
    pull_request_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    repository: Mapped["Repository"] = relationship("Repository", back_populates="tasks")
    creator: Mapped["User"] = relationship("User", back_populates="tasks")
    plans: Mapped[List["TaskPlan"]] = relationship("TaskPlan", back_populates="task", cascade="all, delete-orphan")
    agent_runs: Mapped[List["AgentRun"]] = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")
    file_changes: Mapped[List["FileChange"]] = relationship("FileChange", back_populates="task", cascade="all, delete-orphan")
    test_runs: Mapped[List["TestRun"]] = relationship("TestRun", back_populates="task", cascade="all, delete-orphan")
    approvals: Mapped[List["Approval"]] = relationship("Approval", back_populates="task", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="task", cascade="all, delete-orphan")
    feedback: Mapped[List["Feedback"]] = relationship("Feedback", back_populates="task", cascade="all, delete-orphan")
