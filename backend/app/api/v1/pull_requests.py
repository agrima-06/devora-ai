"""API endpoints for autonomous GitHub Pull Requests management and status synchronization."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.github_pull_request import GitHubPullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.schemas.pull_request import (
    CreatePullRequestRequest,
    PullRequestResponse,
    SyncPullRequestResponse,
)
from app.services.pull_request_service import PullRequestService

router = APIRouter(prefix="/pull-requests", tags=["Pull Requests"])
pr_service = PullRequestService()


@router.get(
    "",
    response_model=List[PullRequestResponse],
    summary="List autonomous pull requests",
)
async def list_pull_requests(
    repository_id: Optional[uuid.UUID] = Query(None, description="Filter by repository ID"),
    task_id: Optional[uuid.UUID] = Query(None, description="Filter by task ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pull requests created by Devora AI for the user's repositories."""
    stmt = (
        select(GitHubPullRequest)
        .join(Repository, GitHubPullRequest.repository_id == Repository.id)
        .where(Repository.user_id == current_user.id)
        .order_by(desc(GitHubPullRequest.created_at))
        .offset(skip)
        .limit(limit)
    )

    if repository_id:
        stmt = stmt.where(GitHubPullRequest.repository_id == repository_id)
    if task_id:
        stmt = stmt.where(GitHubPullRequest.task_id == task_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/{id}",
    response_model=PullRequestResponse,
    summary="Get pull request details",
)
async def get_pull_request(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific Pull Request."""
    stmt = (
        select(GitHubPullRequest)
        .join(Repository, GitHubPullRequest.repository_id == Repository.id)
        .where(GitHubPullRequest.id == id, Repository.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    pr = result.scalar_one_or_none()
    if not pr:
        raise NotFoundException("GitHub Pull Request", id)
    return pr


@router.post(
    "/tasks/{task_id}",
    response_model=PullRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Pull Request for task",
)
async def create_pull_request_for_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publish a verified, approved task solution as an autonomous GitHub Pull Request."""
    # Verify task ownership
    task_stmt = (
        select(Task)
        .join(Repository, Task.repository_id == Repository.id)
        .where(Task.id == task_id, Repository.user_id == current_user.id)
    )
    task_res = await db.execute(task_stmt)
    task = task_res.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    gh_pr = await pr_service.create_pull_request_for_task(db=db, task_id=task.id)
    return gh_pr


@router.post(
    "/{id}/sync",
    response_model=SyncPullRequestResponse,
    summary="Synchronize Pull Request status with GitHub",
)
async def sync_pull_request(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch remote PR state (merge status, commit SHA, state) from GitHub."""
    stmt = (
        select(GitHubPullRequest)
        .join(Repository, GitHubPullRequest.repository_id == Repository.id)
        .where(GitHubPullRequest.id == id, Repository.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    pr = result.scalar_one_or_none()
    if not pr:
        raise NotFoundException("GitHub Pull Request", id)

    updated_pr = await pr_service.sync_pull_request_status(db=db, pr_id=pr.id)
    return SyncPullRequestResponse(
        success=True,
        message=f"Pull Request #{updated_pr.pr_number} synchronized with state '{updated_pr.state}'.",
        pull_request=updated_pr,
    )
