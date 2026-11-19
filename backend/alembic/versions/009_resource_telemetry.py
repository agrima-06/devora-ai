"""Add Phase 9 Stage 9.3 Sandbox Resilience & Resource Telemetry columns to test_runs.

Revision ID: 009_resource_telemetry
Revises: 008_flaky_test_records
Create Date: 2026-11-19 10:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "009_resource_telemetry"
down_revision: Union[str, None] = "008_flaky_test_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("peak_memory_rss_bytes", sa.BigInteger(), nullable=True))
    op.add_column("test_runs", sa.Column("peak_memory_rss_mb", sa.Float(), nullable=True))
    op.add_column("test_runs", sa.Column("cpu_time_seconds", sa.Float(), nullable=True))
    op.add_column("test_runs", sa.Column("wall_time_seconds", sa.Float(), nullable=True))
    op.add_column("test_runs", sa.Column("memory_limit_bytes", sa.BigInteger(), nullable=True))
    op.add_column("test_runs", sa.Column("memory_limit_mb", sa.Float(), nullable=True))
    op.add_column("test_runs", sa.Column("cpu_limit", sa.Float(), nullable=True))
    op.add_column("test_runs", sa.Column("oom_killed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("test_runs", sa.Column("termination_reason", sa.String(255), nullable=True))
    op.add_column("test_runs", sa.Column("exit_classification", sa.String(50), nullable=False, server_default="EXECUTION_FAILURE"))
    op.add_column("test_runs", sa.Column("resource_telemetry_available", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("test_runs", "resource_telemetry_available")
    op.drop_column("test_runs", "exit_classification")
    op.drop_column("test_runs", "termination_reason")
    op.drop_column("test_runs", "oom_killed")
    op.drop_column("test_runs", "cpu_limit")
    op.drop_column("test_runs", "memory_limit_mb")
    op.drop_column("test_runs", "memory_limit_bytes")
    op.drop_column("test_runs", "wall_time_seconds")
    op.drop_column("test_runs", "cpu_time_seconds")
    op.drop_column("test_runs", "peak_memory_rss_mb")
    op.drop_column("test_runs", "peak_memory_rss_bytes")
