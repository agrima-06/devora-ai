"""Add workflow checkpoints and workflow events tables.

Revision ID: 003_workflow_system
Revises: 002_repository_intelligence
Create Date: 2026-11-17 17:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "003_workflow_system"
down_revision: Union[str, None] = "002_repository_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create workflow_events table
    op.create_table(
        "workflow_events",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. Create workflow_checkpoints table
    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("thread_id", sa.String(100), nullable=False, index=True),
        sa.Column("checkpoint_ns", sa.String(100), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.String(100), nullable=False, index=True),
        sa.Column("parent_checkpoint_id", sa.String(100), nullable=True),
        sa.Column("state_blob", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("workflow_checkpoints")
    op.drop_table("workflow_events")
