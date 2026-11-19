"""Integration tests for Model Gateway Health API and resilience (Phase 9 Stage 9.5)."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.circuit_breaker import CircuitBreakerRegistry, CircuitState
from app.agents.gateway.exceptions import ProviderServerError
from app.models.model_gateway_health import ModelGatewayHealth
from app.models.user import User


@pytest.mark.asyncio
async def test_get_model_gateway_health(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test GET /api/v1/models/health returns gateway health and syncs to database."""
    res = await client.get("/api/v1/models/health", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "status" in data
    assert data["status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
    assert "circuit_breaker_enabled" in data
    assert "active_primary_model" in data
    assert "breakers" in data
    assert "metrics" in data
    assert isinstance(data["breakers"], list)

    # Verify rows persisted into model_gateway_health table
    stmt = select(ModelGatewayHealth)
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert len(records) >= 1
    first_record = records[0]
    assert first_record.circuit_state in ("CLOSED", "OPEN", "HALF_OPEN")


@pytest.mark.asyncio
async def test_reset_model_circuit_breaker(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test manual reset of a tripped circuit breaker via REST API."""
    registry = CircuitBreakerRegistry.get_instance()
    breaker = registry.get_breaker("mock", "test-reset-model")

    # Force breaker into OPEN state
    for _ in range(10):
        await breaker.record_failure(ProviderServerError("Repeated failure"))
    assert breaker.state == CircuitState.OPEN

    # Call reset endpoint
    res = await client.post(
        f"/api/v1/models/breakers/mock/test-reset-model/reset",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "CLOSED"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_reset_all_model_circuit_breakers(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test resetting all registered circuit breakers via POST /api/v1/models/reset-all."""
    registry = CircuitBreakerRegistry.get_instance()
    b1 = registry.get_breaker("mock", "model-alpha")
    b2 = registry.get_breaker("mock", "model-beta")

    for _ in range(10):
        await b1.record_failure(ProviderServerError("Fail 1"))
        await b2.record_failure(ProviderServerError("Fail 2"))

    assert b1.state == CircuitState.OPEN
    assert b2.state == CircuitState.OPEN

    res = await client.post("/api/v1/models/reset-all", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert b1.state == CircuitState.CLOSED
    assert b2.state == CircuitState.CLOSED
    for breaker in data["breakers"]:
        assert breaker["state"] == "CLOSED"
