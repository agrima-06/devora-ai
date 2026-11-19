"""Semantic Vector Memory API endpoints."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.memory import (
    MemoryCreate,
    MemoryFeedbackCreate,
    MemoryFeedbackResponse,
    MemoryResponse,
    MemorySearchQuery,
    MemorySearchResult,
    MemoryStatsResponse,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/repositories/{repository_id}/memories", tags=["Semantic Memory"])


@router.get(
    "",
    response_model=List[MemoryResponse],
    summary="List engineering memories for a repository",
)
async def list_memories(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by memory category"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    is_stale: Optional[bool] = Query(None, description="Filter by staleness"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List repository memories with category and verification status filtering."""
    service = MemoryService()
    return await service.list_memories(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
        verification_status=verification_status,
        is_stale=is_stale,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update an engineering memory",
)
async def create_memory(
    repository_id: uuid.UUID,
    payload: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store an explicit convention, decision, or architectural memory."""
    service = MemoryService()
    return await service.create_or_update_memory(
        repository_id=repository_id,
        category=payload.category,
        title=payload.title,
        content=payload.content,
        user=current_user,
        db=db,
        source_reference=payload.source_reference,
        commit_sha=payload.commit_sha,
        verification_status=payload.verification_status,
        access_scope=payload.access_scope,
        meta_info=payload.meta_info,
    )


@router.post(
    "/search",
    response_model=List[MemorySearchResult],
    summary="Perform semantic vector search across repository memories",
)
async def search_memories(
    repository_id: uuid.UUID,
    payload: MemorySearchQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Semantic vector search using pgvector cosine distance and verification weighting."""
    service = MemoryService()
    return await service.search_memories(
        repository_id=repository_id,
        query=payload.query,
        user=current_user,
        db=db,
        category=payload.category,
        verification_status=payload.verification_status,
        include_stale=payload.include_stale,
        limit=payload.limit,
        threshold=payload.threshold,
    )


@router.get(
    "/stats",
    response_model=MemoryStatsResponse,
    summary="Get memory aggregation statistics for repository",
)
async def get_memory_stats(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve memory counts by category, verification status, and staleness."""
    service = MemoryService()
    return await service.get_memory_stats(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Get single memory detail",
)
async def get_memory(
    repository_id: uuid.UUID,
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch an individual memory by ID."""
    service = MemoryService()
    return await service.get_memory(
        repository_id=repository_id,
        memory_id=memory_id,
        user=current_user,
        db=db,
    )


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Update a memory entry",
)
async def update_memory(
    repository_id: uuid.UUID,
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update title, content, status or staleness of a memory."""
    service = MemoryService()
    return await service.update_memory(
        repository_id=repository_id,
        memory_id=memory_id,
        user=current_user,
        db=db,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        verification_status=payload.verification_status,
        is_stale=payload.is_stale,
        stale_reason=payload.stale_reason,
    )


@router.post(
    "/{memory_id}/stale",
    response_model=MemoryResponse,
    summary="Mark a memory as stale",
)
async def mark_memory_stale(
    repository_id: uuid.UUID,
    memory_id: uuid.UUID,
    reason: Optional[str] = Query(None, description="Reason for marking stale"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark memory as outdated or superseded."""
    service = MemoryService()
    return await service.mark_memory_stale(
        repository_id=repository_id,
        memory_id=memory_id,
        user=current_user,
        db=db,
        reason=reason,
    )


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory entry",
)
async def delete_memory(
    repository_id: uuid.UUID,
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a memory entry from the repository knowledge base."""
    service = MemoryService()
    await service.delete_memory(
        repository_id=repository_id,
        memory_id=memory_id,
        user=current_user,
        db=db,
    )
    return None


@router.post(
    "/{memory_id}/feedback",
    response_model=MemoryFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit developer utility feedback on retrieved memory",
)
async def submit_memory_feedback(
    repository_id: uuid.UUID,
    memory_id: uuid.UUID,
    payload: MemoryFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record whether a retrieved convention or memory was helpful."""
    service = MemoryService()
    return await service.record_feedback(
        repository_id=repository_id,
        memory_id=memory_id,
        is_helpful=payload.is_helpful,
        user=current_user,
        db=db,
        task_id=payload.task_id,
        notes=payload.notes,
    )
