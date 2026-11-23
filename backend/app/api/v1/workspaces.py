"""API Router for Phase 10 Stage 10.3: Monorepo & Workspace Intelligence Engine."""

import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.models.user import User
from app.schemas.workspace import (
    PackageDependenciesResponse,
    PackageImpactResponse,
    PackageInfo,
    WorkspaceGraphResponse,
    WorkspaceIndexResponse,
    WorkspaceInfo,
)
from app.services.github_service import GitHubService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/repositories/{repository_id}", tags=["Monorepo & Workspace Intelligence"])


class WorkspaceIndexRequest(BaseModel):
    """Optional configuration for workspace indexing."""
    branch: Optional[str] = Field(None, description="Branch to checkout and inspect")
    local_path: Optional[str] = Field(None, description="Direct filesystem path to workspace (for local testing)")


@router.get(
    "/workspaces",
    response_model=WorkspaceGraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Get repository workspaces and cross-package dependency graph",
)
async def get_repository_workspaces(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceGraphResponse:
    """Return all detected monorepos, multi-project workspaces, packages, and cross-package edges."""
    service = WorkspaceService()
    await service.get_repository_for_user(repository_id, current_user.id, db)
    return await service.get_workspace_graph(repository_id=repository_id, db=db)


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceInfo,
    status_code=status.HTTP_200_OK,
    summary="Get workspace details by ID",
)
async def get_workspace_details(
    repository_id: uuid.UUID,
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceInfo:
    """Fetch details and package listing for a specific workspace node."""
    service = WorkspaceService()
    await service.get_repository_for_user(repository_id, current_user.id, db)
    graph = await service.get_workspace_graph(repository_id=repository_id, db=db)
    for ws in graph.workspaces:
        if ws.id == workspace_id or ws.workspace_type == workspace_id:
            return ws
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workspace '{workspace_id}' not found.")


@router.get(
    "/packages",
    response_model=List[PackageInfo],
    status_code=status.HTTP_200_OK,
    summary="List all packages discovered across repository workspaces",
)
async def list_repository_packages(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PackageInfo]:
    """Return a flat list of all packages discovered across all workspaces in the repository."""
    service = WorkspaceService()
    await service.get_repository_for_user(repository_id, current_user.id, db)
    graph = await service.get_workspace_graph(repository_id=repository_id, db=db)
    packages: List[PackageInfo] = []
    for ws in graph.workspaces:
        packages.extend(ws.packages)
    return packages


@router.get(
    "/packages/{package_id}/dependencies",
    response_model=PackageDependenciesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get package dependencies and dependent consumers",
)
async def get_package_dependencies(
    repository_id: uuid.UUID,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PackageDependenciesResponse:
    """Return upstream dependencies (internal & external) and downstream consumers for a package."""
    service = WorkspaceService()
    await service.get_repository_for_user(repository_id, current_user.id, db)
    return await service.get_package_dependencies(
        repository_id=repository_id,
        package_id=package_id,
        db=db,
    )


@router.get(
    "/packages/{package_id}/dependents",
    response_model=List[PackageInfo],
    status_code=status.HTTP_200_OK,
    summary="Get packages that depend on this package",
)
async def get_package_dependents(
    repository_id: uuid.UUID,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PackageInfo]:
    """Return the list of downstream consumer packages that depend on the specified package."""
    service = WorkspaceService()
    await service.get_repository_for_user(repository_id, current_user.id, db)
    deps_resp = await service.get_package_dependencies(
        repository_id=repository_id,
        package_id=package_id,
        db=db,
    )
    return deps_resp.dependents


@router.get(
    "/packages/{package_id}/impact",
    response_model=PackageImpactResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate blast radius and impact for package changes",
)
async def get_package_impact(
    repository_id: uuid.UUID,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PackageImpactResponse:
    """Calculate the downstream blast radius and affected packages if the target package is modified."""
    service = WorkspaceService()
    await service.get_repository_for_user(repository_id, current_user.id, db)
    return await service.get_package_impact(
        repository_id=repository_id,
        package_id=package_id,
        db=db,
    )


@router.post(
    "/workspaces/index",
    response_model=WorkspaceIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan and index repository workspaces and packages into graph",
)
async def index_repository_workspaces(
    repository_id: uuid.UUID,
    payload: Optional[WorkspaceIndexRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceIndexResponse:
    """Trigger multi-ecosystem workspace detection and persist package nodes and edges."""
    service = WorkspaceService()
    repo = await service.get_repository_for_user(repository_id, current_user.id, db)

    if payload and payload.local_path:
        workspace_path = Path(payload.local_path)
    else:
        gh_service = GitHubService()
        token = current_user.github_access_token or settings.GITHUB_TOKEN
        target_branch = (payload.branch if payload else None) or repo.default_branch or "main"
        try:
            git_meta = gh_service.clone_or_update(
                repository_id=str(repo.id),
                clone_url=repo.clone_url,
                branch=target_branch,
                token=token,
            )
            workspace_path = Path(git_meta["workspace_path"])
        except Exception:
            workspace_path = Path(f"/tmp/devora_workspaces/{repo.id}")

    return await service.index_workspaces(
        repository_id=repo.id,
        repo_path=workspace_path,
        db=db,
    )
