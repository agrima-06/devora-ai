"""API endpoints for Phase 7 Adaptive Engineering Intelligence, Failure Learning, and Benchmarks."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.benchmark import BenchmarkDefinition, BenchmarkRun
from app.models.engineering_experience import EngineeringExperience
from app.models.task import Task
from app.models.task_failure_record import TaskFailureRecord
from app.models.user import User
from app.schemas.adaptive import (
    AdaptiveFeedbackCreate,
    AdaptiveFeedbackResponse,
    AgentPerformanceResponse,
    BenchmarkDefinitionResponse,
    BenchmarkExecutionRequest,
    BenchmarkRunResponse,
    BenchmarkSummaryResponse,
    EngineeringExperienceResponse,
    ExperienceSearchQuery,
    ExperienceSearchResult,
    TaskFailureRecordResponse,
)
from app.services.adaptive_service import AdaptiveIntelligenceService
from app.services.benchmark_service import BenchmarkService

router = APIRouter(prefix="/adaptive", tags=["Adaptive Intelligence"])


# ---------------------------------------------------------------------------
# Experience Retrieval & Search Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/experiences",
    response_model=List[EngineeringExperienceResponse],
    summary="List historical engineering experiences",
)
async def list_experiences(
    task_category: Optional[str] = Query(None, description="Filter by task category"),
    bug_category: Optional[str] = Query(None, description="Filter by bug category"),
    status_type: Optional[str] = Query(None, description="Filter by reliability status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve verified and categorized historical engineering experiences."""
    stmt = select(EngineeringExperience)
    if task_category:
        stmt = stmt.where(EngineeringExperience.task_category == task_category)
    if bug_category:
        stmt = stmt.where(EngineeringExperience.bug_category == bug_category)
    if status_type:
        stmt = stmt.where(EngineeringExperience.status_type == status_type)

    stmt = stmt.order_by(desc(EngineeringExperience.created_at)).offset(skip).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.post(
    "/experiences/search",
    response_model=List[ExperienceSearchResult],
    summary="Semantic search across engineering experiences",
)
async def search_experiences(
    query_body: ExperienceSearchQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Perform cosine similarity retrieval across historical experiences with status weighting."""
    service = AdaptiveIntelligenceService()
    results = await service.retrieve_relevant_experiences(
        query=query_body.query,
        task_category=query_body.task_category,
        technology_stack=query_body.technology_stack,
        status_type=query_body.status_type,
        limit=query_body.limit,
        threshold=query_body.threshold,
        db=db,
    )
    return results


@router.get(
    "/experiences/{id}",
    response_model=EngineeringExperienceResponse,
    summary="Get single engineering experience details",
)
async def get_experience(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full technical details and diff patch for an engineering experience."""
    stmt = select(EngineeringExperience).where(EngineeringExperience.id == id)
    exp = (await db.execute(stmt)).scalar_one_or_none()
    if not exp:
        raise NotFoundException("EngineeringExperience", id)
    return exp


# ---------------------------------------------------------------------------
# Failure Learning Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/failures",
    response_model=List[TaskFailureRecordResponse],
    summary="List failure analysis records",
)
async def list_failures(
    task_id: Optional[uuid.UUID] = Query(None, description="Filter by task ID"),
    stage: Optional[str] = Query(None, description="Filter by failure stage"),
    failure_type: Optional[str] = Query(None, description="Filter by failure type"),
    limit: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve structured records of previous execution failures and lessons learned."""
    stmt = select(TaskFailureRecord)
    if task_id:
        stmt = stmt.where(TaskFailureRecord.task_id == task_id)
    if stage:
        stmt = stmt.where(TaskFailureRecord.stage == stage)
    if failure_type:
        stmt = stmt.where(TaskFailureRecord.failure_type == failure_type)

    stmt = stmt.order_by(desc(TaskFailureRecord.created_at)).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


# ---------------------------------------------------------------------------
# Agent Performance Telemetry Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/agent-performance",
    response_model=AgentPerformanceResponse,
    summary="Get aggregated performance metrics across all 9 agents",
)
async def get_agent_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve measurable performance telemetry for all specialized agents."""
    service = AdaptiveIntelligenceService()
    return await service.get_agent_performance_metrics(db=db)


# ---------------------------------------------------------------------------
# Engineering Benchmark Framework Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/benchmarks",
    response_model=List[BenchmarkDefinitionResponse],
    summary="List benchmark suite definitions",
)
async def list_benchmarks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all 7 canonical engineering benchmark specifications."""
    service = BenchmarkService()
    return await service.list_benchmarks(db=db)


@router.post(
    "/benchmarks/run",
    response_model=BenchmarkSummaryResponse,
    summary="Execute benchmark evaluation suite",
)
async def run_benchmarks(
    request: BenchmarkExecutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run benchmark evaluation suite and record verifiable execution metrics."""
    service = BenchmarkService()
    if request.benchmark_id:
        single_run = await service.run_benchmark(
            benchmark_id=request.benchmark_id,
            system_version=request.system_version,
            model_version=request.model_version,
            db=db,
        )
        runs = [single_run]
    else:
        runs = await service.run_all(
            system_version=request.system_version,
            model_version=request.model_version,
            db=db,
        )

    completed_count = sum(1 for r in runs if r.task_completed)
    passed_count = sum(1 for r in runs if r.tests_passed)
    total = len(runs)
    avg_retries = sum(r.retries_count for r in runs) / total if total > 0 else 0.0
    avg_duration = sum(r.execution_time_ms for r in runs) / total if total > 0 else 0.0
    total_cost = sum(r.estimated_cost_usd for r in runs)

    return BenchmarkSummaryResponse(
        system_version=request.system_version,
        total_benchmarks=total,
        tasks_completed_count=completed_count,
        completion_rate=round(completed_count / total, 4) if total > 0 else 0.0,
        tests_passed_count=passed_count,
        test_pass_rate=round(passed_count / total, 4) if total > 0 else 0.0,
        average_retries=round(avg_retries, 2),
        average_execution_time_ms=round(avg_duration, 1),
        total_estimated_cost_usd=round(total_cost, 4),
        runs=runs,
    )


@router.get(
    "/benchmarks/history",
    response_model=List[BenchmarkRunResponse],
    summary="Get historical benchmark runs",
)
async def get_benchmark_history(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical benchmark runs for tracking improvements over time."""
    service = BenchmarkService()
    return await service.get_history(db=db, limit=limit)


# ---------------------------------------------------------------------------
# Human Feedback Submission
# ---------------------------------------------------------------------------

@router.post(
    "/feedback",
    response_model=AdaptiveFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit developer feedback on autonomous task",
)
async def submit_feedback(
    feedback_data: AdaptiveFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record multi-dimensional human feedback to update engineering experience quality scores."""
    service = AdaptiveIntelligenceService()
    fb = await service.submit_feedback(
        task_id=feedback_data.task_id,
        user=current_user,
        rating=feedback_data.rating,
        plan_accepted=feedback_data.plan_accepted,
        code_accepted=feedback_data.code_accepted,
        solution_helpful=feedback_data.solution_helpful,
        comments=feedback_data.comments,
        db=db,
    )
    delta = 10 if fb.solution_accepted else -10
    return AdaptiveFeedbackResponse(
        id=fb.id,
        task_id=fb.task_id,
        rating=fb.rating,
        solution_accepted=fb.solution_accepted,
        quality_score_delta=delta,
        message=f"Feedback recorded. Experience quality score adjusted by {delta:+d}.",
    )
