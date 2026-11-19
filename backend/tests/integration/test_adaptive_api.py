"""Integration tests for Phase 7 Adaptive Intelligence REST APIs."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engineering_experience import EngineeringExperience
from app.models.task import Task
from app.models.task_failure_record import TaskFailureRecord
from app.models.user import User
from app.services.adaptive_service import AdaptiveIntelligenceService


@pytest.mark.asyncio
async def test_adaptive_experiences_crud_and_search(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test experience listing, single item retrieval, and semantic vector search."""
    service = AdaptiveIntelligenceService()

    # Seed an experience directly into DB
    exp = EngineeringExperience(
        repository_id=None,
        task_category="bug_fix",
        bug_category="runtime_logic_error",
        problem_summary="Fix ZeroDivisionError in invoice discount calculator",
        root_cause="Denominator total_discounts was 0 without guard clause",
        resolution_strategy="Check if total_discounts == 0 return 0.0",
        diff_patch="--- a/billing.py\n+++ b/billing.py\n@@ -10,1 +10,3 @@\n+ if total_discounts == 0:\n+     return 0.0",
        embedding=await service.generate_text_embedding("Fix ZeroDivisionError in invoice discount calculator"),
        status_type="verified_successful",
        technology_stack=["python", "pytest"],
        files_involved=["billing.py"],
        attempts_count=1,
        failed_approaches=[],
        successful_approach="Added zero denominator guard clause",
        test_results={"tests_passed": True, "exit_code": 0},
        review_findings={"status": "approved"},
        security_findings={"vulnerabilities": 0},
        is_anonymized=False,
        is_verified=True,
        quality_score=15,
    )
    db_session.add(exp)
    await db_session.commit()
    await db_session.refresh(exp)

    # 1. List experiences
    list_res = await client.get("/api/v1/adaptive/experiences", headers=auth_headers)
    assert list_res.status_code == 200
    experiences = list_res.json()
    assert len(experiences) >= 1
    found = any(e["id"] == str(exp.id) for e in experiences)
    assert found is True

    # 2. Get single experience
    single_res = await client.get(f"/api/v1/adaptive/experiences/{exp.id}", headers=auth_headers)
    assert single_res.status_code == 200
    single_data = single_res.json()
    assert single_data["id"] == str(exp.id)
    assert single_data["status_type"] == "verified_successful"
    assert "billing.py" in single_data["files_involved"]

    # 3. Semantic search
    search_payload = {
        "query": "Fix ZeroDivisionError in invoice discount calculator",
        "task_category": "bug_fix",
        "limit": 5,
        "threshold": 0.0,
    }
    search_res = await client.post(
        "/api/v1/adaptive/experiences/search",
        json=search_payload,
        headers=auth_headers,
    )
    assert search_res.status_code == 200
    search_results = search_res.json()
    assert len(search_results) >= 1
    top = search_results[0]
    assert top["status_type"] == "verified_successful"
    assert top["weighted_score"] >= top["similarity"]  # 1.3x multiplier
    assert top["is_positive_guidance"] is True


@pytest.mark.asyncio
async def test_adaptive_failure_records_api(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test listing failure analysis records."""
    task_id = uuid.uuid4()
    fail_rec = TaskFailureRecord(
        task_id=task_id,
        stage="TESTING",
        failure_type="IMPLEMENTATION_DEFECT",
        attempt_number=1,
        failed_strategy="Direct division without guard",
        error_log="ZeroDivisionError: division by zero",
        review_notes="Test runner exited with code 1",
        lessons_learned="Always verify non-zero denominator in billing algorithms.",
    )
    db_session.add(fail_rec)
    await db_session.commit()

    res = await client.get("/api/v1/adaptive/failures", headers=auth_headers)
    assert res.status_code == 200
    failures = res.json()
    assert len(failures) >= 1
    assert any(f["stage"] == "TESTING" and "ZeroDivisionError" in f["error_log"] for f in failures)


@pytest.mark.asyncio
async def test_agent_performance_api(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test agent performance metrics endpoint returns all 9 agents."""
    res = await client.get("/api/v1/adaptive/agent-performance", headers=auth_headers)
    assert res.status_code == 200
    perf = res.json()
    assert "agents" in perf
    assert len(perf["agents"]) in (9, 10)
    assert "overall_first_pass_rate" in perf
    assert "average_task_duration_seconds" in perf


@pytest.mark.asyncio
async def test_benchmarks_api_workflow(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test listing, running, and retrieving benchmark history."""
    # 1. List benchmarks definitions
    list_res = await client.get("/api/v1/adaptive/benchmarks", headers=auth_headers)
    assert list_res.status_code == 200
    benchmarks = list_res.json()
    assert len(benchmarks) == 7
    assert any(b["id"] == "BM-BUG-01" for b in benchmarks)

    # 2. Run single benchmark
    run_payload = {
        "benchmark_id": "BM-BUG-01",
        "system_version": "v1.0.0-phase7",
        "model_version": "gemini-1.5-pro",
    }
    run_res = await client.post("/api/v1/adaptive/benchmarks/run", json=run_payload, headers=auth_headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["total_benchmarks"] == 1
    assert run_data["tasks_completed_count"] == 1
    assert run_data["test_pass_rate"] == 1.0
    assert len(run_data["runs"]) == 1
    assert run_data["runs"][0]["benchmark_id"] == "BM-BUG-01"

    # 3. Query history
    hist_res = await client.get("/api/v1/adaptive/benchmarks/history", headers=auth_headers)
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 1
    assert history[0]["benchmark_id"] == "BM-BUG-01"


@pytest.mark.asyncio
async def test_feedback_api(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test submitting developer feedback on autonomous task."""
    task_id = uuid.uuid4()
    feedback_payload = {
        "task_id": str(task_id),
        "rating": "ACCEPTED",
        "plan_accepted": True,
        "code_accepted": True,
        "solution_helpful": True,
        "comments": "Flawless code repair and tests verification.",
    }
    res = await client.post(
        "/api/v1/adaptive/feedback",
        json=feedback_payload,
        headers=auth_headers,
    )
    assert res.status_code == 201
    fb_data = res.json()
    assert fb_data["task_id"] == str(task_id)
    assert fb_data["rating"] == "ACCEPTED"
    assert fb_data["solution_accepted"] is True
    assert fb_data["quality_score_delta"] == 10
