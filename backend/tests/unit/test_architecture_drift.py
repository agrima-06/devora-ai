"""Unit tests for Phase 10 Stage 10.5: Architecture Drift Service."""

import uuid
from typing import Any, Dict, List
import pytest

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.schemas.drift import DriftViolationItem
from app.services.architecture_drift_service import ArchitectureDriftService


def test_drift_status_resolution():
    """Verify drift status severity aggregation."""
    service = ArchitectureDriftService()

    # Empty violations -> HEALTHY
    assert service._determine_drift_status([]) == "HEALTHY"

    # Only low violations -> DRIFT_DETECTED
    assert service._determine_drift_status([{"severity": "LOW"}]) == "DRIFT_DETECTED"

    # Medium violations -> DRIFT_DETECTED
    assert service._determine_drift_status([{"severity": "MEDIUM"}]) == "DRIFT_DETECTED"

    # One critical violation -> CRITICAL_DRIFT
    assert service._determine_drift_status([{"severity": "CRITICAL"}]) == "CRITICAL_DRIFT"

    # 3 High violations -> CRITICAL_DRIFT
    assert service._determine_drift_status([
        {"severity": "HIGH"},
        {"severity": "HIGH"},
        {"severity": "HIGH"},
    ]) == "CRITICAL_DRIFT"


def test_detect_layering_violations():
    """Verify detection of API layer directly querying database bypassing service layer."""
    service = ArchitectureDriftService()
    repo_id = uuid.uuid4()

    code = """from fastapi import APIRouter
router = APIRouter()
@router.get("/orders")
async def get_orders(db):
    res = await db.execute(select(Order))
    return res
"""
    knowledge = [
        RepositoryKnowledge(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="backend/app/api/v1/orders.py",
            symbol_name="get_orders",
            symbol_type="function",
            content=code,
            embedding=[0.0] * 768,
            meta_info={"start_line": 1},
        )
    ]

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "knowledge": knowledge,
        "nodes": [],
        "edges": [],
        "files": [],
        "file_paths": ["backend/app/api/v1/orders.py"],
    }

    violations = service._detect_layering_violations(ev)
    assert len(violations) >= 1
    v = violations[0]
    assert v.rule_id == "layering_violation"
    assert v.category == "layering"
    assert v.source_file == "backend/app/api/v1/orders.py"
    assert "service layer" in v.remediation_recommendation.lower() or "service" in v.explanation.lower()


def test_detect_circular_dependencies():
    """Verify detection of cyclic dependency graphs."""
    service = ArchitectureDriftService()
    repo_id = uuid.uuid4()

    node_a = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="AuthService",
        qualified_name="app.services.auth.AuthService",
        file_path="app/services/auth.py",
    )
    node_b = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="UserService",
        qualified_name="app.services.user.UserService",
        file_path="app/services/user.py",
    )

    edge_1 = RepositoryGraphEdge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_node_id=node_a.id,
        target_node_id=node_b.id,
        edge_type="DEPENDS_ON",
    )
    edge_2 = RepositoryGraphEdge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_node_id=node_b.id,
        target_node_id=node_a.id,
        edge_type="DEPENDS_ON",
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "nodes": [node_a, node_b],
        "edges": [edge_1, edge_2],
        "knowledge": [],
        "files": [],
        "file_paths": [],
    }

    violations = service._detect_circular_dependencies(ev)
    assert len(violations) >= 1
    v = violations[0]
    assert v.rule_id == "circular_dependency"
    assert v.category == "dependency"
    assert v.severity == "CRITICAL"
    assert "circular" in v.explanation.lower() or "cycle" in v.name.lower()


def test_detect_package_boundary_breaches():
    """Verify detection of illegal deep imports into private internal modules across packages."""
    service = ArchitectureDriftService()
    repo_id = uuid.uuid4()

    node_src = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="BillingService",
        qualified_name="packages.billing.BillingService",
        file_path="packages/billing/service.py",
        meta_info={"package_name": "billing"},
    )
    node_tgt = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="internal_auth_key",
        qualified_name="packages.auth.internal._keys.internal_auth_key",
        file_path="packages/auth/internal/_keys.py",
        meta_info={"package_name": "auth"},
    )

    edge = RepositoryGraphEdge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_node_id=node_src.id,
        target_node_id=node_tgt.id,
        edge_type="IMPORTS",
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "nodes": [node_src, node_tgt],
        "edges": [edge],
        "knowledge": [],
        "files": [],
        "file_paths": [],
    }

    violations = service._detect_package_boundary_violations(ev)
    assert len(violations) >= 1
    v = violations[0]
    assert v.rule_id == "package_boundary"
    assert v.severity == "HIGH"
    assert "encapsulation" in v.explanation.lower() or "internal" in v.name.lower()


def test_detect_convention_deviations():
    """Verify detection of naming and structure convention violations."""
    service = ArchitectureDriftService()
    repo_id = uuid.uuid4()

    node_svc = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="PaymentManager",
        node_type="CLASS",
        file_path="backend/app/services/payment_manager.py",
        start_line=1,
    )

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "nodes": [node_svc],
        "edges": [],
        "knowledge": [],
        "files": [],
        "file_paths": [
            "backend/app/services/payment_manager.py",
            "backend/app/api/legacy_payments.py",
        ],
    }

    violations = service._detect_convention_violations(ev)
    assert len(violations) >= 2
    rule_ids = [v.rule_id for v in violations]
    assert "convention_deviation" in rule_ids


def test_detect_security_boundary_bypasses():
    """Verify detection of bypassing gateway abstraction to make direct raw LLM API calls."""
    service = ArchitectureDriftService()
    repo_id = uuid.uuid4()

    code = """import google.generativeai as genai

def generate():
    model = genai.GenerativeModel("gemini-1.5-pro")
    return model.generate_content("hello")
"""
    knowledge = [
        RepositoryKnowledge(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="backend/app/agents/specialists/rogue_agent.py",
            symbol_name="generate",
            symbol_type="function",
            content=code,
            embedding=[0.0] * 768,
            meta_info={"start_line": 1},
        )
    ]

    ev = {
        "repository": Repository(id=repo_id, name="demo"),
        "knowledge": knowledge,
        "nodes": [],
        "edges": [],
        "files": [],
        "file_paths": ["backend/app/agents/specialists/rogue_agent.py"],
    }

    violations = service._detect_security_boundary_violations(ev)
    assert len(violations) >= 1
    v = violations[0]
    assert v.rule_id == "security_boundary"
    assert v.severity == "CRITICAL"
    assert "ModelGateway" in v.remediation_recommendation or "gateway" in v.remediation_recommendation.lower()
