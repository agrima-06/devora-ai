"""Add Phase 9 Stage 9.5 Model Gateway Health table.

Revision ID: 011_model_gateway_resilience
Revises: 010_workflow_recovery
Create Date: 2026-11-19 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "011_model_gateway_resilience"
down_revision: Union[str, None] = "010_workflow_recovery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_gateway_health",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("circuit_state", sa.String(20), nullable=False, server_default="CLOSED"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_fallbacks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_failure_reason", sa.Text(), nullable=True),
        sa.Column("last_failure_classification", sa.String(50), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_state_change_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_name", "model_name", name="uq_provider_model_health"),
    )
    op.create_index("ix_model_gateway_health_provider_name", "model_gateway_health", ["provider_name"])
    op.create_index("ix_model_gateway_health_model_name", "model_gateway_health", ["model_name"])
    op.create_index("ix_model_gateway_health_circuit_state", "model_gateway_health", ["circuit_state"])


def downgrade() -> None:
    op.drop_index("ix_model_gateway_health_circuit_state", table_name="model_gateway_health")
    op.drop_index("ix_model_gateway_health_model_name", table_name="model_gateway_health")
    op.drop_index("ix_model_gateway_health_provider_name", table_name="model_gateway_health")
    op.drop_table("model_gateway_health")
