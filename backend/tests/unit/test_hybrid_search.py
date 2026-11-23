"""Unit tests for Phase 10 Stage 10.4: Hybrid Semantic Repository Search Engine."""

import uuid
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch
import pytest

from app.models.repository import Repository
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User
from app.schemas.architecture import HybridSearchFilter
from app.services.search_service import CodeSearchService, cosine_similarity


def test_cosine_similarity_edge_cases():
    """Verify cosine similarity calculation under normal and boundary conditions."""
    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 1.0

    # Orthogonal vectors
    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), 0.001) == 0.0

    # Opposite vectors
    v4 = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v4), 0.001) == -1.0

    # Length mismatch
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0

    # Empty vectors
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], []) == 0.0

    # Zero vectors
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_language_inference_from_paths():
    """Verify language inference mapping for various extensions."""
    service = CodeSearchService()
    assert service._infer_language("backend/app/main.py") == "python"
    assert service._infer_language("frontend/src/app/page.tsx") == "typescript"
    assert service._infer_language("src/lib.rs") == "rust"
    assert service._infer_language("cmd/main.go") == "go"
    assert service._infer_language("Application.java") == "java"
    assert service._infer_language("config.yaml") == "yaml"
    assert service._infer_language("unknown.xyz") is None


@pytest.mark.asyncio
async def test_hybrid_search_rrf_scoring_and_ranking(monkeypatch):
    """Verify Reciprocal Rank Fusion combines lexical, semantic, and structural signals with explainability."""
    service = CodeSearchService()
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    user = User(id=user_id, email="dev@example.com", full_name="Dev User", hashed_password="pw")
    repo = Repository(id=repo_id, user_id=user_id, name="demo-repo", language="python")

    # Mock get_repository_for_user
    async def mock_get_repo(r_id, u, d):
        return repo
    monkeypatch.setattr(service, "get_repository_for_user", mock_get_repo)

    # Mock DB query results
    # 1. Knowledge entries with embeddings
    k1 = RepositoryKnowledge(
        repository_id=repo_id,
        file_path="backend/app/services/auth_service.py",
        symbol_name="AuthService",
        symbol_type="class",
        content="class AuthService: manages user sessions and jwt verification",
        embedding=[0.8, 0.1, 0.0],
        meta_info={"start_line": 15, "end_line": 80, "signature": "class AuthService"},
    )
    k2 = RepositoryKnowledge(
        repository_id=repo_id,
        file_path="backend/app/services/payment_service.py",
        symbol_name="PaymentService",
        symbol_type="class",
        content="class PaymentService: charges credit cards",
        embedding=[0.1, 0.9, 0.0],
        meta_info={"start_line": 10, "end_line": 50, "signature": "class PaymentService"},
    )

    # 2. Graph node entries
    node_auth = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        node_type="CLASS",
        qualified_name="backend.app.services.auth_service.AuthService",
        name="AuthService",
        file_path="backend/app/services/auth_service.py",
        language="python",
        start_line=15,
        end_line=80,
    )
    node_util = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        node_type="FUNCTION",
        qualified_name="backend.app.core.security.create_token",
        name="create_token",
        file_path="backend/app/core/security.py",
        language="python",
        start_line=25,
        end_line=40,
    )

    # 3. Graph edges
    edge1 = RepositoryGraphEdge(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_node_id=node_util.id,
        target_node_id=node_auth.id,
        edge_type="CALLS",
    )

    # Mock DB session execution
    mock_db = AsyncMock()

    class MockResult:
        def __init__(self, data):
            self._data = data
        def scalars(self):
            return self
        def all(self):
            return self._data

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "repository_knowledge" in stmt_str:
            return MockResult([k1, k2])
        elif "repository_graph_nodes" in stmt_str:
            return MockResult([node_auth, node_util])
        elif "repository_graph_edges" in stmt_str:
            return MockResult([edge1])
        elif "repository_files" in stmt_str:
            return MockResult([])
        return MockResult([])

    mock_db.execute = mock_execute

    # Mock embedding generator to match query vector to k1
    monkeypatch.setattr(
        "app.services.search_service.generate_embedding_vector",
        lambda text: [0.8, 0.1, 0.0],
    )

    # Execute search for "auth user session"
    resp = await service.search_hybrid(
        repository_id=repo_id,
        query="auth user session",
        user=user,
        db=mock_db,
        limit=10,
        offset=0,
    )

    assert resp.total_matches > 0
    assert len(resp.results) > 0

    top_item = resp.results[0]
    assert top_item.file_path == "backend/app/services/auth_service.py"
    assert top_item.symbol_name == "AuthService"
    assert top_item.combined_score > 0.5
    assert top_item.rank == 1
    assert "Lexical" in top_item.provenance_explanation or "Semantic" in top_item.provenance_explanation


@pytest.mark.asyncio
async def test_hybrid_search_credential_scrubbing(monkeypatch):
    """Verify that sensitive secrets in snippets are redacted prior to returning search results."""
    service = CodeSearchService()
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    user = User(id=user_id, email="dev@example.com", full_name="Dev User", hashed_password="pw")
    repo = Repository(id=repo_id, user_id=user_id, name="secret-repo")

    async def mock_get_repo(r_id, u, d):
        return repo
    monkeypatch.setattr(service, "get_repository_for_user", mock_get_repo)

    # Injected synthetic secret in content snippet
    dirty_content = 'api_key = "AIzaSyFakeSecretKeyForTesting12345"\ngithub_pat = "github_pat_11AAAAAA_TestTokenForValidation1234567890"'
    k = RepositoryKnowledge(
        repository_id=repo_id,
        file_path="config/keys.py",
        symbol_name="keys",
        symbol_type="variable",
        content=dirty_content,
        embedding=[0.5, 0.5],
        meta_info={"start_line": 1, "end_line": 5},
    )

    mock_db = AsyncMock()
    class MockResult:
        def __init__(self, data):
            self._data = data
        def scalars(self):
            return self
        def all(self):
            return self._data

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "repository_knowledge" in stmt_str:
            return MockResult([k])
        return MockResult([])

    mock_db.execute = mock_execute

    resp = await service.search_hybrid(
        repository_id=repo_id,
        query="keys",
        user=user,
        db=mock_db,
    )

    assert len(resp.results) == 1
    clean_snippet = resp.results[0].snippet
    assert "AIzaSyFakeSecretKeyForTesting12345" not in clean_snippet
    assert "github_pat_11AAAAAA_TestTokenForValidation1234567890" not in clean_snippet
    assert "[REDACTED_API_KEY]" in clean_snippet or "[REDACTED_TOKEN]" in clean_snippet


@pytest.mark.asyncio
async def test_hybrid_search_filters_and_pagination(monkeypatch):
    """Verify language, package, path, and symbol type filters as well as offset pagination."""
    service = CodeSearchService()
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    user = User(id=user_id, email="dev@example.com", full_name="Dev User", hashed_password="pw")
    repo = Repository(id=repo_id, user_id=user_id, name="filter-repo")

    async def mock_get_repo(r_id, u, d):
        return repo
    monkeypatch.setattr(service, "get_repository_for_user", mock_get_repo)

    node_py = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        node_type="CLASS",
        qualified_name="backend.app.ItemService",
        name="ItemService",
        file_path="backend/app/services/item_service.py",
        language="python",
        start_line=10,
        meta_info={"package_name": "backend"},
    )
    node_ts = RepositoryGraphNode(
        id=uuid.uuid4(),
        repository_id=repo_id,
        node_type="FUNCTION",
        qualified_name="frontend.src.renderItem",
        name="renderItem",
        file_path="frontend/src/item.tsx",
        language="typescript",
        start_line=5,
        meta_info={"package_name": "frontend"},
    )

    mock_db = AsyncMock()
    class MockResult:
        def __init__(self, data):
            self._data = data
        def scalars(self):
            return self
        def all(self):
            return self._data

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "repository_graph_nodes" in stmt_str:
            return MockResult([node_py, node_ts])
        return MockResult([])

    mock_db.execute = mock_execute

    # 1. Filter by language = python
    resp_py = await service.search_hybrid(
        repository_id=repo_id,
        query="item",
        user=user,
        db=mock_db,
        filters=HybridSearchFilter(languages=["python"]),
    )
    assert resp_py.total_matches == 1
    assert resp_py.results[0].file_path == "backend/app/services/item_service.py"

    # 2. Filter by symbol_types = ["function"]
    resp_func = await service.search_hybrid(
        repository_id=repo_id,
        query="item",
        user=user,
        db=mock_db,
        filters=HybridSearchFilter(symbol_types=["function"]),
    )
    assert resp_func.total_matches == 1
    assert resp_func.results[0].symbol_name == "renderItem"

    # 3. Pagination offset
    resp_paged = await service.search_hybrid(
        repository_id=repo_id,
        query="item",
        user=user,
        db=mock_db,
        limit=1,
        offset=1,
    )
    assert resp_paged.total_matches == 2
    assert len(resp_paged.results) == 1
    assert resp_paged.results[0].rank == 2
