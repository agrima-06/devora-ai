"""Benchmark Engine database models for Phase 10 Stage 10.7.

Provides comprehensive data structures for evaluating, scoring, tracking regressions,
and auditing Devora AI's autonomous engineering intelligence across 7 canonical categories:
- Category A: Bug Detection and Resolution
- Category B: Repository Understanding
- Category C: Architecture Intelligence
- Category D: Change Impact Analysis
- Category E: Autonomous Refactoring
- Category F: Multi-Agent Workflow Quality
- Category G: Security and Safety
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class BenchmarkScenario(Base, UUIDMixin, TimestampMixin):
    """Ground-truth evaluation scenario with deterministic evaluation criteria."""
    __tablename__ = "benchmark_scenarios"

    scenario_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # bug_detection, repo_understanding, arch_intelligence, impact_analysis, refactoring, multi_agent, security_safety
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MEDIUM",
    )  # LOW, MEDIUM, HIGH, CRITICAL
    eval_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EXACT_MATCH",
    )  # EXACT_MATCH, STRUCTURAL, AST_DELTA, TEST_ASSERTION, SECURITY_POLICY
    input_context: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    expected_output: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    evaluation_criteria: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    tags: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Relationships
    results: Mapped[List["BenchmarkScenarioResult"]] = relationship(
        "BenchmarkScenarioResult",
        back_populates="scenario",
        cascade="all, delete-orphan",
    )
    regressions: Mapped[List["BenchmarkRegression"]] = relationship(
        "BenchmarkRegression",
        back_populates="scenario",
        cascade="all, delete-orphan",
    )


class BenchmarkSuiteRun(Base, UUIDMixin, TimestampMixin):
    """Execution run of the evaluation benchmark suite tracking aggregate performance and safety."""
    __tablename__ = "benchmark_suite_runs"

    suite_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        default="devora_core_intelligence_suite",
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    code_revision: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    dataset_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1.0",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )  # PENDING, RUNNING, COMPLETED, FAILED, CRITICAL_SAFETY_FAILURE, CANCELLED
    total_scenarios: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    passed_scenarios: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_scenarios: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    critical_safety_failure: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    aggregate_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    category_scores: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    calibration_error: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    latency_p50_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    latency_p95_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    token_usage_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    cost_estimate_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    triggered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    results: Mapped[List["BenchmarkScenarioResult"]] = relationship(
        "BenchmarkScenarioResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    baseline_regressions: Mapped[List["BenchmarkRegression"]] = relationship(
        "BenchmarkRegression",
        foreign_keys="[BenchmarkRegression.baseline_run_id]",
        back_populates="baseline_run",
        cascade="all, delete-orphan",
    )
    target_regressions: Mapped[List["BenchmarkRegression"]] = relationship(
        "BenchmarkRegression",
        foreign_keys="[BenchmarkRegression.target_run_id]",
        back_populates="target_run",
        cascade="all, delete-orphan",
    )


class BenchmarkScenarioResult(Base, UUIDMixin, TimestampMixin):
    """Detailed execution result for an individual scenario in a suite run."""
    __tablename__ = "benchmark_scenario_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("benchmark_suite_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("benchmark_scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )  # PASSED, FAILED, TIMEOUT, ERROR, SAFETY_VIOLATION
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    actual_output: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    expected_output: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    diff_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    execution_time_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    invariants_met: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    safety_violated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    evidence: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Relationships
    run: Mapped["BenchmarkSuiteRun"] = relationship(
        "BenchmarkSuiteRun",
        back_populates="results",
    )
    scenario: Mapped["BenchmarkScenario"] = relationship(
        "BenchmarkScenario",
        back_populates="results",
    )


class BenchmarkRegression(Base, UUIDMixin, TimestampMixin):
    """Identified regression between two benchmark suite runs."""
    __tablename__ = "benchmark_regressions"

    baseline_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("benchmark_suite_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("benchmark_suite_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("benchmark_scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # CRITICAL, HIGH, MEDIUM, LOW
    baseline_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    target_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    score_delta: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    percentage_change: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    regression_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # ACCURACY_DROP, LATENCY_SPIKE, SAFETY_BREACH, INVARIANT_FAILURE

    # Relationships
    baseline_run: Mapped["BenchmarkSuiteRun"] = relationship(
        "BenchmarkSuiteRun",
        foreign_keys=[baseline_run_id],
        back_populates="baseline_regressions",
    )
    target_run: Mapped["BenchmarkSuiteRun"] = relationship(
        "BenchmarkSuiteRun",
        foreign_keys=[target_run_id],
        back_populates="target_regressions",
    )
    scenario: Mapped["BenchmarkScenario"] = relationship(
        "BenchmarkScenario",
        back_populates="regressions",
    )
