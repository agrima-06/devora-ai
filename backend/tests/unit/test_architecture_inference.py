"""Unit tests for Phase 10 Stage 10.4: Architecture Pattern Inference & Convention Discovery."""

import uuid
from typing import Any, Dict, List
from unittest.mock import AsyncMock
import pytest

from app.models.repository import Repository
from app.models.repository_architecture_pattern import RepositoryArchitecturePattern
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User
from app.schemas.architecture import (
    ArchitectureAskRequest,
    ArchitectureConventionItem,
    ArchitecturePatternItem,
    HybridSearchResultItem,
    HybridSearchResponse,
)
from app.services.architecture_inference_service import ArchitectureInferenceService


def test_status_resolution():
    """Verify confidence to status mapping bands."""
    service = ArchitectureInferenceService()
    assert service._resolve_status(0.95) == "CONFIRMED"
    assert service._resolve_status(0.85) == "CONFIRMED"
    assert service._resolve_status(0.80) == "STRONGLY_SUPPORTED"
    assert service._resolve_status(0.70) == "STRONGLY_SUPPORTED"
    assert service._resolve_status(0.65) == "POSSIBLE"
    assert service._resolve_status(0.40) == "POSSIBLE"
    assert service._resolve_status(0.35) == "INSUFFICIENT_EVIDENCE"
    assert service._resolve_status(0.10) == "INSUFFICIENT_EVIDENCE"


def test_detect_layered_architecture_and_service_layer():
    """Verify empirical detection of Layered Architecture and Service Layer patterns."""
    service = ArchitectureInferenceService()
    repo_id = uuid.uuid4()
    repo = Repository(id=repo_id, name="layered-app", language="python")

    evidence = {
        "repository": repo,
        "file_paths": [
            "backend/app/api/v1/auth.py",
            "backend/app/api/v1/tasks.py",
            "backend/app/services/auth_service.py",
            "backend/app/services/task_service.py",
            "backend/app/models/user.py",
            "backend/app/models/task.py",
        ],
        "knowledge": [],
        "nodes": [
            RepositoryGraphNode(name="AuthService", node_type="CLASS", file_path="backend/app/services/auth_service.py"),
            RepositoryGraphNode(name="TaskService", node_type="CLASS", file_path="backend/app/services/task_service.py"),
        ],
        "edges": [],
        "frameworks": ["fastapi", "sqlalchemy"],
        "configs": {},
        "meta": {},
    }

    patterns = service._detect_all_patterns(evidence)
    p_map = {p.pattern_id: p for p in patterns}

    # Layered architecture should be CONFIRMED (all 3 tiers present: api, services, models)
    assert "layered_architecture" in p_map
    layered = p_map["layered_architecture"]
    assert layered.evidence_status == "CONFIRMED"
    assert layered.confidence_score >= 0.85
    assert len(layered.supporting_files) > 0

    # Service layer pattern should be CONFIRMED or STRONGLY_SUPPORTED
    assert "service_layer" in p_map
    svc_pattern = p_map["service_layer"]
    assert svc_pattern.evidence_status in ("CONFIRMED", "STRONGLY_SUPPORTED")
    assert "AuthService" in svc_pattern.supporting_symbols


def test_insufficient_evidence_never_forced():
    """Verify that absent patterns are flagged INSUFFICIENT_EVIDENCE and not falsely confirmed."""
    service = ArchitectureInferenceService()
    repo_id = uuid.uuid4()
    repo = Repository(id=repo_id, name="flat-script", language="python")

    # Minimal flat repository
    evidence = {
        "repository": repo,
        "file_paths": ["script.py", "requirements.txt"],
        "knowledge": [],
        "nodes": [],
        "edges": [],
        "frameworks": [],
        "configs": {},
        "meta": {},
    }

    patterns = service._detect_all_patterns(evidence)
    p_map = {p.pattern_id: p for p in patterns}

    # Clean architecture should be INSUFFICIENT_EVIDENCE
    clean_p = p_map["clean_architecture"]
    assert clean_p.evidence_status == "INSUFFICIENT_EVIDENCE"
    assert clean_p.confidence_score < 0.40

    # Repository pattern should be INSUFFICIENT_EVIDENCE
    repo_p = p_map["repository_pattern"]
    assert repo_p.evidence_status == "INSUFFICIENT_EVIDENCE"
    assert repo_p.confidence_score < 0.40


def test_convention_discovery():
    """Verify empirical convention extraction across services, APIs, error handling and testing."""
    service = ArchitectureInferenceService()
    repo_id = uuid.uuid4()
    repo = Repository(id=repo_id, name="devora-backend", language="python")

    evidence = {
        "repository": repo,
        "file_paths": [
            "backend/app/services/workflow_service.py",
            "backend/app/api/v1/tasks.py",
            "backend/app/core/exceptions.py",
            "backend/tests/unit/test_tasks.py",
        ],
        "knowledge": [],
        "nodes": [
            RepositoryGraphNode(name="WorkflowService", node_type="CLASS", file_path="backend/app/services/workflow_service.py"),
            RepositoryGraphNode(name="DevoraException", node_type="CLASS", file_path="backend/app/core/exceptions.py"),
        ],
        "edges": [],
        "frameworks": ["fastapi", "pytest"],
        "configs": {},
        "meta": {},
    }

    conventions = service._discover_conventions(evidence, [])
    categories = {c.category for c in conventions}

    assert "service" in categories
    assert "api" in categories
    assert "database" in categories
    assert "error" in categories
    assert "test" in categories

    service_conv = next(c for c in conventions if c.category == "service")
    assert "Service Class & File Naming" in service_conv.name
    assert service_conv.confidence >= 0.90


@pytest.mark.asyncio
async def test_ask_architecture_evidence_backed(monkeypatch):
    """Verify Ask Your Codebase synthesizes an evidence-grounded answer with confidence and references."""
    mock_search = AsyncMock()
    service = ArchitectureInferenceService(search_service=mock_search)

    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    user = User(id=user_id, email="dev@example.com", full_name="Dev User", hashed_password="pw")
    repo = Repository(id=repo_id, user_id=user_id, name="devora-repo", language="python")

    async def mock_get_repo(r_id, u, d):
        return repo
    monkeypatch.setattr(service, "get_repository_for_user", mock_get_repo)

    # Mock get_architecture_summary returning confirmed service layer pattern
    pattern = ArchitecturePatternItem(
        pattern_id="service_layer",
        category="application",
        name="Service Layer Pattern",
        description="Dedicated business service classes encapsulating domain workflows.",
        evidence_status="CONFIRMED",
        confidence_score=0.95,
        supporting_files=["backend/app/services/workflow_service.py"],
    )
    conv = ArchitectureConventionItem(
        name="Service Class & File Naming",
        category="service",
        description="Domain services placed in backend/app/services/.",
        confidence=0.95,
        supporting_examples=["WorkflowService"],
    )

    from app.schemas.architecture import ArchitectureSummaryResponse
    summary_resp = ArchitectureSummaryResponse(
        repository_id=str(repo_id),
        total_patterns=1,
        confirmed_patterns_count=1,
        patterns=[pattern],
        conventions=[conv],
        is_stale=False,
    )
    async def mock_summary(r_id, u, d):
        return summary_resp
    monkeypatch.setattr(service, "get_architecture_summary", mock_summary)

    # Mock hybrid search results
    search_item = HybridSearchResultItem(
        file_path="backend/app/services/workflow_service.py",
        line_number=20,
        symbol_name="WorkflowService",
        snippet="class WorkflowService:\n    async def execute_task(): pass",
        combined_score=0.89,
        rank=1,
        provenance_explanation="Lexical & Semantic match",
    )
    mock_search.search_hybrid.return_value = HybridSearchResponse(
        repository_id=str(repo_id),
        query="service layer",
        total_matches=1,
        limit=6,
        offset=0,
        results=[search_item],
    )

    req = ArchitectureAskRequest(question="How is the service layer structured?", context_limit=6)
    ask_resp = await service.ask_architecture(
        repository_id=repo_id,
        request=req,
        user=user,
        db=AsyncMock(),
    )

    assert ask_resp.confidence >= 0.80
    assert "backend/app/services/workflow_service.py" in ask_resp.relevant_files
    assert "Service Layer Pattern" in ask_resp.inferred_patterns_referenced
    assert "WorkflowService" in ask_resp.answer
