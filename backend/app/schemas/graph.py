"""Schemas for Phase 10 Stage 10.1: Cross-File Symbol and Dependency Graph Engine."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GraphNodeItem(BaseModel):
    """Source-code entity node in repository dependency graph."""
    id: str
    repository_id: str
    node_type: str = Field(description="REPOSITORY, DIRECTORY, FILE, MODULE, PACKAGE, CLASS, INTERFACE, FUNCTION, METHOD, VARIABLE")
    qualified_name: str
    name: str
    file_path: Optional[str] = None
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GraphEdgeItem(BaseModel):
    """Directional relationship between two graph nodes or external symbols."""
    id: str
    repository_id: str
    source_node_id: str
    target_node_id: Optional[str] = None
    edge_type: str = Field(description="CONTAINS, DEFINES, IMPORTS, DEPENDS_ON, INHERITS, IMPLEMENTS, REFERENCES, CALLS")
    confidence: float = 1.0
    resolution_status: str = Field(description="RESOLVED, EXTERNAL, UNRESOLVED, AMBIGUOUS")
    target_symbol: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GraphNodeDetailResponse(BaseModel):
    """Detailed node entity with direct incoming and outgoing relationships."""
    node: GraphNodeItem
    incoming_edges: List[GraphEdgeItem] = Field(default_factory=list)
    outgoing_edges: List[GraphEdgeItem] = Field(default_factory=list)
    related_nodes: Dict[str, GraphNodeItem] = Field(default_factory=dict)


class RepositoryGraphSummaryResponse(BaseModel):
    """Overview statistics and metadata for a repository's dependency graph."""
    repository_id: str
    total_nodes: int = 0
    total_edges: int = 0
    node_types_breakdown: Dict[str, int] = Field(default_factory=dict)
    edge_types_breakdown: Dict[str, int] = Field(default_factory=dict)
    languages_breakdown: Dict[str, int] = Field(default_factory=dict)
    unresolved_count: int = 0
    external_count: int = 0
    last_indexed_at: Optional[datetime] = None
    current_commit_sha: Optional[str] = None
    indexing_status: str = "NOT_INDEXED"


class GraphNodesListResponse(BaseModel):
    """Paginated list of graph nodes matching query criteria."""
    total: int
    limit: int
    offset: int
    nodes: List[GraphNodeItem]


class GraphDependenciesResponse(BaseModel):
    """Bounded dependency traversal subgraph."""
    root_node_id: str
    direction: str = Field(description="outgoing, incoming, or both")
    max_depth: int
    nodes: List[GraphNodeItem]
    edges: List[GraphEdgeItem]


class UnresolvedReferenceItem(BaseModel):
    """Record of an unresolved cross-file or external reference."""
    edge_id: str
    source_file: str
    source_symbol: str
    target_symbol: str
    edge_type: str
    resolution_status: str
    line_number: Optional[int] = None


class GraphUnresolvedReferencesResponse(BaseModel):
    """Paginated list of unresolved dependencies."""
    total: int
    limit: int
    offset: int
    unresolved: List[UnresolvedReferenceItem]


class GraphIndexRequest(BaseModel):
    """Request payload to trigger dependency graph indexing."""
    force_reindex: bool = Field(default=False, description="Force full reparse ignoring content hashes")
    branch: Optional[str] = Field(default=None, description="Optional target branch")


class GraphIndexingResponse(BaseModel):
    """Execution telemetry and results of a graph indexing run."""
    repository_id: str
    status: str
    commit_sha: str
    total_files: int
    files_indexed: int
    files_skipped: int
    nodes_created: int
    edges_created: int
    unresolved_references: int
    duration_seconds: float
    message: str
