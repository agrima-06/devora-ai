"""API Router for Phase 10 Stage 10.6: Architecture-Aware Refactoring & Safe Remediation Engine."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.refactoring import (
    BeforeAfterComparisonResponse,
    RefactoringApproveRequest,
    RefactoringExecuteRequest,
    RefactoringExecutionResponse,
    RefactoringPlanCreateRequest,
    RefactoringPlanResponse,
    RefactoringPlansListResponse,
    RefactoringRecommendationsResponse,
)
from app.services.refactoring_service import ArchitectureAwareRefactoringService

router = APIRouter(prefix="/repositories/{repository_id}/refactoring", tags=["Refactoring Engine"])


@router.post(
    "/recommendations",
    response_model=RefactoringRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate evidence-backed refactoring recommendations",
)
async def generate_refactoring_recommendations(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Optional category filter (layering, dependency, duplication, complexity, convention, testability)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringRecommendationsResponse:
    """Evaluate repository drift and technical debt findings to generate explainable refactoring proposals."""
    service = ArchitectureAwareRefactoringService()
    return await service.generate_recommendations(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
    )


@router.get(
    "/recommendations",
    response_model=RefactoringRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="List refactoring recommendations with optional category filter",
)
async def list_refactoring_recommendations(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringRecommendationsResponse:
    """Retrieve verified refactoring recommendations for a repository."""
    service = ArchitectureAwareRefactoringService()
    return await service.generate_recommendations(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
    )


@router.post(
    "/plans",
    response_model=RefactoringPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create structured, ordered refactoring plan from recommendations",
)
async def create_refactoring_plan(
    repository_id: uuid.UUID,
    request: RefactoringPlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringPlanResponse:
    """Synthesize a dependency-aware, topologically ordered refactoring plan with risk scoring."""
    service = ArchitectureAwareRefactoringService()
    return await service.create_plan(
        repository_id=repository_id,
        user=current_user,
        db=db,
        recommendation_ids=request.recommendation_ids,
        title=request.title,
        description=request.description,
    )


@router.get(
    "/plans",
    response_model=RefactoringPlansListResponse,
    status_code=status.HTTP_200_OK,
    summary="List refactoring plans for a repository",
)
async def list_refactoring_plans(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by category"),
    approval_status: Optional[str] = Query(None, description="Filter by approval status (PENDING, APPROVED, REJECTED, INVALIDATED)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringPlansListResponse:
    """Retrieve historical and pending refactoring plans."""
    service = ArchitectureAwareRefactoringService()
    return await service.list_plans(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
        approval_status=approval_status,
    )


@router.get(
    "/plans/{plan_id}",
    response_model=RefactoringPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get refactoring plan details by ID",
)
async def get_refactoring_plan(
    repository_id: uuid.UUID,
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringPlanResponse:
    """Fetch complete refactoring plan details including ordered steps, risk factors, and approval status."""
    service = ArchitectureAwareRefactoringService()
    return await service.get_plan(
        repository_id=repository_id,
        plan_id=plan_id,
        user=current_user,
        db=db,
    )


@router.post(
    "/plans/{plan_id}/approve",
    response_model=RefactoringPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve refactoring plan with cryptographic diff hash binding",
)
async def approve_refactoring_plan(
    repository_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: RefactoringApproveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringPlanResponse:
    """Record human approval for a plan, cryptographically binding the decision to the specific diff hash."""
    service = ArchitectureAwareRefactoringService()
    return await service.approve_plan(
        repository_id=repository_id,
        plan_id=plan_id,
        user=current_user,
        db=db,
        diff_hash=request.diff_hash,
        notes=request.notes,
    )


@router.post(
    "/plans/{plan_id}/reject",
    response_model=RefactoringPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject refactoring plan",
)
async def reject_refactoring_plan(
    repository_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringPlanResponse:
    """Record human rejection of a refactoring plan."""
    service = ArchitectureAwareRefactoringService()
    reason = payload.get("reason") if payload else None
    return await service.reject_plan(
        repository_id=repository_id,
        plan_id=plan_id,
        user=current_user,
        db=db,
        reason=reason,
    )


@router.post(
    "/plans/{plan_id}/execute",
    response_model=RefactoringExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute approved refactoring plan with behavioral preservation checks",
)
async def execute_refactoring_plan(
    repository_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: RefactoringExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringExecutionResponse:
    """Execute plan in an isolated workspace, validating behavioral preservation and reverting on regression."""
    service = ArchitectureAwareRefactoringService()
    return await service.execute_plan(
        repository_id=repository_id,
        plan_id=plan_id,
        user=current_user,
        db=db,
        diff_hash=request.diff_hash,
        dry_run=request.dry_run,
        simulate_regression=request.simulate_regression,
    )


@router.get(
    "/executions/{execution_id}",
    response_model=RefactoringExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get refactoring execution outcome and verification metrics",
)
async def get_refactoring_execution(
    repository_id: uuid.UUID,
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefactoringExecutionResponse:
    """Retrieve execution status, test execution results, and before/after metrics."""
    service = ArchitectureAwareRefactoringService()
    return await service.get_execution(
        repository_id=repository_id,
        execution_id=execution_id,
        user=current_user,
        db=db,
    )


@router.get(
    "/executions/{execution_id}/comparison",
    response_model=BeforeAfterComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Get before-and-after comparison of debt scores and drift",
)
async def get_before_after_comparison(
    repository_id: uuid.UUID,
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BeforeAfterComparisonResponse:
    """Retrieve comparative assessment between baseline repository state and post-refactoring outcome."""
    service = ArchitectureAwareRefactoringService()
    return await service.get_comparison(
        repository_id=repository_id,
        execution_id=execution_id,
        user=current_user,
        db=db,
    )
