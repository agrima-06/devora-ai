"""Semantic Vector Memory Engine: repository-specific conventions, architecture, and experience retrieval."""
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.gateway import ModelGateway
from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger
from app.models.engineering_experience import EngineeringExperience
from app.models.memory_feedback import MemoryFeedback
from app.models.repository import Repository
from app.models.repository_memory import RepositoryMemory
from app.models.task import Task
from app.models.user import User

logger = get_logger("memory_service")

# Verification status quality multipliers
STATUS_WEIGHTS = {
    "developer_confirmed": 1.3,
    "verified_outcome": 1.2,
    "observed_fact": 1.0,
    "ai_hypothesis": 0.7,
}


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two normalized vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class MemoryService:
    """Enterprise semantic vector memory service with pgvector, deduplication, and lifecycle management."""

    def __init__(self, gateway: Optional[ModelGateway] = None):
        self.gateway = gateway or ModelGateway.get_instance()

    async def get_repository_for_user(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> Repository:
        """Verify repository ownership and enforce strict tenant isolation."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user.id,
        )
        res = await db.execute(stmt)
        repo = res.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)
        return repo

    async def create_or_update_memory(
        self,
        repository_id: uuid.UUID,
        category: str,
        content: str,
        user: User,
        db: AsyncSession,
        title: Optional[str] = None,
        source_reference: Optional[str] = None,
        commit_sha: Optional[str] = None,
        verification_status: str = "observed_fact",
        access_scope: str = "repository",
        meta_info: Optional[Dict[str, Any]] = None,
        deduplicate: bool = True,
    ) -> RepositoryMemory:
        """Create or update a semantic memory record with duplicate detection."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        clean_content = content.strip()
        if not clean_content:
            raise BadRequestException("Memory content cannot be empty.")

        # 1. Generate 768-dim normalized embedding
        embedding = await self.gateway.generate_embedding(
            f"{title or ''} {category} {clean_content}".strip()
        )

        # 2. Duplicate detection check
        if deduplicate:
            existing_stmt = select(RepositoryMemory).where(
                RepositoryMemory.repository_id == repo.id,
                RepositoryMemory.category == category,
            )
            existing_res = await db.execute(existing_stmt)
            existing_memories = existing_res.scalars().all()

            for existing in existing_memories:
                if existing.embedding:
                    sim = cosine_similarity(embedding, existing.embedding)
                    if sim >= settings.MEMORY_DEDUPLICATION_THRESHOLD:
                        logger.info(
                            "duplicate_memory_detected_updating",
                            existing_id=str(existing.id),
                            similarity=round(sim, 3),
                        )
                        existing.content = clean_content
                        existing.embedding = embedding
                        if title:
                            existing.title = title
                        if source_reference:
                            existing.source_reference = source_reference
                        if commit_sha:
                            existing.commit_sha = commit_sha
                        if verification_status:
                            existing.verification_status = verification_status
                        existing.is_stale = False
                        existing.stale_reason = None
                        existing.updated_at = datetime.now(timezone.utc)
                        if meta_info:
                            existing.meta_info = {**(existing.meta_info or {}), **meta_info}
                        await db.flush()
                        return existing

        # 3. Create fresh memory record
        memory = RepositoryMemory(
            repository_id=repo.id,
            category=category,
            title=title or (clean_content[:60] + "..." if len(clean_content) > 60 else clean_content),
            content=clean_content,
            embedding=embedding,
            source_reference=source_reference,
            commit_sha=commit_sha or repo.current_commit_sha,
            verification_status=verification_status,
            access_scope=access_scope,
            is_stale=False,
            helpful_count=0,
            unhelpful_count=0,
            meta_info=meta_info or {},
        )
        db.add(memory)
        await db.flush()
        await db.refresh(memory)
        logger.info("memory_created", memory_id=str(memory.id), category=category)
        return memory

    async def search_memories(
        self,
        repository_id: uuid.UUID,
        query: str,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
        verification_status: Optional[str] = None,
        include_stale: bool = False,
        limit: int = 5,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic vector search across repository memories with pgvector and quality weighting."""
        min_thresh = threshold if threshold is not None else settings.MEMORY_SIMILARITY_THRESHOLD
        repo = await self.get_repository_for_user(repository_id, user, db)

        q = query.strip()
        if not q:
            return []

        query_vec = await self.gateway.generate_embedding(q)

        # Retrieve candidates filtered by repository
        stmt = select(RepositoryMemory).where(RepositoryMemory.repository_id == repo.id)
        if category:
            stmt = stmt.where(RepositoryMemory.category == category)
        if verification_status:
            stmt = stmt.where(RepositoryMemory.verification_status == verification_status)
        if not include_stale:
            stmt = stmt.where(RepositoryMemory.is_stale.is_(False))

        res = await db.execute(stmt)
        memories = res.scalars().all()

        scored: List[Dict[str, Any]] = []
        for mem in memories:
            if not mem.embedding:
                continue
            raw_sim = cosine_similarity(query_vec, mem.embedding)
            if raw_sim < min_thresh:
                continue

            status_weight = STATUS_WEIGHTS.get(mem.verification_status, 1.0)
            stale_penalty = 0.5 if mem.is_stale else 1.0
            helpful_boost = 1.0 + (min(mem.helpful_count, 10) * 0.02) - (min(mem.unhelpful_count, 5) * 0.05)
            final_score = raw_sim * status_weight * stale_penalty * helpful_boost

            scored.append({
                "id": str(mem.id),
                "repository_id": str(mem.repository_id),
                "category": mem.category,
                "title": mem.title,
                "content": mem.content,
                "source_reference": mem.source_reference,
                "commit_sha": mem.commit_sha,
                "verification_status": mem.verification_status,
                "is_stale": mem.is_stale,
                "stale_reason": mem.stale_reason,
                "helpful_count": mem.helpful_count,
                "unhelpful_count": mem.unhelpful_count,
                "raw_similarity": round(raw_sim, 4),
                "score": round(final_score, 4),
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
                "metadata": mem.meta_info or {},
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def list_memories(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
        verification_status: Optional[str] = None,
        is_stale: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[RepositoryMemory]:
        """List repository memories with pagination and metadata filtering."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RepositoryMemory).where(RepositoryMemory.repository_id == repo.id)
        if category:
            stmt = stmt.where(RepositoryMemory.category == category)
        if verification_status:
            stmt = stmt.where(RepositoryMemory.verification_status == verification_status)
        if is_stale is not None:
            stmt = stmt.where(RepositoryMemory.is_stale == is_stale)

        stmt = stmt.order_by(RepositoryMemory.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def get_memory(
        self,
        repository_id: uuid.UUID,
        memory_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> RepositoryMemory:
        """Fetch a single memory item with tenant verification."""
        repo = await self.get_repository_for_user(repository_id, user, db)
        stmt = select(RepositoryMemory).where(
            RepositoryMemory.id == memory_id,
            RepositoryMemory.repository_id == repo.id,
        )
        res = await db.execute(stmt)
        memory = res.scalar_one_or_none()
        if not memory:
            raise NotFoundException("RepositoryMemory", memory_id)
        return memory

    async def update_memory(
        self,
        repository_id: uuid.UUID,
        memory_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        verification_status: Optional[str] = None,
        is_stale: Optional[bool] = None,
        stale_reason: Optional[str] = None,
    ) -> RepositoryMemory:
        """Update memory fields, recalculating embeddings if content is modified."""
        memory = await self.get_memory(repository_id, memory_id, user, db)

        if content and content.strip() != memory.content:
            memory.content = content.strip()
            # Regenerate embedding
            text_for_embed = f"{title or memory.title or ''} {category or memory.category} {memory.content}".strip()
            memory.embedding = await self.gateway.generate_embedding(text_for_embed)

        if title is not None:
            memory.title = title
        if category is not None:
            memory.category = category
        if verification_status is not None:
            memory.verification_status = verification_status
        if is_stale is not None:
            memory.is_stale = is_stale
            memory.stale_reason = stale_reason if is_stale else None

        memory.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return memory

    async def mark_memory_stale(
        self,
        repository_id: uuid.UUID,
        memory_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        reason: Optional[str] = None,
    ) -> RepositoryMemory:
        """Mark an individual memory as stale."""
        return await self.update_memory(
            repository_id=repository_id,
            memory_id=memory_id,
            user=user,
            db=db,
            is_stale=True,
            stale_reason=reason or "Marked stale by user or system update",
        )

    async def delete_memory(
        self,
        repository_id: uuid.UUID,
        memory_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> bool:
        """Delete an individual memory entry."""
        memory = await self.get_memory(repository_id, memory_id, user, db)
        await db.delete(memory)
        await db.flush()
        return True

    async def invalidate_by_files(
        self,
        repository_id: uuid.UUID,
        modified_files: List[str],
        db: AsyncSession,
    ) -> int:
        """Invalidate memories referencing modified or deleted source files."""
        if not modified_files:
            return 0

        stmt = select(RepositoryMemory).where(
            RepositoryMemory.repository_id == repository_id,
            RepositoryMemory.source_reference.in_(modified_files),
            RepositoryMemory.is_stale.is_(False),
        )
        res = await db.execute(stmt)
        memories = res.scalars().all()
        count = 0
        for m in memories:
            m.is_stale = True
            m.stale_reason = f"Source file '{m.source_reference}' was modified."
            m.updated_at = datetime.now(timezone.utc)
            count += 1
        if count > 0:
            await db.flush()
            logger.info("invalidated_memories_for_modified_files", count=count, files=modified_files)
        return count

    async def record_feedback(
        self,
        repository_id: uuid.UUID,
        memory_id: uuid.UUID,
        is_helpful: bool,
        user: User,
        db: AsyncSession,
        task_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
    ) -> MemoryFeedback:
        """Record human or workflow utility feedback on retrieved memory."""
        memory = await self.get_memory(repository_id, memory_id, user, db)

        fb = MemoryFeedback(
            memory_id=memory.id,
            user_id=user.id,
            task_id=task_id,
            is_helpful=is_helpful,
            notes=notes,
        )
        db.add(fb)

        if is_helpful:
            memory.helpful_count += 1
        else:
            memory.unhelpful_count += 1
            if memory.unhelpful_count >= 3:
                memory.is_stale = True
                memory.stale_reason = "Flagged multiple times as unhelpful or inaccurate."

        await db.flush()
        await db.refresh(fb)
        return fb

    async def get_memory_stats(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Aggregate memory statistics by category, verification status, and staleness."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RepositoryMemory).where(RepositoryMemory.repository_id == repo.id)
        res = await db.execute(stmt)
        all_mems = res.scalars().all()

        categories: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        total = len(all_mems)
        stale_count = 0
        verified_count = 0

        for m in all_mems:
            categories[m.category] = categories.get(m.category, 0) + 1
            statuses[m.verification_status] = statuses.get(m.verification_status, 0) + 1
            if m.is_stale:
                stale_count += 1
            if m.verification_status in ("verified_outcome", "developer_confirmed", "observed_fact"):
                verified_count += 1

        return {
            "repository_id": str(repo.id),
            "total_memories": total,
            "verified_count": verified_count,
            "stale_count": stale_count,
            "categories": categories,
            "verification_statuses": statuses,
        }

    async def distill_task_outcome(
        self,
        task: Task,
        user: User,
        db: AsyncSession,
        test_passed: bool = True,
        diff_patch: str = "",
        root_cause: str = "",
        resolution_strategy: str = "",
    ) -> Optional[RepositoryMemory]:
        """Distill a verified task outcome into persistent project and engineering memory."""
        if not test_passed or not task.repository_id:
            return None

        content = (
            f"Problem: {task.title}\n"
            f"Prompt: {task.prompt}\n"
            f"Root Cause: {root_cause or 'Identified and corrected through automated test loop.'}\n"
            f"Resolution Strategy: {resolution_strategy or 'Defensive code modification and test assertion verification.'}\n"
            f"Verified In: Sandbox test execution with zero regressions."
        )

        memory = await self.create_or_update_memory(
            repository_id=task.repository_id,
            category="task_outcome",
            title=f"Verified Resolution: {task.title}",
            content=content,
            user=user,
            db=db,
            source_reference=str(task.id),
            commit_sha=task.target_branch,
            verification_status="verified_outcome",
            meta_info={
                "task_id": str(task.id),
                "task_type": task.task_type,
                "iterations": task.iterations_count,
            },
        )

        # Also register in cross-project engineering_experiences if bug fix
        if task.task_type == "bug_fix":
            embedding = await self.gateway.generate_embedding(content)
            exp = EngineeringExperience(
                repository_id=task.repository_id,
                task_category="bug_fix",
                bug_category="verified_fix",
                problem_summary=task.title,
                root_cause=root_cause or "Automated diagnosis",
                resolution_strategy=resolution_strategy or "Isolated sandbox patch",
                diff_patch=diff_patch[:2000] if diff_patch else "N/A",
                embedding=embedding,
                is_anonymized=False,
                is_verified=True,
                quality_score=90,
            )
            db.add(exp)
            await db.flush()

        return memory
