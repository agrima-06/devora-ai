"""Pydantic schemas for Phase 10 Stage 10.4: Semantic Architecture & Pattern Inference Engine."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HybridSearchFilter(BaseModel):
    """Filters applicable to hybrid repository searches."""
    languages: Optional[List[str]] = Field(default=None, description="Filter results by programming language")
    packages: Optional[List[str]] = Field(default=None, description="Filter results by workspace package name")
    file_paths: Optional[List[str]] = Field(default=None, description="Filter results by file path prefixes or globs")
    symbol_types: Optional[List[str]] = Field(default=None, description="Filter results by symbol type (class, function, method, interface)")


class HybridSearchRequest(BaseModel):
    """Search request combining lexical, semantic, and structural retrieval."""
    query: str = Field(..., min_length=1, description="Natural language search question or exact symbol/code snippet")
    filters: Optional[HybridSearchFilter] = Field(default=None, description="Optional scope filters")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results to return")
    offset: int = Field(default=0, ge=0, description="Result offset for pagination")
    lexical_weight: float = Field(default=0.35, ge=0.0, le=1.0, description="Weight assigned to BM25/keyword ranking")
    semantic_weight: float = Field(default=0.45, ge=0.0, le=1.0, description="Weight assigned to vector similarity ranking")
    structural_weight: float = Field(default=0.20, ge=0.0, le=1.0, description="Weight assigned to graph centrality & topology")


class HybridSearchResultItem(BaseModel):
    """Single ranked search match with multi-modal provenance information."""
    file_path: str
    line_number: int = 1
    line_end: Optional[int] = None
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    package_name: Optional[str] = None
    language: Optional[str] = None
    snippet: str
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    structural_score: float = 0.0
    combined_score: float = 0.0
    rank: int = 1
    provenance_explanation: str


class HybridSearchResponse(BaseModel):
    """Aggregated hybrid search response with explainable ranking."""
    repository_id: str
    query: str
    total_matches: int
    limit: int
    offset: int
    results: List[HybridSearchResultItem]
    search_duration_seconds: float = 0.0


class ArchitectureConventionItem(BaseModel):
    """Empirically discovered repository coding convention."""
    name: str = Field(..., description="Convention title (e.g. Service Layer Suffix, Dependency Injection)")
    category: str = Field(..., description="service, api, database, error, test, agent")
    description: str = Field(..., description="Detailed specification of the convention")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Empirical confidence score")
    supporting_examples: List[str] = Field(default_factory=list, description="Exemplar code snippets or signatures")
    relevant_paths: List[str] = Field(default_factory=list, description="Exemplar source file paths")
    applicability_scope: str = Field(default="REPOSITORY_WIDE", description="Scope of applicability (e.g. REPOSITORY_WIDE, PACKAGE, BACKEND)")
    potential_exceptions: List[str] = Field(default_factory=list, description="Known exceptions or non-conforming paths")


class ArchitecturePatternItem(BaseModel):
    """Inferred architectural pattern record grounded in empirical repository evidence."""
    id: Optional[str] = None
    pattern_id: str = Field(..., description="Unique slug: layered_architecture, service_layer, modular_monolith, etc.")
    category: str = Field(..., description="application, backend, frontend, ai_agent, data")
    name: str = Field(..., description="Human-readable pattern title")
    description: str = Field(..., description="Detailed description of pattern manifestation")
    evidence_status: str = Field(..., description="CONFIRMED, STRONGLY_SUPPORTED, POSSIBLE, INSUFFICIENT_EVIDENCE")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Deterministic confidence rating")
    supporting_files: List[str] = Field(default_factory=list, description="Files embodying the pattern")
    supporting_symbols: List[str] = Field(default_factory=list, description="Symbols, classes, or interfaces demonstrating the pattern")
    supporting_relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Graph edges illustrating relationship")
    supporting_config: Dict[str, Any] = Field(default_factory=dict, description="Configuration or manifest evidence")
    counterexamples: List[str] = Field(default_factory=list, description="Counterexamples or non-conforming modules")
    conventions: List[ArchitectureConventionItem] = Field(default_factory=list, description="Conventions derived from pattern")


class ArchitectureSummaryResponse(BaseModel):
    """Unified repository architectural profile and pattern catalog."""
    repository_id: str
    primary_language: Optional[str] = None
    current_commit_sha: Optional[str] = None
    frameworks: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    manifests: List[str] = Field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    architecture_summary: Optional[str] = None
    coding_conventions: Optional[str] = None
    total_patterns: int = 0
    confirmed_patterns_count: int = 0
    patterns: List[ArchitecturePatternItem] = Field(default_factory=list)
    conventions: List[ArchitectureConventionItem] = Field(default_factory=list)
    is_stale: bool = False
    last_analyzed_at: Optional[str] = None


class ArchitectureAskRequest(BaseModel):
    """Natural-language architectural question request."""
    question: str = Field(..., min_length=2, description="Architectural question (e.g. How are database sessions managed?)")
    context_limit: int = Field(default=6, ge=1, le=15, description="Number of evidence code matches to incorporate into response context")


class ArchitectureAskResponse(BaseModel):
    """Evidence-backed architectural explanation."""
    repository_id: str
    question: str
    answer: str
    confidence: float
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_files: List[str] = Field(default_factory=list)
    inferred_patterns_referenced: List[str] = Field(default_factory=list)
