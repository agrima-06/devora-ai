"""Pydantic schemas for Phase 10 Stage 10.2: Blast Radius and Change Impact Analysis Engine."""
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ImpactTarget(BaseModel):
    """Represents a source file or symbol targeted for modification."""
    node_id: Optional[str] = Field(None, description="Graph node UUID if resolved in database")
    node_type: str = Field(..., description="Node type: FILE, CLASS, FUNCTION, METHOD, etc.")
    qualified_name: str = Field(..., description="Fully qualified name or file path")
    name: str = Field(..., description="Short entity or file name")
    file_path: Optional[str] = Field(None, description="Repository-relative file path")


class DependencyHop(BaseModel):
    """Single step along an impact dependency chain."""
    source_node_id: str
    source_name: str
    source_type: str
    edge_type: str
    target_node_id: Optional[str] = None
    target_name: Optional[str] = None
    confidence: float = 1.0
    resolution_status: str = "RESOLVED"


class DependencyPathItem(BaseModel):
    """Explainable dependency path connecting a changed target to an impacted consumer."""
    target_name: str = Field(..., description="Name of the changed upstream entity")
    impacted_node_id: str = Field(..., description="UUID of the affected downstream node")
    impacted_name: str = Field(..., description="Name of the affected downstream entity")
    impacted_file_path: Optional[str] = Field(None, description="File path of the affected consumer")
    depth: int = Field(..., description="Hop distance from target (1 = direct consumer)")
    hops: List[DependencyHop] = Field(default_factory=list, description="Ordered relationship hops")
    explanation: str = Field(..., description="Human-readable path breadcrumb: A -> CALLS -> B")


class ImpactedNodeItem(BaseModel):
    """Detailed metadata for a code entity identified in the blast radius."""
    node_id: str
    node_type: str
    qualified_name: str
    name: str
    file_path: Optional[str] = None
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    depth: int
    is_direct: bool
    primary_reason: str
    confidence: float
    resolution_status: str
    paths_count: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecommendedTestItem(BaseModel):
    """Test suite or test file recommended for execution to verify changes."""
    test_file_path: str
    test_framework: Optional[str] = "pytest"
    recommendation_type: str = "CONFIRMED"  # CONFIRMED (graph edge), HEURISTIC (naming pattern)
    confidence: float = 1.0
    reason: str
    target_symbol_or_file: str


class UnresolvedWarningItem(BaseModel):
    """Advisory warning regarding unresolved, ambiguous, or external references."""
    edge_id: Optional[str] = None
    source_node_name: str
    source_file: Optional[str] = None
    target_symbol: str
    edge_type: str
    resolution_status: str
    message: str


class ImpactScoreBreakdown(BaseModel):
    """Deterministic contributing factors to the 0-100 impact score."""
    files_score: int = Field(..., description="Contribution from affected files count (0-30)")
    symbols_score: int = Field(..., description="Contribution from direct and transitive symbols (0-25)")
    depth_score: int = Field(..., description="Contribution from max traversal depth and paths (0-20)")
    coupling_score: int = Field(..., description="Contribution from cross-module/package spread (0-15)")
    untested_penalty: int = Field(..., description="Penalty if no tests are mapped to blast radius (0-10)")


class ImpactSummaryMetrics(BaseModel):
    """High-level counters summarizing blast radius size."""
    total_affected_files: int
    total_affected_symbols: int
    direct_impact_count: int
    transitive_impact_count: int
    recommended_tests_count: int
    unresolved_warnings_count: int


class ImpactAnalysisRequest(BaseModel):
    """Request payload to calculate blast radius and change impact."""
    file_paths: List[str] = Field(default_factory=list, description="Repository-relative file paths to analyze")
    symbol_ids: List[str] = Field(default_factory=list, description="Node UUIDs to analyze")
    qualified_names: List[str] = Field(default_factory=list, description="Qualified symbol names to analyze")
    max_depth: int = Field(3, ge=1, le=5, description="Maximum traversal depth (default 3, max 5)")
    include_tests: bool = Field(True, description="Whether to discover and map relevant test suites")
    max_impacted_nodes: int = Field(100, ge=1, le=200, description="Maximum impacted nodes to return")


class ImpactAnalysisResponse(BaseModel):
    """Full blast radius and change impact report."""
    repository_id: str
    commit_sha: Optional[str] = None
    is_stale: bool = False
    staleness_reason: Optional[str] = None
    targets: List[ImpactTarget] = Field(default_factory=list)
    impact_score: int = Field(..., description="Deterministic impact severity score (0-100)")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN")
    confidence: float = Field(..., description="Overall confidence rating (0.0 to 1.0)")
    score_explanation: str = Field(..., description="Human-readable explanation of impact severity")
    score_breakdown: ImpactScoreBreakdown
    summary: ImpactSummaryMetrics
    affected_files: List[str] = Field(default_factory=list)
    affected_packages: List[str] = Field(default_factory=list, description="Unique names of packages affected across workspaces")
    cross_package_boundaries: bool = Field(False, description="Whether impact propagates across package boundaries")
    impacted_nodes: List[ImpactedNodeItem] = Field(default_factory=list)
    dependency_paths: List[DependencyPathItem] = Field(default_factory=list)
    recommended_tests: List[RecommendedTestItem] = Field(default_factory=list)
    unresolved_warnings: List[UnresolvedWarningItem] = Field(default_factory=list)
    execution_duration_seconds: float = 0.0
