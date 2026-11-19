"""Add Phase 7 Adaptive Engineering Intelligence schema: experience extensions, failure records, and benchmark framework.

Revision ID: 006_adaptive_intelligence
Revises: 005_ml_engine
Create Date: 2026-11-19 01:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "006_adaptive_intelligence"
down_revision: Union[str, None] = "005_ml_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend engineering_experiences table with adaptive intelligence attributes
    op.add_column(
        "engineering_experiences",
        sa.Column("status_type", sa.String(50), nullable=False, server_default="verified_successful"),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("technology_stack", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("files_involved", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("failed_approaches", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("successful_approach", sa.Text(), nullable=True),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("test_results", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("review_findings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("security_findings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("failure_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "engineering_experiences",
        sa.Column("commit_sha", sa.String(40), nullable=True),
    )
    op.create_index("idx_eng_exp_status_type", "engineering_experiences", ["status_type"])
    op.create_index("idx_eng_exp_failure_type", "engineering_experiences", ["failure_type"])

    # 2. Create task_failure_records table
    op.create_table(
        "task_failure_records",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stage", sa.String(50), nullable=False, index=True),
        sa.Column("failure_type", sa.String(50), nullable=False, index=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("failed_strategy", sa.Text(), nullable=False),
        sa.Column("error_log", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("lessons_learned", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_task_failures_stage_type", "task_failure_records", ["stage", "failure_type"])

    # 3. Create benchmark_definitions table
    op.create_table(
        "benchmark_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("initial_repo_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("expected_outcomes", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evaluation_criteria", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("baseline_pass_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 4. Create benchmark_runs table
    op.create_table(
        "benchmark_runs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "benchmark_id",
            sa.String(100),
            sa.ForeignKey("benchmark_definitions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("system_version", sa.String(50), nullable=False, index=True),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("task_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tests_passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retries_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planning_efficiency_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("review_passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_bm_runs_id_ver", "benchmark_runs", ["benchmark_id", "system_version"])


def downgrade() -> None:
    op.drop_index("idx_bm_runs_id_ver", table_name="benchmark_runs")
    op.drop_table("benchmark_runs")
    op.drop_table("benchmark_definitions")
    op.drop_index("idx_task_failures_stage_type", table_name="task_failure_records")
    op.drop_table("task_failure_records")
    op.drop_index("idx_eng_exp_failure_type", table_name="engineering_experiences")
    op.drop_index("idx_eng_exp_status_type", table_name="engineering_experiences")
    op.drop_column("engineering_experiences", "commit_sha")
    op.drop_column("engineering_experiences", "failure_type")
    op.drop_column("engineering_experiences", "security_findings")
    op.drop_column("engineering_experiences", "review_findings")
    op.drop_column("engineering_experiences", "test_results")
    op.drop_column("engineering_experiences", "successful_approach")
    op.drop_column("engineering_experiences", "failed_approaches")
    op.drop_column("engineering_experiences", "attempts_count")
    op.drop_column("engineering_experiences", "files_involved")
    op.drop_column("engineering_experiences", "technology_stack")
    op.drop_column("engineering_experiences", "status_type")
