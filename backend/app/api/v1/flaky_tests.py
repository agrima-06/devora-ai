"""API endpoints for Flaky Test Detection, stability scoring, and historical test tracking."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.flaky_test_record import FlakyTestRecord
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.schemas.flaky_test import (
    FlakyTestRecordResponse,
    RepositoryStabilitySummaryResponse,
)
from app.services.flaky_detector import FlakyTestDetector

router = APIRouter(tags=["Flaky Tests & Stability"])
detector = FlakyTestDetector()


@router.get(
    "/repositories/{repository_id}/flaky-tests",
    response_model=List[FlakyTestRecordResponse],
    summary="List flaky test records for repository",
)
async def list_repository_flaky_tests(
    repository_id: uuid.UUID,
    classification: Optional[str] = Query(None, description="Filter by classification (e.g. FLAKY, CONSISTENT_FAILURE)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all flaky and unstable test records for a specific repository."""
    # Verify repository ownership
    repo_stmt = select(Repository).where(
        Repository.id == repository_id,
        Repository.user_id == current_user.id,
    )
    repo_res = await db.execute(repo_stmt)
    repo = repo_res.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repository_id)

    return await detector.get_repository_flaky_tests(
        repository_id=repository_id,
        db=db,
        classification=classification,
    )


@router.get(
    "/repositories/{repository_id}/test-stability",
    response_model=RepositoryStabilitySummaryResponse,
    summary="Get aggregated repository test stability summary",
)
async def get_repository_test_stability(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve aggregated test stability statistics for a repository."""
    repo_stmt = select(Repository).where(
        Repository.id == repository_id,
        Repository.user_id == current_user.id,
    )
    repo_res = await db.execute(repo_stmt)
    repo = repo_res.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repository_id)

    summary = await detector.get_repository_stability_summary(
        repository_id=repository_id,
        db=db,
    )
    return summary


@router.get(
    "/tasks/{task_id}/flaky-tests",
    response_model=List[FlakyTestRecordResponse],
    summary="List flaky tests detected in a task",
)
async def list_task_flaky_tests(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all flaky test records identified during execution of a task."""
    task_stmt = select(Task).where(
        Task.id == task_id,
        Task.created_by == current_user.id,
    )
    task_res = await db.execute(task_stmt)
    task = task_res.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    return await detector.get_task_flaky_tests(task_id=task_id, db=db)


@router.get(
    "/flaky-tests/{flaky_test_id}",
    response_model=FlakyTestRecordResponse,
    summary="Get individual flaky test record details",
)
async def get_flaky_test_detail(
    flaky_test_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed history and metrics for a specific flaky test record."""
    stmt = (
        select(FlakyTestRecord)
        .join(Repository, FlakyTestRecord.repository_id == Repository.id)
        .where(
            FlakyTestRecord.id == flaky_test_id,
            Repository.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise NotFoundException("FlakyTestRecord", flaky_test_id)

    return record
