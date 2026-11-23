"""Pydantic schemas for Phase 10 Stage 10.5: Architectural Drift & Technical Debt Intelligence Engine."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DriftViolationItem(BaseModel):
    """Specific architectural drift violation."""
    id: str = Field(..., description="Unique violation ID")
    rule_id: str = Field(..., description="Rule code: layering_violation, circular_dependency, package_boundary, convention_deviation, security_boundary")
    category: str = Field(..., description="layering, dependency, convention, security, pattern")
    name: str = Field(..., description="Human-readable title of the violation")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the violation finding")
    source_file: str = Field(..., description="Originating file path")
    target_file: Optional[str] = Field(default=None, description="Target or imported file path")
    source_symbol: Optional[str] = Field(default=None, description="Offending function or class")
    target_symbol: Optional[str] = Field(default=None, description="Referenced function or class")
    line_number: int = Field(default=1, description="Line number of violation")
    explanation: str = Field(..., description="Detailed explanation of why this constitutes architectural drift")
    remediation_recommendation: str = Field(..., description="Specific guidance to resolve violation")
    evidence_snippet: Optional[str] = Field(default=None, description="Sanitized code excerpt demonstrating the violation")


class ArchitectureDriftResponse(BaseModel):
    """Aggregated architecture drift summary comparing current state to baseline."""
    repository_id: str
    commit_sha: Optional[str] = None
    baseline_commit_sha: Optional[str] = None
    drift_status: str = Field(..., description="HEALTHY, DRIFT_DETECTED, CRITICAL_DRIFT")
    total_violations: int = 0
    critical_violations: int = 0
    high_violations: int = 0
    medium_violations: int = 0
    low_violations: int = 0
    violations: List[DriftViolationItem] = Field(default_factory=list)
    resolved_violations: List[DriftViolationItem] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    is_stale: bool = False
    last_analyzed_at: Optional[str] = None


class TechnicalDebtFindingItem(BaseModel):
    """Detailed technical debt finding."""
    finding_id: str = Field(..., description="Unique finding ID")
    category: str = Field(..., description="duplication, complexity, dependency, maintainability, test")
    title: str = Field(..., description="Finding title")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Measurement confidence")
    file_path: str = Field(..., description="Primary affected file")
    symbol_name: Optional[str] = Field(default=None, description="Affected symbol or function")
    line_number: int = Field(default=1, description="Line number")
    line_end: Optional[int] = Field(default=None, description="End line number")
    measured_metric: Dict[str, Any] = Field(default_factory=dict, description="Concrete metric (e.g. lines=120, complexity=18, scc_size=3)")
    explanation: str = Field(..., description="Detailed debt rationale")
    remediation: str = Field(..., description="Actionable remediation advice")
    potential_impact: str = Field(..., description="Operational or maintenance consequence")
    detection_method: str = Field(..., description="AST_ANALYSIS, GRAPH_CYCLE, TOKEN_SIMILARITY, STATIC_INSPECTION")
    evidence_snippet: Optional[str] = Field(default=None, description="Redacted code evidence")


class TechnicalDebtDimensionScores(BaseModel):
    """Individual scores across the 5 debt dimensions (0-100 each)."""
    complexity: float = 0.0
    duplication: float = 0.0
    dependency: float = 0.0
    architecture_drift: float = 0.0
    test_debt: float = 0.0
    maintainability: float = 0.0


class TechnicalDebtSummaryResponse(BaseModel):
    """Unified repository technical debt score and metric breakdown."""
    repository_id: str
    commit_sha: Optional[str] = None
    overall_debt_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score (0-100)")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW, CLEAN")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Aggregate confidence rating")
    dimension_scores: TechnicalDebtDimensionScores
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    top_findings: List[TechnicalDebtFindingItem] = Field(default_factory=list)
    is_stale: bool = False
    last_analyzed_at: Optional[str] = None


class TechnicalDebtFindingsResponse(BaseModel):
    """Paginated list of technical debt findings with filters."""
    repository_id: str
    total_count: int
    limit: int
    offset: int
    findings: List[TechnicalDebtFindingItem]


class TechnicalDebtTrendItem(BaseModel):
    """Single historical technical debt data point."""
    commit_sha: str
    analyzed_at: str
    overall_debt_score: float
    severity: str
    critical_findings: int
    total_findings: int


class TechnicalDebtTrendsResponse(BaseModel):
    """Historical technical debt progression over commits."""
    repository_id: str
    trends: List[TechnicalDebtTrendItem]
