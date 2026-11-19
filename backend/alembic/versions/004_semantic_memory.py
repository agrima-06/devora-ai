"""Add repository_memories and memory_feedback tables for Phase 5 semantic vector memory.

Revision ID: 004_semantic_memory
Revises: 003_workflow_system
Create Date: 2026-11-18 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.base import VectorType

# revision identifiers, used by Alembic.
revision: str = "004_semantic_memory"
down_revision: Union[str, None] = "003_workflow_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create repository_memories table
    op.create_table(
        "repository_memories",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", VectorType(768), nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="observed_fact", index=True),
        sa.Column("access_scope", sa.String(50), nullable=False, server_default="repository"),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unhelpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_repo_memories_repo_cat", "repository_memories", ["repository_id", "category"])
    op.create_index("idx_repo_memories_status", "repository_memories", ["repository_id", "verification_status"])

    # 2. Create memory_feedback table
    op.create_table(
        "memory_feedback",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "memory_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repository_memories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("is_helpful", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("memory_feedback")
    op.drop_table("repository_memories")
