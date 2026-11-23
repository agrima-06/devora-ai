"""Add Phase 10 Stage 10.6 Refactoring Plans and Executions tables.

Revision ID: 015_refactoring_engine
Revises: 014_arch_drift_tech_debt
Create Date: 2026-11-23 03:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "015_refactoring_engine"
down_revision: Union[str, None] = "014_arch_drift_tech_debt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. repository_refactoring_plans table
    op.create_table(
        "repository_refactoring_plans",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_revision", sa.String(100), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="LOW"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column(
            "approved_by",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_diff_hash", sa.String(64), nullable=True),
        sa.Column("execution_status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("target_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("target_symbols", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("finding_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("affected_packages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("ordered_steps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommended_tests", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("expected_outcomes", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refactor_plans_repo_id", "repository_refactoring_plans", ["repository_id"])
    op.create_index("ix_refactor_plans_source_rev", "repository_refactoring_plans", ["source_revision"])
    op.create_index("ix_refactor_plans_approval", "repository_refactoring_plans", ["approval_status"])
    op.create_index("ix_refactor_plans_execution", "repository_refactoring_plans", ["execution_status"])

    # 2. refactoring_executions table
    op.create_table(
        "refactoring_executions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repository_refactoring_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("source_commit_sha", sa.String(100), nullable=True),
        sa.Column("target_branch", sa.String(255), nullable=True),
        sa.Column("diff_content", sa.Text(), nullable=True),
        sa.Column("diff_hash", sa.String(64), nullable=True),
        sa.Column("files_changed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lines_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lines_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("baseline_tests_passed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("post_tests_passed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tests_executed", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("before_metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("after_metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("new_violations_detected", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refactor_exec_plan_id", "refactoring_executions", ["plan_id"])
    op.create_index("ix_refactor_exec_repo_id", "refactoring_executions", ["repository_id"])
    op.create_index("ix_refactor_exec_status", "refactoring_executions", ["status"])
    op.create_index("ix_refactor_exec_diff_hash", "refactoring_executions", ["diff_hash"])


def downgrade() -> None:
    op.drop_index("ix_refactor_exec_diff_hash", table_name="refactoring_executions")
    op.drop_index("ix_refactor_exec_status", table_name="refactoring_executions")
    op.drop_index("ix_refactor_exec_repo_id", table_name="refactoring_executions")
    op.drop_index("ix_refactor_exec_plan_id", table_name="refactoring_executions")
    op.drop_table("refactoring_executions")

    op.drop_index("ix_refactor_plans_execution", table_name="repository_refactoring_plans")
    op.drop_index("ix_refactor_plans_approval", table_name="repository_refactoring_plans")
    op.drop_index("ix_refactor_plans_source_rev", table_name="repository_refactoring_plans")
    op.drop_index("ix_refactor_plans_repo_id", table_name="repository_refactoring_plans")
    op.drop_table("repository_refactoring_plans")
