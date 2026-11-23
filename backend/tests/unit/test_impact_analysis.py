"""Unit tests for Phase 10 Stage 10.2: Blast Radius and Change Impact Analysis Engine."""
import uuid
from typing import List
import pytest

from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.schemas.impact import (
    DependencyHop,
    DependencyPathItem,
    ImpactAnalysisRequest,
    ImpactScoreBreakdown,
)
from app.services.impact_analysis_service import (
    ImpactAnalysisService,
    VALID_CONSUMER_EDGE_TYPES,
)


def test_valid_consumer_edge_types():
    """Verify that consumer edge types contain key relationships and exclude structural containers."""
    assert "IMPORTS" in VALID_CONSUMER_EDGE_TYPES
    assert "CALLS" in VALID_CONSUMER_EDGE_TYPES
    assert "INHERITS" in VALID_CONSUMER_EDGE_TYPES
    assert "DEPENDS_ON" in VALID_CONSUMER_EDGE_TYPES
    assert "IMPLEMENTS" in VALID_CONSUMER_EDGE_TYPES
    assert "REFERENCES" in VALID_CONSUMER_EDGE_TYPES
    # Structural hierarchy must NEVER propagate blast radius to siblings
    assert "CONTAINS" not in VALID_CONSUMER_EDGE_TYPES


def test_deterministic_scoring_and_severity_bands():
    """Verify deterministic 0-100 scoring logic across severity thresholds."""
    service = ImpactAnalysisService()

    # Case 1: Zero blast radius
    score0, sev0, breakdown0, exp0 = service._calculate_impact_score(
        affected_files_count=0,
        direct_symbols_count=0,
        transitive_symbols_count=0,
        max_depth=0,
        paths_count=0,
        distinct_directories_count=0,
        recommended_tests_count=0,
    )
    assert score0 == 0
    assert sev0 == "UNKNOWN"

    # Case 2: Minimal localized change (Low)
    score_low, sev_low, _, _ = service._calculate_impact_score(
        affected_files_count=1,
        direct_symbols_count=1,
        transitive_symbols_count=0,
        max_depth=1,
        paths_count=1,
        distinct_directories_count=1,
        recommended_tests_count=1,
    )
    assert 1 <= score_low < 30
    assert sev_low == "LOW"

    # Case 3: Moderate localized change (Medium)
    score_med, sev_med, _, _ = service._calculate_impact_score(
        affected_files_count=2,
        direct_symbols_count=2,
        transitive_symbols_count=1,
        max_depth=2,
        paths_count=2,
        distinct_directories_count=1,
        recommended_tests_count=2,
    )
    # files: 12, symbols: 9, depth: 10, coupling: 5, untested: 0 -> total: 36
    assert 30 <= score_med < 60
    assert sev_med == "MEDIUM"

    # Case 4: Significant blast radius (High)
    score_high, sev_high, _, _ = service._calculate_impact_score(
        affected_files_count=4,
        direct_symbols_count=4,
        transitive_symbols_count=2,
        max_depth=2,
        paths_count=4,
        distinct_directories_count=2,
        recommended_tests_count=2,
    )
    # files: 24, symbols: 19, depth: 12, coupling: 10, untested: 0 -> total: 65
    assert 60 <= score_high < 80
    assert sev_high == "HIGH"

    # Case 5: Critical architectural change (Critical)
    score_crit, sev_crit, breakdown_crit, _ = service._calculate_impact_score(
        affected_files_count=10,
        direct_symbols_count=8,
        transitive_symbols_count=12,
        max_depth=4,
        paths_count=15,
        distinct_directories_count=5,
        recommended_tests_count=0,  # untested penalty applies
    )
    assert score_crit >= 80
    assert sev_crit == "CRITICAL"
    assert breakdown_crit.untested_penalty == 10


def test_confidence_calculation_with_unresolved_edges():
    """Verify that confidence rating discounts unresolved and external edges appropriately."""
    service = ImpactAnalysisService()
    repo_id = uuid.uuid4()
    node1_id = uuid.uuid4()
    node2_id = uuid.uuid4()

    edge_resolved = RepositoryGraphEdge(
        repository_id=repo_id,
        source_node_id=node1_id,
        target_node_id=node2_id,
        edge_type="IMPORTS",
        confidence=1.0,
        resolution_status="RESOLVED",
    )
    edge_external = RepositoryGraphEdge(
        repository_id=repo_id,
        source_node_id=node1_id,
        target_node_id=None,
        edge_type="IMPORTS",
        confidence=0.8,
        resolution_status="EXTERNAL",
    )
    edge_unresolved = RepositoryGraphEdge(
        repository_id=repo_id,
        source_node_id=node1_id,
        target_node_id=None,
        edge_type="CALLS",
        confidence=0.5,
        resolution_status="UNRESOLVED",
    )

    conf_all_resolved = service._calculate_overall_confidence([edge_resolved, edge_resolved])
    assert conf_all_resolved == 1.0

    conf_mixed = service._calculate_overall_confidence([edge_resolved, edge_external, edge_unresolved])
    # Expected: (1.0*1.0 + 0.8*0.8 + 0.5*0.5) / 3 = (1.0 + 0.64 + 0.25) / 3 = 1.89 / 3 = 0.63
    assert conf_mixed < 1.0
    assert 0.60 <= conf_mixed <= 0.65


def test_dependency_path_construction():
    """Verify breadcrumb formatting and hop order."""
    hop1 = DependencyHop(
        source_node_id=str(uuid.uuid4()),
        source_name="api_endpoint",
        source_type="FUNCTION",
        edge_type="CALLS",
        target_name="auth_service",
    )
    hop2 = DependencyHop(
        source_node_id=str(uuid.uuid4()),
        source_name="auth_service",
        source_type="CLASS",
        edge_type="CALLS",
        target_name="verify_token",
    )
    path = DependencyPathItem(
        target_name="verify_token",
        impacted_node_id=str(uuid.uuid4()),
        impacted_name="api_endpoint",
        impacted_file_path="app/api.py",
        depth=2,
        hops=[hop1, hop2],
        explanation="api_endpoint (FUNCTION) -[CALLS]-> auth_service (CLASS) -[CALLS]-> verify_token",
    )
    assert path.depth == 2
    assert len(path.hops) == 2
    assert "api_endpoint" in path.explanation
    assert "verify_token" in path.explanation


def test_workspace_boundary_response_fields():
    """Verify that ImpactAnalysisResponse incorporates affected_packages and cross_package_boundaries."""
    from app.schemas.impact import ImpactAnalysisResponse, ImpactSummaryMetrics

    resp = ImpactAnalysisResponse(
        repository_id=str(uuid.uuid4()),
        impact_score=50,
        severity="MEDIUM",
        confidence=0.9,
        score_explanation="Moderate impact",
        score_breakdown=ImpactScoreBreakdown(
            files_score=15,
            symbols_score=15,
            depth_score=10,
            coupling_score=10,
            untested_penalty=0,
        ),
        summary=ImpactSummaryMetrics(
            total_affected_files=2,
            total_affected_symbols=4,
            direct_impact_count=2,
            transitive_impact_count=2,
            recommended_tests_count=1,
            unresolved_warnings_count=0,
        ),
        affected_files=["packages/core/src/index.ts", "apps/web/src/page.tsx"],
        affected_packages=["@devora/core", "@devora/web"],
        cross_package_boundaries=True,
    )

    assert resp.cross_package_boundaries is True
    assert len(resp.affected_packages) == 2
    assert "@devora/core" in resp.affected_packages
    assert "@devora/web" in resp.affected_packages

