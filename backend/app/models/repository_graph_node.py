"""RepositoryGraphNode database model."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_graph_edge import RepositoryGraphEdge


class RepositoryGraphNode(Base, UUIDMixin, TimestampMixin):
    """Represents a structural or semantic source-code entity in a repository."""
    __tablename__ = "repository_graph_nodes"
    __table_args__ = (
        UniqueConstraint("repository_id", "qualified_name", name="uq_repo_graph_node_qualified"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # REPOSITORY, DIRECTORY, FILE, MODULE, PACKAGE, CLASS, INTERFACE, FUNCTION, METHOD, VARIABLE
    qualified_name: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    file_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    start_line: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    end_line: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    meta_info: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="graph_nodes")
    outgoing_edges: Mapped[List["RepositoryGraphEdge"]] = relationship(
        "RepositoryGraphEdge",
        foreign_keys="RepositoryGraphEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List["RepositoryGraphEdge"]] = relationship(
        "RepositoryGraphEdge",
        foreign_keys="RepositoryGraphEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )
