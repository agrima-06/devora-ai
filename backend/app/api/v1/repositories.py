"""Repository metadata CRUD endpoints."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.models.indexing_job import IndexingJob
from app.models.project import Project
from app.models.repository import Repository
from app.models.user import User
from app.schemas.repository import (
    CodeSearchResponse,
    IndexRepositoryRequest,
    IndexingJobResponse,
    RepositoryArchitectureResponse,
    RepositoryCreate,
    RepositoryFileResponse,
    RepositoryResponse,
    RepositorySymbolResponse,
    RepositorySyncResponse,
    RepositoryUpdate,
)
from app.services.repo_intelligence_service import RepositoryIntelligenceService
from app.services.search_service import CodeSearchService

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a new repository to a project",
)
async def create_repository(
    payload: RepositoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Connect a code repository to an existing project owned by the user."""
    # Verify project exists and belongs to user
    project_result = await db.execute(
        select(Project).where(Project.id == payload.project_id, Project.owner_id == current_user.id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise NotFoundException("Project", payload.project_id)

    # Check for duplicate repo in project
    existing = await db.execute(
        select(Repository).where(
            Repository.project_id == payload.project_id,
            Repository.full_name == payload.full_name,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Repository '{payload.full_name}' is already connected to this project.")

    repo = Repository(
        project_id=payload.project_id,
        user_id=current_user.id,
        name=payload.name,
        full_name=payload.full_name,
        clone_url=payload.clone_url,
        default_branch=payload.default_branch,
        language=payload.language,
        meta_info=payload.meta_info,
    )
    db.add(repo)
    await db.flush()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.get(
    "",
    response_model=List[RepositoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List repositories",
)
async def list_repositories(
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryResponse]:
    """List all connected repositories, optionally filtered by project."""
    query = select(Repository).where(Repository.user_id == current_user.id)
    if project_id:
        query = query.where(Repository.project_id == project_id)
    query = query.order_by(Repository.created_at.desc())

    result = await db.execute(query)
    repos = result.scalars().all()
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.get(
    "/{repo_id}",
    response_model=RepositoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve repository details",
)
async def get_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Retrieve repository metadata, ensuring tenant ownership."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repo_id)
    return RepositoryResponse.model_validate(repo)


@router.put(
    "/{repo_id}",
    response_model=RepositoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update repository metadata",
)
async def update_repository(
    repo_id: uuid.UUID,
    payload: RepositoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Update repository configuration."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repo_id)

    if payload.name is not None:
        repo.name = payload.name
    if payload.default_branch is not None:
        repo.default_branch = payload.default_branch
    if payload.language is not None:
        repo.language = payload.language
    if payload.meta_info is not None:
        repo.meta_info = payload.meta_info

    await db.flush()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.delete(
    "/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a repository",
)
async def delete_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete repository and all associated tasks, plans, and knowledge."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repo_id)

    await db.delete(repo)
    await db.flush()


@router.post(
    "/{repo_id}/sync",
    response_model=RepositorySyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync repository metadata",
)
async def sync_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositorySyncResponse:
    """Trigger repository metadata synchronization."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repo_id)

    repo.last_synced_at = datetime.now(timezone.utc)
    await db.flush()

    return RepositorySyncResponse(
        repository_id=repo.id,
        status="SYNCED",
        message="Repository metadata successfully synchronized.",
    )


@router.post(
    "/{repo_id}/index",
    response_model=IndexingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger repository indexing",
)
async def trigger_indexing(
    repo_id: uuid.UUID,
    payload: Optional[IndexRepositoryRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IndexingJobResponse:
    """Trigger repository intelligence scanning, AST parsing, and knowledge indexing."""
    service = RepositoryIntelligenceService()
    branch = payload.branch if payload else None
    force_reindex = payload.force_reindex if payload else False

    job = await service.index_repository(
        repository_id=repo_id,
        user=current_user,
        db=db,
        branch=branch,
        force_reindex=force_reindex,
    )
    return IndexingJobResponse.model_validate(job)


@router.get(
    "/{repo_id}/index/status",
    response_model=IndexingJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get repository indexing status",
)
async def get_indexing_status(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IndexingJobResponse:
    """Retrieve the latest indexing job status for the repository."""
    repo_res = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    )
    repo = repo_res.scalar_one_or_none()
    if not repo:
        raise NotFoundException("Repository", repo_id)

    job_res = await db.execute(
        select(IndexingJob)
        .where(IndexingJob.repository_id == repo.id)
        .order_by(IndexingJob.created_at.desc())
    )
    job = job_res.scalars().first()
    if not job:
        raise NotFoundException("IndexingJob for Repository", repo_id)

    return IndexingJobResponse.model_validate(job)


@router.get(
    "/{repo_id}/architecture",
    response_model=RepositoryArchitectureResponse,
    status_code=status.HTTP_200_OK,
    summary="Get repository architecture and coding conventions",
)
async def get_repository_architecture(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryArchitectureResponse:
    """Retrieve synthesized architecture, frameworks, entry points, and coding conventions."""
    search_service = CodeSearchService()
    data = await search_service.get_architecture_summary(repo_id, current_user, db)
    return RepositoryArchitectureResponse(**data)


@router.get(
    "/{repo_id}/files",
    response_model=List[RepositoryFileResponse],
    status_code=status.HTTP_200_OK,
    summary="List indexed files for a repository",
)
async def get_repository_files(
    repo_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by category (source, test, config, documentation, manifest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryFileResponse]:
    """Retrieve list of indexed repository files with lines count and summary."""
    search_service = CodeSearchService()
    files = await search_service.list_files(repo_id, current_user, db, category=category)
    return [RepositoryFileResponse.model_validate(f) for f in files]


@router.get(
    "/{repo_id}/symbols",
    response_model=List[RepositorySymbolResponse],
    status_code=status.HTTP_200_OK,
    summary="List extracted symbols for a repository",
)
async def get_repository_symbols(
    repo_id: uuid.UUID,
    symbol_type: Optional[str] = Query(None, description="Filter by symbol type (function, class, method)"),
    file_path: Optional[str] = Query(None, description="Filter by file path"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositorySymbolResponse]:
    """Retrieve extracted classes, functions, and methods with line numbers and signatures."""
    search_service = CodeSearchService()
    symbols = await search_service.list_symbols(repo_id, current_user, db, symbol_type=symbol_type, file_path=file_path)
    return [RepositorySymbolResponse(**s) for s in symbols]


@router.get(
    "/{repo_id}/search",
    response_model=CodeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search code across repository",
)
async def search_code(
    repo_id: uuid.UUID,
    q: str = Query(..., min_length=1, description="Search query string"),
    search_type: str = Query("all", pattern="^(all|keyword|symbol|semantic)$", description="Search type"),
    limit: int = Query(25, ge=1, le=100, description="Max results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeSearchResponse:
    """Search code across repository using keyword, symbol, or semantic search."""
    search_service = CodeSearchService()
    res = await search_service.search(
        repository_id=repo_id,
        query=q,
        user=current_user,
        db=db,
        search_type=search_type,
        limit=limit,
    )
    return CodeSearchResponse(**res)
