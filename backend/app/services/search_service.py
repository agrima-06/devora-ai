"""Code Search and Retrieval Service: provides keyword, symbol, and semantic search."""
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User
from app.services.repo_intelligence_service import generate_embedding_vector

logger = get_logger("search_service")


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


class CodeSearchService:
    """Service providing keyword, symbol, semantic search and architectural retrieval."""

    async def get_repository_for_user(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> Repository:
        """Fetch and verify tenant ownership of repository."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user.id,
        )
        result = await db.execute(stmt)
        repo = result.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)
        return repo

    async def search(
        self,
        repository_id: uuid.UUID,
        query: str,
        user: User,
        db: AsyncSession,
        search_type: str = "all",
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Perform search across code files, symbols, and embeddings based on search_type."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        q = query.strip()
        if not q:
            return {"repository_id": repo.id, "query": "", "search_type": search_type, "results": [], "total_matches": 0}

        results: List[Dict[str, Any]] = []

        if search_type in ("symbol", "all"):
            symbol_results = await self.search_symbols(repo.id, q, db, limit=limit)
            results.extend(symbol_results)

        if search_type in ("keyword", "all"):
            keyword_results = await self.search_keywords(repo.id, q, db, limit=limit)
            results.extend(keyword_results)

        if search_type in ("semantic", "all"):
            semantic_results = await self.search_semantic(repo.id, q, db, limit=limit)
            results.extend(semantic_results)

        # De-duplicate results while maintaining priority order
        seen = set()
        unique_results = []
        for r in results:
            key = (r["file_path"], r.get("line_number"), r.get("symbol_name"))
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        return {
            "repository_id": repo.id,
            "query": query,
            "search_type": search_type,
            "results": unique_results[:limit],
            "total_matches": len(unique_results),
        }

    async def search_symbols(
        self,
        repository_id: uuid.UUID,
        query: str,
        db: AsyncSession,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search symbol definitions (functions, classes, methods) in RepositoryKnowledge."""
        stmt = (
            select(RepositoryKnowledge)
            .where(
                RepositoryKnowledge.repository_id == repository_id,
                RepositoryKnowledge.symbol_type.in_(["function", "class", "method", "interface"]),
                RepositoryKnowledge.symbol_name.ilike(f"%{query}%"),
            )
            .limit(limit)
        )
        res = await db.execute(stmt)
        entries = res.scalars().all()

        results = []
        for e in entries:
            meta = e.meta_info or {}
            results.append({
                "file_path": e.file_path,
                "match_type": "symbol",
                "line_number": meta.get("start_line", 1),
                "snippet": meta.get("signature") or e.symbol_name or "",
                "symbol_name": e.symbol_name,
                "symbol_type": e.symbol_type,
                "score": 1.0,
            })
        return results

    async def search_keywords(
        self,
        repository_id: uuid.UUID,
        query: str,
        db: AsyncSession,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search exact keywords across repository files on disk or stored summaries."""
        # 1. Fetch tracked repository files
        files_stmt = select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        files_res = await db.execute(files_stmt)
        files = files_res.scalars().all()

        workspace_path = Path(settings.WORKSPACE_BASE_DIR) / str(repository_id)
        results: List[Dict[str, Any]] = []
        q_lower = query.lower()

        # Check if workspace directory exists on disk
        if workspace_path.exists() and workspace_path.is_dir():
            for f in files:
                full_file = workspace_path / f.file_path
                if not full_file.is_file():
                    continue

                try:
                    with open(full_file, "r", encoding="utf-8", errors="replace") as fh:
                        lines = fh.readlines()

                    for idx, line in enumerate(lines, start=1):
                        if q_lower in line.lower():
                            # Extract 3-line snippet context
                            start_idx = max(0, idx - 2)
                            end_idx = min(len(lines), idx + 2)
                            snippet = "".join(lines[start_idx:end_idx]).strip()

                            results.append({
                                "file_path": f.file_path,
                                "match_type": "keyword",
                                "line_number": idx,
                                "snippet": snippet,
                                "symbol_name": None,
                                "symbol_type": None,
                                "score": 0.9,
                            })
                            if len(results) >= limit:
                                return results
                except Exception as exc:
                    logger.warning("file_search_read_error", path=f.file_path, error=str(exc))
        else:
            # Fallback to searching summaries and knowledge content
            k_stmt = (
                select(RepositoryKnowledge)
                .where(
                    RepositoryKnowledge.repository_id == repository_id,
                    RepositoryKnowledge.content.ilike(f"%{query}%"),
                )
                .limit(limit)
            )
            k_res = await db.execute(k_stmt)
            for k in k_res.scalars().all():
                meta = k.meta_info or {}
                results.append({
                    "file_path": k.file_path,
                    "match_type": "keyword",
                    "line_number": meta.get("start_line", 1),
                    "snippet": k.content[:200],
                    "symbol_name": k.symbol_name,
                    "symbol_type": k.symbol_type,
                    "score": 0.8,
                })

        return results

    async def search_semantic(
        self,
        repository_id: uuid.UUID,
        query: str,
        db: AsyncSession,
        limit: int = 15,
        threshold: float = 0.12,
    ) -> List[Dict[str, Any]]:
        """Semantic search using embedding vector cosine similarity."""
        query_vec = generate_embedding_vector(query)

        stmt = select(RepositoryKnowledge).where(
            RepositoryKnowledge.repository_id == repository_id
        )
        res = await db.execute(stmt)
        entries = res.scalars().all()

        scored_entries = []
        for e in entries:
            if not e.embedding:
                continue
            sim = cosine_similarity(query_vec, e.embedding)
            if sim >= threshold:
                scored_entries.append((sim, e))

        scored_entries.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, e in scored_entries[:limit]:
            meta = e.meta_info or {}
            results.append({
                "file_path": e.file_path,
                "match_type": "semantic",
                "line_number": meta.get("start_line", 1),
                "snippet": e.content[:250],
                "symbol_name": e.symbol_name,
                "symbol_type": e.symbol_type,
                "score": round(sim, 4),
            })
        return results

    async def get_architecture_summary(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Retrieve aggregated architecture summary and coding conventions."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        # Retrieve architecture and conventions from RepositoryKnowledge
        stmt = select(RepositoryKnowledge).where(
            RepositoryKnowledge.repository_id == repo.id,
            RepositoryKnowledge.symbol_type.in_(["architecture_summary", "coding_conventions"]),
        )
        res = await db.execute(stmt)
        knowledge_entries = res.scalars().all()

        arch_text = ""
        conv_text = ""
        for entry in knowledge_entries:
            if entry.symbol_type == "architecture_summary":
                arch_text = entry.content
            elif entry.symbol_type == "coding_conventions":
                conv_text = entry.content

        meta = repo.meta_info or {}

        # Fallback if not yet indexed
        if not arch_text:
            arch_text = (
                f"Repository '{repo.name}' has not been indexed yet. "
                "Trigger repository indexing to extract architectural patterns, entry points, and dependencies."
            )
        if not conv_text:
            conv_text = "Repository indexing pending."

        return {
            "repository_id": repo.id,
            "primary_language": repo.language,
            "current_commit_sha": repo.current_commit_sha,
            "frameworks": meta.get("frameworks", []),
            "entry_points": meta.get("entry_points", []),
            "manifests": meta.get("manifests", []),
            "total_files": meta.get("total_files", 0),
            "total_lines": meta.get("total_lines", 0),
            "architecture_summary": arch_text,
            "coding_conventions": conv_text,
        }

    async def list_files(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
    ) -> List[RepositoryFile]:
        """List indexed files for repository."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RepositoryFile).where(RepositoryFile.repository_id == repo.id)
        stmt = stmt.order_by(RepositoryFile.file_path.asc())
        res = await db.execute(stmt)
        files = res.scalars().all()

        if category:
            files = [f for f in files if (f.meta_info or {}).get("category") == category]

        return list(files)

    async def list_symbols(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        symbol_type: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List extracted symbols from repository knowledge."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RepositoryKnowledge).where(
            RepositoryKnowledge.repository_id == repo.id,
            RepositoryKnowledge.symbol_type.in_(["function", "class", "method", "interface"]),
        )
        if symbol_type:
            stmt = stmt.where(RepositoryKnowledge.symbol_type == symbol_type)
        if file_path:
            stmt = stmt.where(RepositoryKnowledge.file_path == file_path)

        stmt = stmt.order_by(RepositoryKnowledge.file_path.asc(), RepositoryKnowledge.symbol_name.asc())
        res = await db.execute(stmt)
        entries = res.scalars().all()

        symbols = []
        for e in entries:
            meta = e.meta_info or {}
            symbols.append({
                "name": e.symbol_name,
                "type": e.symbol_type,
                "file_path": e.file_path,
                "start_line": meta.get("start_line", 1),
                "end_line": meta.get("end_line", 1),
                "signature": meta.get("signature", e.symbol_name or ""),
                "docstring": meta.get("docstring"),
            })
        return symbols
