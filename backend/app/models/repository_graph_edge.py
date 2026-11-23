"""RepositoryGraphEdge database model."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_graph_node import RepositoryGraphNode


class RepositoryGraphEdge(Base, UUIDMixin):
    """Represents a directional relationship between two code entities or an entity and an external symbol."""
    __tablename__ = "repository_graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "target_symbol",
            name="uq_repo_graph_edge",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repository_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repository_graph_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    edge_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # CONTAINS, DEFINES, IMPORTS, DEPENDS_ON, INHERITS, IMPLEMENTS, REFERENCES, CALLS
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    resolution_status: Mapped[str] = mapped_column(
        String(50),
        default="RESOLVED",
        nullable=False,
        index=True,
    )  # RESOLVED, EXTERNAL, UNRESOLVED, AMBIGUOUS
    target_symbol: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    meta_info: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="graph_edges")
    source_node: Mapped["RepositoryGraphNode"] = relationship(
        "RepositoryGraphNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
    target_node: Mapped[Optional["RepositoryGraphNode"]] = relationship(
        "RepositoryGraphNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )
