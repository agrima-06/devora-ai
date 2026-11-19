"""Unit tests for Phase 7 Engineering Benchmark Framework."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.benchmark_service import BenchmarkService, CANONICAL_BENCHMARKS


def test_canonical_benchmark_suite_definitions():
    """Verify that all 7 canonical engineering benchmark tasks are defined."""
    assert len(CANONICAL_BENCHMARKS) == 7

    benchmark_ids = [bm["id"] for bm in CANONICAL_BENCHMARKS]
    expected_ids = [
        "BM-BUG-01",
        "BM-BUG-02",
        "BM-EXPLORE-01",
        "BM-REFACTOR-01",
        "BM-DEP-01",
        "BM-TEST-01",
        "BM-QUAL-01",
    ]
    assert benchmark_ids == expected_ids

    # Verify each benchmark has required structured fields
    for bm in CANONICAL_BENCHMARKS:
        assert "name" in bm
        assert "category" in bm
        assert "description" in bm
        assert "initial_repo_snapshot" in bm
        assert "expected_outcomes" in bm
        assert "evaluation_criteria" in bm
        assert 0.0 < bm["baseline_pass_rate"] <= 1.0


@pytest.mark.asyncio
async def test_benchmark_seeding_and_listing(db_session: AsyncSession):
    """Test seeding canonical benchmarks into database and listing them."""
    service = BenchmarkService()
    benchmarks = await service.list_benchmarks(db=db_session)

    assert len(benchmarks) == 7
    categories = {b.category for b in benchmarks}
    expected_categories = {
        "bug_investigation",
        "bug_fixing",
        "repository_exploration",
        "refactoring",
        "dependency_problems",
        "test_failure_resolution",
        "code_quality",
    }
    assert categories == expected_categories


@pytest.mark.asyncio
async def test_run_single_benchmark(db_session: AsyncSession):
    """Test executing a single benchmark evaluation run."""
    service = BenchmarkService()
    run = await service.run_benchmark(
        benchmark_id="BM-BUG-01",
        system_version="v1.0.0-phase7",
        model_version="gemini-1.5-pro",
        db=db_session,
    )

    assert run.id is not None
    assert run.benchmark_id == "BM-BUG-01"
    assert run.system_version == "v1.0.0-phase7"
    assert run.model_version == "gemini-1.5-pro"
    assert run.task_completed is True
    assert run.tests_passed is True
    assert run.retries_count == 0
    assert run.execution_time_ms > 0
    assert run.tokens_used > 0
    assert run.estimated_cost_usd > 0.0
    assert run.review_passed is True


@pytest.mark.asyncio
async def test_run_all_and_history(db_session: AsyncSession):
    """Test running entire suite and querying historical runs."""
    service = BenchmarkService()
    runs = await service.run_all(
        system_version="v1.0.0-phase7",
        model_version="gemini-1.5-pro",
        db=db_session,
    )

    assert len(runs) == 7
    assert all(r.task_completed for r in runs)
    assert all(r.tests_passed for r in runs)

    # Check history
    history = await service.get_history(db=db_session, limit=10)
    assert len(history) >= 7
