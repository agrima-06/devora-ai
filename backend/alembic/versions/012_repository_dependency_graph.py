"""Add Phase 10 Stage 10.1 Repository Dependency Graph tables.

Revision ID: 012_repository_dependency_graph
Revises: 011_model_gateway_resilience
Create Date: 2026-11-19 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "012_repository_dependency_graph"
down_revision: Union[str, None] = "011_model_gateway_resilience"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. repository_graph_nodes table
    op.create_table(
        "repository_graph_nodes",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("qualified_name", sa.String(1000), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("repository_id", "qualified_name", name="uq_repo_graph_node_qualified"),
    )
    op.create_index("ix_repo_graph_nodes_repo_id", "repository_graph_nodes", ["repository_id"])
    op.create_index("ix_repo_graph_nodes_node_type", "repository_graph_nodes", ["node_type"])
    op.create_index("ix_repo_graph_nodes_repo_type", "repository_graph_nodes", ["repository_id", "node_type"])
    op.create_index("ix_repo_graph_nodes_repo_file", "repository_graph_nodes", ["repository_id", "file_path"])
    op.create_index("ix_repo_graph_nodes_qualified", "repository_graph_nodes", ["repository_id", "qualified_name"])

    # 2. repository_graph_edges table
    op.create_table(
        "repository_graph_edges",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", PG_UUID(as_uuid=True), sa.ForeignKey("repository_graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_node_id", PG_UUID(as_uuid=True), sa.ForeignKey("repository_graph_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("edge_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("resolution_status", sa.String(50), nullable=False, server_default="RESOLVED"),
        sa.Column("target_symbol", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "repository_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "target_symbol",
            name="uq_repo_graph_edge",
        ),
    )
    op.create_index("ix_repo_graph_edges_repo_id", "repository_graph_edges", ["repository_id"])
    op.create_index("ix_repo_graph_edges_source", "repository_graph_edges", ["source_node_id"])
    op.create_index("ix_repo_graph_edges_target", "repository_graph_edges", ["target_node_id"])
    op.create_index("ix_repo_graph_edges_edge_type", "repository_graph_edges", ["edge_type"])
    op.create_index("ix_repo_graph_edges_resolution", "repository_graph_edges", ["resolution_status"])
    op.create_index("ix_repo_graph_edges_repo_source", "repository_graph_edges", ["repository_id", "source_node_id"])
    op.create_index("ix_repo_graph_edges_repo_target", "repository_graph_edges", ["repository_id", "target_node_id"])


def downgrade() -> None:
    op.drop_table("repository_graph_edges")
    op.drop_table("repository_graph_nodes")
