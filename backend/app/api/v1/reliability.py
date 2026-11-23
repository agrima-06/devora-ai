"""API endpoints for Phase 9 Stage 9.6: Reliability Observability Console."""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.reliability import (
    ReliabilityEventsResponse,
    ReliabilityOverviewResponse,
    ReliabilityTrendsResponse,
)
from app.services.reliability_service import ReliabilityService

router = APIRouter(prefix="/reliability", tags=["Reliability Observability"])


@router.get(
    "/overview",
    response_model=ReliabilityOverviewResponse,
    summary="Get single-pane system reliability and resilience overview",
)
async def get_reliability_overview(
    repository_id: Optional[uuid.UUID] = Query(None, description="Optional repository filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve verified health states and aggregate metrics across workflows, sandbox, testing, gateway, and recovery."""
    service = ReliabilityService()
    return await service.get_overview(
        db=db,
        user_id=current_user.id,
        repository_id=repository_id,
    )


@router.get(
    "/events",
    response_model=ReliabilityEventsResponse,
    summary="List unified reliability audit events with subsystem and severity filtering",
)
async def list_reliability_events(
    subsystem: Optional[str] = Query(None, description="Filter by subsystem: Workflow, Sandbox, ModelGateway, Recovery, GitHub"),
    severity: Optional[str] = Query(None, description="Filter by severity: INFO, WARNING, ERROR, CRITICAL"),
    repository_id: Optional[uuid.UUID] = Query(None, description="Filter by repository ID"),
    task_id: Optional[uuid.UUID] = Query(None, description="Filter by task ID"),
    start_date: Optional[datetime] = Query(None, description="Start timestamp"),
    end_date: Optional[datetime] = Query(None, description="End timestamp"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated, credential-scrubbed reliability events across workflows."""
    service = ReliabilityService()
    return await service.get_events(
        db=db,
        user_id=current_user.id,
        subsystem=subsystem,
        severity=severity,
        repository_id=repository_id,
        task_id=task_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/trends",
    response_model=ReliabilityTrendsResponse,
    summary="Get aggregated reliability time-series trends",
)
async def get_reliability_trends(
    timeframe: str = Query("7d", description="Timeframe: 24h, 7d, 14d, 30d"),
    repository_id: Optional[uuid.UUID] = Query(None, description="Optional repository filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve daily time-bucketed trends for completions, failures, OOMs, timeouts, and recoveries."""
    service = ReliabilityService()
    return await service.get_trends(
        db=db,
        user_id=current_user.id,
        timeframe=timeframe,
        repository_id=repository_id,
    )
