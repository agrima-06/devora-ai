"""API endpoints for GitHub App integration, installations, and repository permissions."""
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.github_installation import GitHubInstallation
from app.models.user import User
from app.schemas.github import (
    GitHubInstallationConnectRequest,
    GitHubInstallationResponse,
    GitHubRepositoryItem,
    GitHubStatusResponse,
)
from app.services.github_app_service import GitHubAppService

router = APIRouter(prefix="/github", tags=["GitHub Integration"])
gh_app = GitHubAppService()


@router.get(
    "/status",
    response_model=GitHubStatusResponse,
    summary="Get GitHub App integration status",
)
async def get_github_status(
    current_user: User = Depends(get_current_user),
):
    """Return whether the GitHub App is configured, active, or running in mock mode."""
    app_id = gh_app.app_id
    has_key = bool(gh_app.private_key)
    is_mock = gh_app.is_mock or not (app_id and has_key)

    return GitHubStatusResponse(
        app_configured=bool(app_id and has_key) or is_mock,
        app_id=app_id or "devora-github-app",
        has_private_key=has_key or is_mock,
        is_mock=is_mock,
    )


@router.get(
    "/installations",
    response_model=List[GitHubInstallationResponse],
    summary="List connected GitHub installations for user",
)
async def list_installations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all GitHub App installations authorized for the authenticated user."""
    stmt = (
        select(GitHubInstallation)
        .where(GitHubInstallation.user_id == current_user.id, GitHubInstallation.is_active == True)
        .order_by(GitHubInstallation.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/installations/connect",
    response_model=GitHubInstallationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect GitHub App installation",
)
async def connect_installation(
    payload: GitHubInstallationConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register or update an authorized GitHub App installation for the user."""
    stmt = select(GitHubInstallation).where(
        GitHubInstallation.installation_id == payload.installation_id,
        GitHubInstallation.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    installation = result.scalar_one_or_none()

    if installation:
        installation.account_login = payload.account_login or installation.account_login
        installation.account_type = payload.account_type
        installation.repository_selection = payload.repository_selection
        installation.permissions = payload.permissions
        installation.is_active = True
    else:
        account_name = payload.account_login or f"{current_user.username}-org"
        installation = GitHubInstallation(
            user_id=current_user.id,
            installation_id=payload.installation_id,
            account_login=account_name,
            account_type=payload.account_type,
            repository_selection=payload.repository_selection,
            permissions=payload.permissions or {"pull_requests": "write", "contents": "write"},
            is_active=True,
        )
        db.add(installation)

    await db.commit()
    await db.refresh(installation)
    return installation


@router.get(
    "/installations/{installation_id}/repositories",
    response_model=List[GitHubRepositoryItem],
    summary="List repositories for GitHub installation",
)
async def list_installation_repositories(
    installation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query GitHub for repositories accessible under the specified installation."""
    # Verify installation belongs to user or mock mode is active
    stmt = select(GitHubInstallation).where(
        GitHubInstallation.installation_id == installation_id,
        GitHubInstallation.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()
    if not inst and not gh_app.is_mock:
        raise NotFoundException("GitHub Installation", installation_id)

    repos = await gh_app.list_installation_repositories(installation_id)
    return [GitHubRepositoryItem(**r) for r in repos]


@router.delete(
    "/installations/{installation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect GitHub installation",
)
async def disconnect_installation(
    installation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect and deactivate a GitHub App installation."""
    stmt = select(GitHubInstallation).where(
        GitHubInstallation.installation_id == installation_id,
        GitHubInstallation.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()
    if not inst:
        raise NotFoundException("GitHub Installation", installation_id)

    inst.is_active = False
    await db.commit()
    return None
