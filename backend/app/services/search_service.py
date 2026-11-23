"""Code Search and Retrieval Service: provides keyword, symbol, semantic, and hybrid search."""
import fnmatch
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.exceptions import scrub_credentials
from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User
from app.schemas.architecture import (
    HybridSearchFilter,
    HybridSearchResponse,
    HybridSearchResultItem,
)
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

    def _infer_language(self, path_str: str) -> Optional[str]:
        """Infer programming language from file extension."""
        ext = Path(path_str).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sql": "sql",
            ".sh": "shell",
        }
        return mapping.get(ext)

    async def search_hybrid(
        self,
        repository_id: uuid.UUID,
        query: str,
        user: User,
        db: AsyncSession,
        filters: Optional[HybridSearchFilter] = None,
        limit: int = 20,
        offset: int = 0,
        lexical_weight: float = 0.35,
        semantic_weight: float = 0.45,
        structural_weight: float = 0.20,
    ) -> HybridSearchResponse:
        """Execute multi-modal hybrid retrieval combining Lexical, Semantic, and Structural intelligence.

        Uses Weighted Reciprocal Rank Fusion (RRF) with explainable provenance and credential scrubbing.
        """
        start_time = time.time()
        repo = await self.get_repository_for_user(repository_id, user, db)

        q = (query or "").strip()
        if not q:
            return HybridSearchResponse(
                repository_id=str(repo.id),
                query="",
                total_matches=0,
                limit=limit,
                offset=offset,
                results=[],
                search_duration_seconds=0.0,
            )

        # Normalize weights
        total_w = lexical_weight + semantic_weight + structural_weight
        if total_w <= 0:
            w_lex, w_sem, w_struct = 0.35, 0.45, 0.20
        else:
            w_lex = lexical_weight / total_w
            w_sem = semantic_weight / total_w
            w_struct = structural_weight / total_w

        q_lower = q.lower()
        q_tokens = [tok for tok in re.split(r"\W+", q_lower) if len(tok) >= 2] or [q_lower]

        # Structure to track candidates across modalities
        # key: (file_path, line_number, symbol_name)
        candidates: Dict[Tuple[str, int, Optional[str]], Dict[str, Any]] = {}

        def get_or_create_candidate(
            file_path: str,
            line_number: int,
            symbol_name: Optional[str] = None,
            line_end: Optional[int] = None,
            symbol_type: Optional[str] = None,
            language: Optional[str] = None,
            package_name: Optional[str] = None,
            snippet: str = "",
        ) -> Dict[str, Any]:
            key = (file_path, line_number, symbol_name)
            if key not in candidates:
                inferred_lang = language or self._infer_language(file_path)
                candidates[key] = {
                    "file_path": file_path,
                    "line_number": line_number,
                    "line_end": line_end,
                    "symbol_name": symbol_name,
                    "symbol_type": symbol_type,
                    "package_name": package_name,
                    "language": inferred_lang,
                    "snippet": snippet or "",
                    "lexical_score": 0.0,
                    "semantic_score": 0.0,
                    "structural_score": 0.0,
                    "r_lex": None,
                    "r_sem": None,
                    "r_struct": None,
                }
            elif snippet and not candidates[key]["snippet"]:
                candidates[key]["snippet"] = snippet
            return candidates[key]

        # -------------------------------------------------------------
        # 1. LEXICAL RETRIEVAL
        # -------------------------------------------------------------
        lexical_items: List[Tuple[float, Dict[str, Any]]] = []

        # 1.1 Query RepositoryKnowledge
        k_stmt = select(RepositoryKnowledge).where(
            RepositoryKnowledge.repository_id == repo.id
        )
        k_res = await db.execute(k_stmt)
        all_knowledge = k_res.scalars().all()

        for k in all_knowledge:
            sym_name = k.symbol_name or ""
            fpath = k.file_path or ""
            content = k.content or ""
            meta = k.meta_info or {}
            score = 0.0

            if sym_name.lower() == q_lower:
                score = 1.0
            elif sym_name.lower().startswith(q_lower):
                score = 0.90
            elif any(tok in sym_name.lower() for tok in q_tokens):
                score = 0.80
            elif q_lower in Path(fpath).name.lower():
                score = 0.85
            elif q_lower in fpath.lower():
                score = 0.70
            elif any(tok in content.lower() for tok in q_tokens):
                score = 0.60

            if score > 0.0:
                snippet = meta.get("signature") or (content[:300] if content else sym_name)
                cand = get_or_create_candidate(
                    file_path=fpath,
                    line_number=meta.get("start_line", 1),
                    line_end=meta.get("end_line"),
                    symbol_name=sym_name or None,
                    symbol_type=k.symbol_type,
                    snippet=snippet,
                )
                lexical_items.append((score, cand))

        # 1.2 Query RepositoryGraphNode
        g_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repo.id
        )
        g_res = await db.execute(g_stmt)
        all_nodes = g_res.scalars().all()

        for node in all_nodes:
            node_name = node.name or ""
            fpath = node.file_path or ""
            q_name = node.qualified_name or ""
            score = 0.0

            if node_name.lower() == q_lower:
                score = 1.0
            elif node_name.lower().startswith(q_lower):
                score = 0.90
            elif any(tok in node_name.lower() for tok in q_tokens):
                score = 0.80
            elif q_lower in Path(fpath).name.lower():
                score = 0.85
            elif q_lower in q_name.lower():
                score = 0.75

            if score > 0.0 and fpath:
                cand = get_or_create_candidate(
                    file_path=fpath,
                    line_number=node.start_line or 1,
                    line_end=node.end_line,
                    symbol_name=node_name if node.node_type not in ("FILE", "DIRECTORY", "PACKAGE") else None,
                    symbol_type=node.node_type.lower(),
                    language=node.language,
                    package_name=(node.meta_info or {}).get("package_name"),
                    snippet=(node.meta_info or {}).get("signature") or node_name,
                )
                lexical_items.append((score, cand))

        # 1.3 Disk fallback/enrichment if workspace exists
        workspace_path = Path(settings.WORKSPACE_BASE_DIR) / str(repo.id)
        if workspace_path.exists() and workspace_path.is_dir():
            files_stmt = select(RepositoryFile).where(RepositoryFile.repository_id == repo.id)
            files_res = await db.execute(files_stmt)
            for f in files_res.scalars().all():
                full_path = workspace_path / f.file_path
                if not full_path.is_file():
                    continue
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                        for l_idx, line in enumerate(fh, start=1):
                            if q_lower in line.lower():
                                cand = get_or_create_candidate(
                                    file_path=f.file_path,
                                    line_number=l_idx,
                                    snippet=line.strip()[:300],
                                )
                                lexical_items.append((0.70, cand))
                                if len(lexical_items) > 100:
                                    break
                except Exception:
                    pass

        # Sort and assign 1-based ranks for lexical
        lexical_items.sort(key=lambda x: x[0], reverse=True)
        seen_lex_keys = set()
        lex_rank = 1
        for score, cand in lexical_items:
            k_key = (cand["file_path"], cand["line_number"], cand["symbol_name"])
            if k_key not in seen_lex_keys:
                seen_lex_keys.add(k_key)
                cand["lexical_score"] = max(cand["lexical_score"], round(score, 4))
                cand["r_lex"] = lex_rank
                lex_rank += 1

        # -------------------------------------------------------------
        # 2. SEMANTIC RETRIEVAL
        # -------------------------------------------------------------
        query_vec = generate_embedding_vector(q)
        semantic_items: List[Tuple[float, Dict[str, Any]]] = []

        for k in all_knowledge:
            if not k.embedding or not k.file_path:
                continue
            sim = cosine_similarity(query_vec, k.embedding)
            if sim >= 0.10:
                meta = k.meta_info or {}
                cand = get_or_create_candidate(
                    file_path=k.file_path,
                    line_number=meta.get("start_line", 1),
                    line_end=meta.get("end_line"),
                    symbol_name=k.symbol_name,
                    symbol_type=k.symbol_type,
                    snippet=meta.get("signature") or (k.content[:300] if k.content else (k.symbol_name or "")),
                )
                semantic_items.append((sim, cand))

        semantic_items.sort(key=lambda x: x[0], reverse=True)
        seen_sem_keys = set()
        sem_rank = 1
        for sim, cand in semantic_items:
            s_key = (cand["file_path"], cand["line_number"], cand["symbol_name"])
            if s_key not in seen_sem_keys:
                seen_sem_keys.add(s_key)
                cand["semantic_score"] = max(cand["semantic_score"], round(sim, 4))
                cand["r_sem"] = sem_rank
                sem_rank += 1

        # -------------------------------------------------------------
        # 3. STRUCTURAL RETRIEVAL
        # -------------------------------------------------------------
        # Query incoming and outgoing edges for centrality
        e_stmt = select(RepositoryGraphEdge).where(RepositoryGraphEdge.repository_id == repo.id)
        e_res = await db.execute(e_stmt)
        all_edges = e_res.scalars().all()

        node_in_degree: Dict[uuid.UUID, int] = {}
        node_out_degree: Dict[uuid.UUID, int] = {}
        for edge in all_edges:
            if edge.target_node_id:
                node_in_degree[edge.target_node_id] = node_in_degree.get(edge.target_node_id, 0) + 1
            node_out_degree[edge.source_node_id] = node_out_degree.get(edge.source_node_id, 0) + 1

        structural_items: List[Tuple[float, Dict[str, Any]]] = []
        for node in all_nodes:
            if not node.file_path:
                continue
            in_deg = node_in_degree.get(node.id, 0)
            out_deg = node_out_degree.get(node.id, 0)
            centrality = min(1.0, (in_deg * 2.0 + out_deg) / 15.0)

            # Check if query matches node or its file path
            relevance_boost = 0.0
            if node.name and (node.name.lower() in q_lower or q_lower in node.name.lower()):
                relevance_boost = 0.5
            elif any(tok in (node.name or "").lower() for tok in q_tokens):
                relevance_boost = 0.3
            elif any(tok in node.file_path.lower() for tok in q_tokens):
                relevance_boost = 0.2

            struct_score = round(0.5 * centrality + relevance_boost, 4)
            if struct_score > 0.15:
                cand = get_or_create_candidate(
                    file_path=node.file_path,
                    line_number=node.start_line or 1,
                    line_end=node.end_line,
                    symbol_name=node.name if node.node_type not in ("FILE", "DIRECTORY", "PACKAGE") else None,
                    symbol_type=node.node_type.lower(),
                    language=node.language,
                    package_name=(node.meta_info or {}).get("package_name"),
                    snippet=(node.meta_info or {}).get("signature") or node.name,
                )
                structural_items.append((struct_score, cand))

        structural_items.sort(key=lambda x: x[0], reverse=True)
        seen_struct_keys = set()
        struct_rank = 1
        for score, cand in structural_items:
            st_key = (cand["file_path"], cand["line_number"], cand["symbol_name"])
            if st_key not in seen_struct_keys:
                seen_struct_keys.add(st_key)
                cand["structural_score"] = max(cand["structural_score"], round(score, 4))
                cand["r_struct"] = struct_rank
                struct_rank += 1

        # -------------------------------------------------------------
        # 4. FILTERING & RECIPROCAL RANK FUSION (RRF)
        # -------------------------------------------------------------
        k_const = 60.0
        ranked_candidates: List[HybridSearchResultItem] = []

        for cand in candidates.values():
            # Apply language filter
            if filters and filters.languages:
                lang = (cand["language"] or "").lower()
                allowed_langs = [l.lower() for l in filters.languages]
                if not any(al in lang or lang in al for al in allowed_langs):
                    continue

            # Apply package filter
            if filters and filters.packages:
                pkg = (cand["package_name"] or "").lower()
                allowed_pkgs = [p.lower() for p in filters.packages]
                if not any(ap in pkg for ap in allowed_pkgs):
                    # Also check if file_path starts with package name or package path
                    if not any(ap in cand["file_path"].lower() for ap in allowed_pkgs):
                        continue

            # Apply file_paths filter
            if filters and filters.file_paths:
                fpath = cand["file_path"]
                matches_path = False
                for p_filter in filters.file_paths:
                    if fnmatch.fnmatch(fpath, p_filter) or fpath.startswith(p_filter) or p_filter in fpath:
                        matches_path = True
                        break
                if not matches_path:
                    continue

            # Apply symbol_types filter
            if filters and filters.symbol_types:
                stype = (cand["symbol_type"] or "").lower()
                allowed_types = [t.lower() for t in filters.symbol_types]
                if stype not in allowed_types:
                    continue

            # Calculate RRF score
            rrf_lex = (w_lex / (k_const + cand["r_lex"])) if cand["r_lex"] is not None else 0.0
            rrf_sem = (w_sem / (k_const + cand["r_sem"])) if cand["r_sem"] is not None else 0.0
            rrf_struct = (w_struct / (k_const + cand["r_struct"])) if cand["r_struct"] is not None else 0.0

            rrf_sum = rrf_lex + rrf_sem + rrf_struct
            combined_score = min(1.0, round(rrf_sum * (k_const + 1.0), 4))

            # Build explainable provenance
            prov_parts = []
            if cand["r_lex"] is not None:
                prov_parts.append(f"Lexical match (rank #{cand['r_lex']}, score {cand['lexical_score']})")
            if cand["r_sem"] is not None:
                prov_parts.append(f"Semantic similarity (rank #{cand['r_sem']}, score {cand['semantic_score']})")
            if cand["r_struct"] is not None:
                prov_parts.append(f"Structural centrality (rank #{cand['r_struct']}, score {cand['structural_score']})")

            prov_explanation = "; ".join(prov_parts) if prov_parts else "Retrieved via repository index"

            # Scrub secrets in code snippet
            clean_snippet = scrub_credentials(cand["snippet"] or cand["symbol_name"] or cand["file_path"])

            item = HybridSearchResultItem(
                file_path=cand["file_path"],
                line_number=cand["line_number"],
                line_end=cand["line_end"],
                symbol_name=cand["symbol_name"],
                symbol_type=cand["symbol_type"],
                package_name=cand["package_name"],
                language=cand["language"],
                snippet=clean_snippet,
                lexical_score=cand["lexical_score"],
                semantic_score=cand["semantic_score"],
                structural_score=cand["structural_score"],
                combined_score=combined_score,
                rank=1,  # will be assigned below
                provenance_explanation=prov_explanation,
            )
            ranked_candidates.append(item)

        # Sort all candidates by combined_score descending
        ranked_candidates.sort(key=lambda x: x.combined_score, reverse=True)

        for idx, item in enumerate(ranked_candidates, start=1):
            item.rank = idx

        total_matches = len(ranked_candidates)
        paginated_results = ranked_candidates[offset : offset + limit]
        duration = round(time.time() - start_time, 4)

        return HybridSearchResponse(
            repository_id=str(repo.id),
            query=q,
            total_matches=total_matches,
            limit=limit,
            offset=offset,
            results=paginated_results,
            search_duration_seconds=duration,
        )
