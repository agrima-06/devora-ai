"""API endpoints for Model Gateway Health, Circuit Breakers, and Telemetry (Phase 9 Stage 9.5)."""
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.model_health import (
    ModelCircuitBreakerStatus,
    ModelGatewayHealthResponse,
)
from app.services.model_health_service import ModelHealthService

router = APIRouter(prefix="/models", tags=["Model Gateway"])


@router.get(
    "/health",
    response_model=ModelGatewayHealthResponse,
    summary="Get Model Gateway resilience and circuit breaker health",
)
async def get_model_gateway_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve live status, active providers, circuit breakers, and token accounting metrics."""
    service = ModelHealthService()
    # Sync latest in-memory metrics to PostgreSQL table
    await service.sync_health_to_db(db)
    return service.get_health_overview()


@router.post(
    "/breakers/{provider_name}/{model_name}/reset",
    response_model=ModelCircuitBreakerStatus,
    summary="Reset a specific model circuit breaker to CLOSED state",
)
async def reset_model_circuit_breaker(
    provider_name: str,
    model_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually reset an OPEN or HALF_OPEN circuit breaker for a given provider and model."""
    service = ModelHealthService()
    return await service.reset_breaker(provider_name, model_name, db=db)


@router.post(
    "/reset-all",
    response_model=ModelGatewayHealthResponse,
    summary="Reset all model circuit breakers to CLOSED state",
)
async def reset_all_model_circuit_breakers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually reset all registered circuit breakers to CLOSED state."""
    service = ModelHealthService()
    service.registry.reset_all()
    await service.sync_health_to_db(db)
    return service.get_health_overview()
