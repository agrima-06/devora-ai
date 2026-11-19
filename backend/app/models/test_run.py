"""TestRun database model."""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.task import Task


class TestRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "test_runs"
    __test__ = False  # Prevent pytest from treating this model as a test suite

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    iteration: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Sandbox Resilience & Resource Telemetry (Phase 9 Stage 9.3)
    peak_memory_rss_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    peak_memory_rss_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpu_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wall_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_limit_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    memory_limit_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpu_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oom_killed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    termination_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exit_classification: Mapped[str] = mapped_column(String(50), default="EXECUTION_FAILURE", nullable=False)
    resource_telemetry_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="test_runs")
