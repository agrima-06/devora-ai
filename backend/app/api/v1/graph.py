"""API Router for Phase 10 Stage 10.1: Cross-File Symbol and Dependency Graph Engine."""
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.models.user import User
from app.schemas.graph import (
    GraphDependenciesResponse,
    GraphIndexRequest,
    GraphIndexingResponse,
    GraphNodeDetailResponse,
    GraphNodesListResponse,
    GraphUnresolvedReferencesResponse,
    RepositoryGraphSummaryResponse,
)
from app.services.github_service import GitHubService
from app.services.graph_service import RepositoryGraphService

router = APIRouter(prefix="/repositories/{repository_id}/graph", tags=["Repository Dependency Graph"])


@router.get(
    "",
    response_model=RepositoryGraphSummaryResponse,
    summary="Get repository dependency graph summary and statistics",
)
async def get_graph_summary(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryGraphSummaryResponse:
    """Retrieve node counts, edge counts, language breakdowns, and resolution counters."""
    service = RepositoryGraphService()
    return await service.get_summary(
        repository_id=repository_id,
        user_id=current_user.id,
        db=db,
    )


@router.post(
    "/index",
    response_model=GraphIndexingResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger incremental or full dependency graph indexing",
)
async def index_repository_graph(
    repository_id: uuid.UUID,
    payload: Optional[GraphIndexRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphIndexingResponse:
    """Scan workspace files, extract symbols, resolve cross-file dependencies, and persist graph."""
    service = RepositoryGraphService()
    repo = await service.get_repository_for_user(repository_id, current_user.id, db)

    gh_service = GitHubService()
    token = current_user.github_access_token or settings.GITHUB_TOKEN
    target_branch = (payload.branch if payload else None) or repo.default_branch or "main"

    git_meta = gh_service.clone_or_update(
        repository_id=str(repo.id),
        clone_url=repo.clone_url,
        branch=target_branch,
        token=token,
    )
    workspace_path = Path(git_meta["workspace_path"])
    commit_sha = git_meta.get("commit_sha")

    return await service.index_repository_graph(
        repository_id=repo.id,
        user=current_user,
        db=db,
        workspace_path=workspace_path,
        commit_sha=commit_sha,
        force_reindex=payload.force_reindex if payload else False,
    )


@router.get(
    "/nodes",
    response_model=GraphNodesListResponse,
    summary="Query paginated graph nodes with filtering",
)
async def list_graph_nodes(
    repository_id: uuid.UUID,
    node_type: Optional[str] = Query(None, description="Filter by node type: FILE, CLASS, FUNCTION, METHOD, etc."),
    language: Optional[str] = Query(None, description="Filter by programming language"),
    file_path: Optional[str] = Query(None, description="Filter by file path"),
    q: Optional[str] = Query(None, description="Search symbol or file name"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNodesListResponse:
    """Retrieve paginated graph nodes for a repository with optional type and name filters."""
    service = RepositoryGraphService()
    return await service.get_nodes(
        repository_id=repository_id,
        user_id=current_user.id,
        db=db,
        node_type=node_type,
        language=language,
        file_path=file_path,
        search_query=q,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/nodes/{node_id}",
    response_model=GraphNodeDetailResponse,
    summary="Get graph node details with direct relationships",
)
async def get_graph_node_detail(
    repository_id: uuid.UUID,
    node_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeDetailResponse:
    """Fetch node entity and its incoming and outgoing dependency edges."""
    service = RepositoryGraphService()
    return await service.get_node_detail(
        repository_id=repository_id,
        node_id=node_id,
        user_id=current_user.id,
        db=db,
    )


@router.get(
    "/dependencies",
    response_model=GraphDependenciesResponse,
    summary="Get bounded dependency subgraph from a root node",
)
async def get_graph_dependencies(
    repository_id: uuid.UUID,
    node_id: uuid.UUID = Query(..., description="Root node UUID to traverse from"),
    direction: str = Query("outgoing", description="Traversal direction: outgoing, incoming, or both"),
    max_depth: int = Query(2, ge=1, le=5, description="Maximum traversal depth (1 to 5)"),
    edge_type: Optional[str] = Query(None, description="Optional filter: IMPORTS, DEPENDS_ON, INHERITS, etc."),
    limit: int = Query(100, ge=1, le=200, description="Maximum nodes in returned subgraph"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphDependenciesResponse:
    """Perform bounded breadth-first traversal returning a connected dependency subgraph."""
    service = RepositoryGraphService()
    return await service.get_dependencies(
        repository_id=repository_id,
        root_node_id=node_id,
        user_id=current_user.id,
        db=db,
        direction=direction,
        max_depth=max_depth,
        edge_type=edge_type,
        limit=limit,
    )


@router.get(
    "/unresolved",
    response_model=GraphUnresolvedReferencesResponse,
    summary="List unresolved dependencies and external imports",
)
async def list_unresolved_references(
    repository_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphUnresolvedReferencesResponse:
    """Retrieve unresolved or ambiguous references across repository files."""
    service = RepositoryGraphService()
    return await service.get_unresolved_references(
        repository_id=repository_id,
        user_id=current_user.id,
        db=db,
        limit=limit,
        offset=offset,
    )
