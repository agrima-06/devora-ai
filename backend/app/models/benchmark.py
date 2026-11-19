"""BenchmarkDefinition and BenchmarkRun database models for empirical performance evaluation."""
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin


class BenchmarkDefinition(Base, TimestampMixin):
    """Fixed reproducible engineering benchmark specification."""
    __tablename__ = "benchmark_definitions"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )  # e.g. 'BM-BUG-01'
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'bug_investigation', 'bug_fixing', 'repository_exploration', 'refactoring', etc.
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    initial_repo_snapshot: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    expected_outcomes: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    evaluation_criteria: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    baseline_pass_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Relationships
    runs = relationship("BenchmarkRun", back_populates="benchmark", cascade="all, delete-orphan")


class BenchmarkRun(Base, UUIDMixin, TimestampMixin):
    """Historical execution run evaluating Devora AI against a benchmark task."""
    __tablename__ = "benchmark_runs"

    benchmark_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("benchmark_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    system_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    task_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    tests_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    retries_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    planning_efficiency_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    execution_time_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    estimated_cost_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    review_passed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    benchmark: Mapped["BenchmarkDefinition"] = relationship("BenchmarkDefinition", back_populates="runs")
