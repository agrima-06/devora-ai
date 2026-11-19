"""Unit tests for Semantic Vector Memory Engine."""
import uuid
import pytest
from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.models.repository import Repository
from app.models.repository_memory import RepositoryMemory
from app.models.user import User
from app.services.memory_service import MemoryService, cosine_similarity


@pytest.fixture(autouse=True)
def mock_gateway():
    mock_prov = MockLLMProvider()
    gw = ModelGateway(provider=mock_prov)
    ModelGateway.set_instance(gw)
    return mock_prov


@pytest.mark.asyncio
async def test_embedding_generation_and_dimension():
    """Verify that semantic embeddings are strictly 768 dimensions and normalized."""
    gw = ModelGateway.get_instance()
    vec = await gw.generate_embedding("Async SQLAlchemy with FastAPI conventions")
    assert len(vec) == 768
    norm = sum(x * x for x in vec)
    assert 0.99 <= norm <= 1.01  # L2 normalized


@pytest.mark.asyncio
async def test_cosine_similarity_properties():
    """Verify cosine similarity properties."""
    v1 = [1.0] + [0.0] * 767
    v2 = [1.0] + [0.0] * 767
    assert cosine_similarity(v1, v2) == 1.0

    v3 = [0.0, 1.0] + [0.0] * 766
    assert cosine_similarity(v1, v3) == 0.0


@pytest.mark.asyncio
async def test_memory_creation_and_deduplication(db_session, test_user, test_repository):
    """Creating a memory with high similarity must update existing rather than duplicating."""
    service = MemoryService()

    # 1. Create initial memory
    mem1 = await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="coding_conventions",
        title="Naming conventions for async handlers",
        content="Always use async def for FastAPI routes and suffix service methods with async.",
        user=test_user,
        db=db_session,
        verification_status="developer_confirmed",
    )
    assert mem1.id is not None
    assert mem1.category == "coding_conventions"
    assert mem1.verification_status == "developer_confirmed"

    # 2. Insert nearly identical content in the same category
    mem2 = await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="coding_conventions",
        title="Naming conventions for async handlers",
        content="Always use async def for FastAPI routes and suffix service methods with async.",
        user=test_user,
        db=db_session,
        deduplicate=True,
    )

    # Must update the existing memory rather than creating a new UUID
    assert mem2.id == mem1.id

    # 3. Verify total memories for repo is exactly 1
    mems = await service.list_memories(test_repository.id, test_user, db_session)
    assert len(mems) == 1


@pytest.mark.asyncio
async def test_semantic_search_and_thresholding(db_session, test_user, test_repository):
    """Semantic search must retrieve relevant memories and respect thresholds."""
    service = MemoryService()

    # Seed 3 distinct memories
    await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="coding_conventions",
        title="Python Error Handling",
        content="Always catch specific exceptions and re-raise DevoraException with structured code.",
        user=test_user,
        db=db_session,
        verification_status="developer_confirmed",
    )
    await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="testing_patterns",
        title="Pytest Async Fixtures",
        content="Use anyio or pytest_asyncio with function scope for database sessions.",
        user=test_user,
        db=db_session,
        verification_status="observed_fact",
    )
    await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="architecture",
        title="PostgreSQL pgvector Store",
        content="All vector columns use pgvector 768-dim with cosine similarity.",
        user=test_user,
        db=db_session,
        verification_status="observed_fact",
    )

    # Search for testing fixtures
    results = await service.search_memories(
        repository_id=test_repository.id,
        query="How should we configure pytest async test fixtures?",
        user=test_user,
        db=db_session,
        limit=2,
    )
    assert len(results) >= 1
    assert any("pytest" in r["content"].lower() or r["category"] == "testing_patterns" for r in results)

    # Search with category filter
    arch_results = await service.search_memories(
        repository_id=test_repository.id,
        query="pgvector database storage",
        user=test_user,
        db=db_session,
        category="architecture",
    )
    assert len(arch_results) >= 1
    assert arch_results[0]["category"] == "architecture"


@pytest.mark.asyncio
async def test_memory_staleness_and_invalidation(db_session, test_user, test_repository):
    """Modifying files or manual stale marking must flag memory as stale."""
    service = MemoryService()

    mem = await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="architecture",
        title="Auth Controller Logic",
        content="Auth tokens are generated in src/auth.py using HS256.",
        source_reference="src/auth.py",
        user=test_user,
        db=db_session,
        verification_status="observed_fact",
    )
    assert mem.is_stale is False

    # Invalidate by file modification
    invalidated_count = await service.invalidate_by_files(
        repository_id=test_repository.id,
        modified_files=["src/auth.py"],
        db=db_session,
    )
    assert invalidated_count == 1

    # Fetch updated memory
    updated_mem = await service.get_memory(test_repository.id, mem.id, test_user, db_session)
    assert updated_mem.is_stale is True
    assert "src/auth.py" in updated_mem.stale_reason

    # Default semantic search must exclude stale memories
    results = await service.search_memories(
        repository_id=test_repository.id,
        query="Auth tokens HS256",
        user=test_user,
        db=db_session,
        include_stale=False,
    )
    assert not any(r["id"] == str(mem.id) for r in results)


@pytest.mark.asyncio
async def test_memory_feedback_and_auto_stale(db_session, test_user, test_repository):
    """Submitting 3 unhelpful feedback entries must automatically mark the memory stale."""
    service = MemoryService()

    mem = await service.create_or_update_memory(
        repository_id=test_repository.id,
        category="common_errors",
        title="Obsolete bug fix workaround",
        content="Workaround for sqlalchemy 1.4 deprecated method.",
        user=test_user,
        db=db_session,
        verification_status="ai_hypothesis",
    )

    # Add 2 unhelpful feedbacks
    await service.record_feedback(test_repository.id, mem.id, is_helpful=False, user=test_user, db=db_session)
    await service.record_feedback(test_repository.id, mem.id, is_helpful=False, user=test_user, db=db_session)
    mem_check = await service.get_memory(test_repository.id, mem.id, test_user, db_session)
    assert mem_check.is_stale is False
    assert mem_check.unhelpful_count == 2

    # Add 3rd unhelpful feedback -> should trigger auto-stale
    await service.record_feedback(test_repository.id, mem.id, is_helpful=False, user=test_user, db=db_session)
    mem_check2 = await service.get_memory(test_repository.id, mem.id, test_user, db_session)
    assert mem_check2.is_stale is True
    assert mem_check2.unhelpful_count == 3
