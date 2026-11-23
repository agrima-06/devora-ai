"""Add Phase 10 Stage 10.4 Repository Architecture Patterns table.

Revision ID: 013_architecture_patterns
Revises: 012_repository_dependency_graph
Create Date: 2026-11-19 19:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "013_architecture_patterns"
down_revision: Union[str, None] = "012_repository_dependency_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repository_architecture_patterns",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pattern_id", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_status", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("supporting_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("supporting_symbols", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("supporting_relationships", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("supporting_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("counterexamples", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("conventions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("analysis_version", sa.String(50), nullable=False, server_default="1.0.0"),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("repository_id", "pattern_id", name="uq_repo_architecture_pattern"),
    )
    op.create_index("ix_repo_arch_patterns_repo_id", "repository_architecture_patterns", ["repository_id"])
    op.create_index("ix_repo_arch_patterns_pattern_id", "repository_architecture_patterns", ["pattern_id"])
    op.create_index("ix_repo_arch_patterns_category", "repository_architecture_patterns", ["category"])
    op.create_index("ix_repo_arch_patterns_status", "repository_architecture_patterns", ["evidence_status"])


def downgrade() -> None:
    op.drop_index("ix_repo_arch_patterns_status", table_name="repository_architecture_patterns")
    op.drop_index("ix_repo_arch_patterns_category", table_name="repository_architecture_patterns")
    op.drop_index("ix_repo_arch_patterns_pattern_id", table_name="repository_architecture_patterns")
    op.drop_index("ix_repo_arch_patterns_repo_id", table_name="repository_architecture_patterns")
    op.drop_table("repository_architecture_patterns")
