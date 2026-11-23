"""Add Phase 10 Stage 10.5 Repository Architecture Drift and Technical Debt tables.

Revision ID: 014_architectural_drift_and_technical_debt
Revises: 013_architecture_patterns
Create Date: 2026-11-20 23:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "014_arch_drift_tech_debt"
down_revision: Union[str, None] = "013_architecture_patterns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. repository_architecture_drift table
    op.create_table(
        "repository_architecture_drift",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(100), nullable=True),
        sa.Column("baseline_commit_sha", sa.String(100), nullable=True),
        sa.Column("drift_status", sa.String(50), nullable=False, server_default="HEALTHY"),
        sa.Column("total_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("medium_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("violations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("resolved_violations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_repo_drift_repo_id", "repository_architecture_drift", ["repository_id"])
    op.create_index("ix_repo_drift_commit_sha", "repository_architecture_drift", ["commit_sha"])
    op.create_index("ix_repo_drift_status", "repository_architecture_drift", ["drift_status"])

    # 2. repository_technical_debt table
    op.create_table(
        "repository_technical_debt",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(100), nullable=True),
        sa.Column("overall_debt_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("severity", sa.String(50), nullable=False, server_default="CLEAN"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("dimension_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("summary_metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("findings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_repo_tech_debt_repo_id", "repository_technical_debt", ["repository_id"])
    op.create_index("ix_repo_tech_debt_commit_sha", "repository_technical_debt", ["commit_sha"])
    op.create_index("ix_repo_tech_debt_severity", "repository_technical_debt", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_repo_tech_debt_severity", table_name="repository_technical_debt")
    op.drop_index("ix_repo_tech_debt_commit_sha", table_name="repository_technical_debt")
    op.drop_index("ix_repo_tech_debt_repo_id", table_name="repository_technical_debt")
    op.drop_table("repository_technical_debt")

    op.drop_index("ix_repo_drift_status", table_name="repository_architecture_drift")
    op.drop_index("ix_repo_drift_commit_sha", table_name="repository_architecture_drift")
    op.drop_index("ix_repo_drift_repo_id", table_name="repository_architecture_drift")
    op.drop_table("repository_architecture_drift")
