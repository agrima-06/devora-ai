"""Add Phase 9 Stage 9.2 Flaky Test Detection schema: flaky_test_records table.

Revision ID: 008_flaky_test_records
Revises: 007_github_native_engineering
Create Date: 2026-11-19 10:05:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "008_flaky_test_records"
down_revision: Union[str, None] = "007_github_native_engineering"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flaky_test_records",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_identifier", sa.String(500), nullable=False),
        sa.Column("test_file", sa.String(500), nullable=False),
        sa.Column("framework", sa.String(50), nullable=False, server_default="pytest"),
        sa.Column("language", sa.String(50), nullable=False, server_default="python"),
        sa.Column("test_command", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(50), nullable=False, server_default="FLAKY"),
        sa.Column("stability_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("infrastructure_error_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_history", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_flaky_test_repo_ident", "flaky_test_records", ["repository_id", "test_identifier"])
    op.create_index("idx_flaky_test_task_id", "flaky_test_records", ["task_id"])
    op.create_index("idx_flaky_test_classification", "flaky_test_records", ["classification"])


def downgrade() -> None:
    op.drop_index("idx_flaky_test_classification", table_name="flaky_test_records")
    op.drop_index("idx_flaky_test_task_id", table_name="flaky_test_records")
    op.drop_index("idx_flaky_test_repo_ident", table_name="flaky_test_records")
    op.drop_table("flaky_test_records")
