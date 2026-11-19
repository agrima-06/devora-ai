"""FlakyTestRecord database model for tracking test stability and non-deterministic failures."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.task import Task


class FlakyTestRecord(Base, UUIDMixin, TimestampMixin):
    """Stores historical stability scores and repeat execution telemetry for flaky tests."""
    __tablename__ = "flaky_test_records"
    __test__ = False  # Prevent pytest from collecting this model class as a test suite

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_identifier: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    test_file: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    framework: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pytest",
    )
    language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="python",
    )
    test_command: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    classification: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default="FLAKY",
    )  # 'STABLE_PASS', 'CONSISTENT_FAILURE', 'FLAKY', 'INCONCLUSIVE', 'UNVERIFIED'
    stability_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    total_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    passed_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    infrastructure_error_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    timeout_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    execution_history: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="flaky_tests")
    task: Mapped["Task"] = relationship("Task", back_populates="flaky_tests")
