"""Add ml_predictions and ml_models tables for Phase 6 Machine Learning Bug Classification Engine.

Revision ID: 005_ml_engine
Revises: 004_semantic_memory
Create Date: 2026-11-19 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "005_ml_engine"
down_revision: Union[str, None] = "004_semantic_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ml_models table
    op.create_table(
        "ml_models",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("algorithm", sa.String(100), nullable=False, server_default="LogisticRegression"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("accuracy", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("macro_f1", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("weighted_f1", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("training_sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_sha256", sa.String(64), nullable=False),
        sa.Column("vectorizer_sha256", sa.String(64), nullable=False),
        sa.Column("promotion_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. Create ml_predictions table
    op.create_table(
        "ml_predictions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("input_hash", sa.String(64), nullable=False, index=True),
        sa.Column("error_sample_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("predicted_category", sa.String(50), nullable=False, index=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("top_probabilities", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_low_confidence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model_version", sa.String(50), nullable=False, index=True),
        sa.Column("inference_time_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("verified_category", sa.String(50), nullable=True, index=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ml_pred_task_cat", "ml_predictions", ["task_id", "predicted_category"])


def downgrade() -> None:
    op.drop_index("idx_ml_pred_task_cat", table_name="ml_predictions")
    op.drop_table("ml_predictions")
    op.drop_table("ml_models")
