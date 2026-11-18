"""Add repository intelligence tables and repository status columns.

Revision ID: 002_repository_intelligence
Revises: 001_initial_schema
Create Date: 2026-11-17 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "002_repository_intelligence"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to repositories
    op.add_column("repositories", sa.Column("current_commit_sha", sa.String(100), nullable=True))
    op.add_column(
        "repositories",
        sa.Column("indexing_status", sa.String(50), nullable=False, server_default="NOT_INDEXED"),
    )
    op.add_column("repositories", sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Create indexing_jobs table
    op.create_table(
        "indexing_jobs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(100), nullable=False),
        sa.Column("branch", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("files_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("symbols_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_indexing_jobs_repo_status", "indexing_jobs", ["repository_id", "status"])

    # 3. Create repository_files table
    op.create_table(
        "repository_files",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lines_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commit_sha", sa.String(100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_repo_files_repo_path", "repository_files", ["repository_id", "file_path"])


def downgrade() -> None:
    op.drop_table("repository_files")
    op.drop_table("indexing_jobs")
    op.drop_column("repositories", "last_indexed_at")
    op.drop_column("repositories", "indexing_status")
    op.drop_column("repositories", "current_commit_sha")
