"""Add Phase 9 Stage 9.4 Workflow Recovery & Resumption schema updates.

Revision ID: 010_workflow_recovery
Revises: 009_resource_telemetry
Create Date: 2026-11-19 11:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "010_workflow_recovery"
down_revision: Union[str, None] = "009_resource_telemetry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update tasks table with recovery tracking and lease columns
    op.add_column(
        "tasks",
        sa.Column("recovery_status", sa.String(50), nullable=False, server_default="NOT_REQUIRED"),
    )
    op.create_index("ix_tasks_recovery_status", "tasks", ["recovery_status"])
    op.add_column(
        "tasks",
        sa.Column("recovery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tasks",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("recovery_lease_owner", sa.String(100), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("recovery_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("recovery_error", sa.Text(), nullable=True),
    )

    # 2. Update workflow_checkpoints table with node tracking and step ordering
    op.add_column(
        "workflow_checkpoints",
        sa.Column("node_name", sa.String(100), nullable=True),
    )
    op.create_index("ix_workflow_checkpoints_node_name", "workflow_checkpoints", ["node_name"])
    op.add_column(
        "workflow_checkpoints",
        sa.Column("step_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "workflow_checkpoints",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("workflow_checkpoints", "version")
    op.drop_column("workflow_checkpoints", "step_number")
    op.drop_index("ix_workflow_checkpoints_node_name", table_name="workflow_checkpoints")
    op.drop_column("workflow_checkpoints", "node_name")

    op.drop_column("tasks", "recovery_error")
    op.drop_column("tasks", "recovery_lease_expires_at")
    op.drop_column("tasks", "recovery_lease_owner")
    op.drop_column("tasks", "last_heartbeat_at")
    op.drop_column("tasks", "recovery_attempts")
    op.drop_index("ix_tasks_recovery_status", table_name="tasks")
    op.drop_column("tasks", "recovery_status")
