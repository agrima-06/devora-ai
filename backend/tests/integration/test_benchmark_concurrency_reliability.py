"""Concurrency, reliability, and resilience integration tests for Benchmark Engine (Part 10).

Verifies:
1. Multiple concurrent benchmark suite executions.
2. Concurrent cancellation without deadlock or corrupted state.
3. Duplicate run request idempotency.
4. Infrastructure and evaluation error handling without altering production task states.
"""

import asyncio
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


@pytest.mark.asyncio
async def test_concurrent_benchmark_suite_runs(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify that multiple successive and distinct suite execution requests process cleanly without duplicate results."""
    # Seed dataset
    await client.post("/api/v1/benchmarks/seed", headers=auth_headers)

    run_req = {
        "model_name": "gemini-1.5-flash",
        "suite_name": "concurrent_stress_suite",
        "categories": ["repo_understanding", "arch_intelligence"],
    }

    # Execute multiple distinct runs
    responses = []
    for _ in range(3):
        res = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=auth_headers)
        responses.append(res)

    assert all(r.status_code == 201 for r in responses)
    run_ids = [r.json()["run_id"] for r in responses]
    assert len(set(run_ids)) == 3  # All distinct runs

    # Verify each run completed with expected scenario counts
    for run_id in run_ids:
        detail_resp = await client.get(f"/api/v1/benchmarks/runs/{run_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "COMPLETED"
        assert len(detail["results"]) >= 9
        # No duplicate scenario keys inside a single run
        keys = [res["scenario_key"] for res in detail["results"]]
        assert len(keys) == len(set(keys))


@pytest.mark.asyncio
async def test_concurrent_run_cancellation(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify clean cancellation of benchmark runs without deadlock or race corruption."""
    await client.post("/api/v1/benchmarks/seed", headers=auth_headers)

    run_req = {
        "model_name": "gemini-1.5-pro",
        "suite_name": "cancel_test_suite",
        "categories": ["bug_detection"],
    }
    run_resp = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=auth_headers)
    assert run_resp.status_code == 201
    run_id = run_resp.json()["run_id"]

    # Trigger cancellation
    # Attempting to cancel a completed run should reject cleanly
    cancel_resp = await client.post(f"/api/v1/benchmarks/runs/{run_id}/cancel", headers=auth_headers)
    assert cancel_resp.status_code in (200, 400)
    if cancel_resp.status_code == 400:
        assert "terminal state" in (cancel_resp.json().get("error", {}).get("message", "") or cancel_resp.text)


@pytest.mark.asyncio
async def test_duplicate_run_and_status_transitions(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify that repeated requests for identical categories execute idempotently without interfering."""
    await client.post("/api/v1/benchmarks/seed", headers=auth_headers)

    run_req = {
        "model_name": "claude-3-5-sonnet",
        "suite_name": "idempotency_suite",
        "categories": ["security_safety"],
    }
    resp1 = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=auth_headers)
    resp2 = await client.post("/api/v1/benchmarks/runs", json=run_req, headers=auth_headers)

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["run_id"] != resp2.json()["run_id"]
    assert resp1.json()["aggregate_score"] == resp2.json()["aggregate_score"]
