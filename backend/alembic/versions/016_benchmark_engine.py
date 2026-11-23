"""Add Phase 10 Stage 10.7 Benchmark Engine tables.

Revision ID: 016_benchmark_engine
Revises: 015_refactoring_engine
Create Date: 2026-11-23 05:35:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "016_benchmark_engine"
down_revision: Union[str, None] = "015_refactoring_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. benchmark_scenarios table
    op.create_table(
        "benchmark_scenarios",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("scenario_key", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("difficulty", sa.String(50), nullable=False, server_default="MEDIUM"),
        sa.Column("eval_type", sa.String(50), nullable=False, server_default="EXACT_MATCH"),
        sa.Column("input_context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("expected_output", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("evaluation_criteria", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_benchmark_scenarios_key", "benchmark_scenarios", ["scenario_key"])
    op.create_index("ix_benchmark_scenarios_category", "benchmark_scenarios", ["category"])
    op.create_index("ix_benchmark_scenarios_active", "benchmark_scenarios", ["is_active"])

    # 2. benchmark_suite_runs table
    op.create_table(
        "benchmark_suite_runs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_name", sa.String(100), nullable=False, server_default="devora_core_intelligence_suite"),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("code_revision", sa.String(100), nullable=True),
        sa.Column("dataset_version", sa.String(50), nullable=False, server_default="v1.0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("total_scenarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_scenarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_scenarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_safety_failure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("aggregate_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("category_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("calibration_error", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_p50_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_p95_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("token_usage_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_estimate_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "triggered_by",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_benchmark_suite_runs_suite", "benchmark_suite_runs", ["suite_name"])
    op.create_index("ix_benchmark_suite_runs_model", "benchmark_suite_runs", ["model_name"])
    op.create_index("ix_benchmark_suite_runs_status", "benchmark_suite_runs", ["status"])
    op.create_index("ix_benchmark_suite_runs_safety", "benchmark_suite_runs", ["critical_safety_failure"])

    # 3. benchmark_scenario_results table
    op.create_table(
        "benchmark_scenario_results",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("benchmark_suite_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("benchmark_scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scenario_key", sa.String(100), nullable=False, server_default=""),
        sa.Column("category", sa.String(50), nullable=False, server_default=""),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("actual_output", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("expected_output", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("diff_summary", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("invariants_met", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("safety_violated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_benchmark_results_run_id", "benchmark_scenario_results", ["run_id"])
    op.create_index("ix_benchmark_results_scenario_id", "benchmark_scenario_results", ["scenario_id"])
    op.create_index("ix_benchmark_results_safety", "benchmark_scenario_results", ["safety_violated"])

    # 4. benchmark_regressions table
    op.create_table(
        "benchmark_regressions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "baseline_run_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("benchmark_suite_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_run_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("benchmark_suite_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("benchmark_scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scenario_key", sa.String(100), nullable=False, server_default=""),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("baseline_score", sa.Float(), nullable=False),
        sa.Column("target_score", sa.Float(), nullable=False),
        sa.Column("score_delta", sa.Float(), nullable=False),
        sa.Column("percentage_change", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("regression_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_benchmark_regressions_base_run", "benchmark_regressions", ["baseline_run_id"])
    op.create_index("ix_benchmark_regressions_tgt_run", "benchmark_regressions", ["target_run_id"])
    op.create_index("ix_benchmark_regressions_scenario", "benchmark_regressions", ["scenario_id"])
    op.create_index("ix_benchmark_regressions_category", "benchmark_regressions", ["category"])
    op.create_index("ix_benchmark_regressions_severity", "benchmark_regressions", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_benchmark_regressions_severity", table_name="benchmark_regressions")
    op.drop_index("ix_benchmark_regressions_category", table_name="benchmark_regressions")
    op.drop_index("ix_benchmark_regressions_scenario", table_name="benchmark_regressions")
    op.drop_index("ix_benchmark_regressions_tgt_run", table_name="benchmark_regressions")
    op.drop_index("ix_benchmark_regressions_base_run", table_name="benchmark_regressions")
    op.drop_table("benchmark_regressions")

    op.drop_index("ix_benchmark_results_safety", table_name="benchmark_scenario_results")
    op.drop_index("ix_benchmark_results_scenario_id", table_name="benchmark_scenario_results")
    op.drop_index("ix_benchmark_results_run_id", table_name="benchmark_scenario_results")
    op.drop_table("benchmark_scenario_results")

    op.drop_index("ix_benchmark_suite_runs_safety", table_name="benchmark_suite_runs")
    op.drop_index("ix_benchmark_suite_runs_status", table_name="benchmark_suite_runs")
    op.drop_index("ix_benchmark_suite_runs_model", table_name="benchmark_suite_runs")
    op.drop_index("ix_benchmark_suite_runs_suite", table_name="benchmark_suite_runs")
    op.drop_table("benchmark_suite_runs")

    op.drop_index("ix_benchmark_scenarios_active", table_name="benchmark_scenarios")
    op.drop_index("ix_benchmark_scenarios_category", table_name="benchmark_scenarios")
    op.drop_index("ix_benchmark_scenarios_key", table_name="benchmark_scenarios")
    op.drop_table("benchmark_scenarios")
