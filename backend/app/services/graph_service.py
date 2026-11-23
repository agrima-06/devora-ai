"""Repository Graph Service: coordinates graph indexing, cross-file resolution, and bounded queries."""
import hashlib
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.user import User
from app.schemas.graph import (
    GraphDependenciesResponse,
    GraphEdgeItem,
    GraphIndexingResponse,
    GraphNodeDetailResponse,
    GraphNodeItem,
    GraphNodesListResponse,
    GraphUnresolvedReferencesResponse,
    RepositoryGraphSummaryResponse,
    UnresolvedReferenceItem,
)
from app.services.graph_builder import (
    GraphExtractor,
    RawImport,
    RawSymbol,
    resolve_js_ts_module_path,
    resolve_python_module_path,
)
from app.services.scanner_service import RepositoryScanner

logger = get_logger("graph_service")


class RepositoryGraphService:
    """Manages persistence, cross-file resolution, and query operations for repository dependency graphs."""

    def __init__(
        self,
        scanner: Optional[RepositoryScanner] = None,
        extractor: Optional[GraphExtractor] = None,
    ):
        self.scanner = scanner or RepositoryScanner()
        self.extractor = extractor or GraphExtractor()

    async def get_repository_for_user(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Repository:
        """Fetch and enforce tenant isolation on repository access."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
        res = await db.execute(stmt)
        repo = res.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)
        return repo

    async def index_repository_graph(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        workspace_path: Path,
        commit_sha: Optional[str] = None,
        force_reindex: bool = False,
    ) -> GraphIndexingResponse:
        """Build or incrementally update the cross-file symbol and dependency graph."""
        start_time = time.time()
        repo = await self.get_repository_for_user(repository_id, user.id, db)
        current_sha = commit_sha or repo.current_commit_sha or "HEAD"

        if not workspace_path.exists() or not workspace_path.is_dir():
            raise NotFoundException(f"Workspace directory does not exist: {workspace_path}")

        # 1. Scan workspace files
        scan_result = self.scanner.scan(workspace_path)
        scanned_files = scan_result.get("files", [])
        total_files = len(scanned_files)

        all_file_paths = {f["file_path"] for f in scanned_files}

        # 2. Check existing indexed file hashes if incremental
        existing_file_nodes_stmt = select(
            RepositoryGraphNode.file_path,
            RepositoryGraphNode.content_hash,
            RepositoryGraphNode.id,
        ).where(
            RepositoryGraphNode.repository_id == repo.id,
            RepositoryGraphNode.node_type == "FILE",
        )
        existing_res = await db.execute(existing_file_nodes_stmt)
        existing_file_map = {r[0]: (r[1], r[2]) for r in existing_res.all()}

        files_to_index: List[Dict[str, Any]] = []
        files_skipped = 0

        for file_info in scanned_files:
            rel_path = file_info["file_path"]
            full_path = workspace_path / rel_path
            try:
                content_bytes = full_path.read_bytes()
                c_hash = hashlib.sha256(content_bytes).hexdigest()
            except Exception:
                c_hash = ""

            file_info["content_hash"] = c_hash

            if not force_reindex and rel_path in existing_file_map:
                old_hash, _ = existing_file_map[rel_path]
                if old_hash and old_hash == c_hash:
                    files_skipped += 1
                    continue

            files_to_index.append(file_info)

        # If full reindex requested or no existing nodes, clean slate for clean consistency
        if force_reindex or len(existing_file_map) == 0:
            await db.execute(delete(RepositoryGraphEdge).where(RepositoryGraphEdge.repository_id == repo.id))
            await db.execute(delete(RepositoryGraphNode).where(RepositoryGraphNode.repository_id == repo.id))
            await db.flush()
            files_to_index = scanned_files
            files_skipped = 0
        elif not force_reindex and len(existing_file_map) > 0 and len(files_to_index) == 0:
            # All files skipped, return early
            duration = round(time.time() - start_time, 2)
            return GraphIndexingResponse(
                repository_id=str(repo.id),
                status="INDEXED",
                commit_sha=current_sha,
                total_files=total_files,
                files_indexed=0,
                files_skipped=files_skipped,
                nodes_created=0,
                edges_created=0,
                unresolved_references=0,
                duration_seconds=duration,
                message=f"All {files_skipped} files unchanged; graph is already up to date.",
            )
        elif files_to_index:
            # Incremental: delete nodes and edges originating from files about to be re-indexed
            paths_to_clear = [f["file_path"] for f in files_to_index]
            cleared_nodes_stmt = select(RepositoryGraphNode.id).where(
                RepositoryGraphNode.repository_id == repo.id,
                RepositoryGraphNode.file_path.in_(paths_to_clear),
            )
            cleared_ids = (await db.execute(cleared_nodes_stmt)).scalars().all()
            if cleared_ids:
                await db.execute(
                    delete(RepositoryGraphEdge).where(
                        RepositoryGraphEdge.repository_id == repo.id,
                        or_(
                            RepositoryGraphEdge.source_node_id.in_(cleared_ids),
                            RepositoryGraphEdge.target_node_id.in_(cleared_ids),
                        ),
                    )
                )
                await db.execute(
                    delete(RepositoryGraphNode).where(
                        RepositoryGraphNode.id.in_(cleared_ids),
                    )
                )
                await db.flush()

        # 3. Create Root REPOSITORY node if not present
        nodes_created_count = 0
        root_node_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repo.id,
            RepositoryGraphNode.node_type == "REPOSITORY",
        )
        root_node = (await db.execute(root_node_stmt)).scalar_one_or_none()
        if not root_node:
            root_node = RepositoryGraphNode(
                repository_id=repo.id,
                node_type="REPOSITORY",
                qualified_name=".",
                name=repo.name,
                file_path=None,
                language=repo.language,
                meta_info={"full_name": repo.full_name, "default_branch": repo.default_branch},
            )
            db.add(root_node)
            nodes_created_count += 1
            await db.flush()

        # 4. Extract symbols, imports, and calls from files_to_index
        all_raw_symbols: List[RawSymbol] = []
        all_raw_imports: List[RawImport] = []
        file_node_map: Dict[str, RepositoryGraphNode] = {}
        dir_node_map: Dict[str, RepositoryGraphNode] = {}
        symbol_node_map: Dict[str, RepositoryGraphNode] = {}

        # Pre-load existing directory, file, and symbol nodes into maps
        existing_dir_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repo.id,
            RepositoryGraphNode.node_type == "DIRECTORY",
        )
        existing_dirs = (await db.execute(existing_dir_stmt)).scalars().all()
        for ed in existing_dirs:
            if ed.file_path:
                dir_node_map[ed.file_path] = ed

        existing_file_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repo.id,
            RepositoryGraphNode.node_type == "FILE",
        )
        existing_files = (await db.execute(existing_file_stmt)).scalars().all()
        for ef in existing_files:
            if ef.file_path:
                file_node_map[ef.file_path] = ef

        existing_sym_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repo.id,
            RepositoryGraphNode.node_type.in_(["CLASS", "INTERFACE", "FUNCTION", "METHOD", "CONSTANT"]),
        )
        existing_syms = (await db.execute(existing_sym_stmt)).scalars().all()
        for es in existing_syms:
            symbol_node_map[es.qualified_name] = es

        # Pre-populate directory nodes
        directories_created = set()
        for file_info in scanned_files:
            rel_path = file_info["file_path"]
            parts = Path(rel_path).parent.parts
            cur_dir = ""
            for part in parts:
                cur_dir = f"{cur_dir}/{part}" if cur_dir else part
                directories_created.add(cur_dir)

        for dir_path in sorted(directories_created):
            if dir_path not in dir_node_map:
                dir_node = RepositoryGraphNode(
                    repository_id=repo.id,
                    node_type="DIRECTORY",
                    qualified_name=f"dir:{dir_path}",
                    name=os.path.basename(dir_path),
                    file_path=dir_path,
                    meta_info={"is_directory": True},
                )
                db.add(dir_node)
                dir_node_map[dir_path] = dir_node
                nodes_created_count += 1

        await db.flush()

        # 5. Create FILE nodes and extract code entities

        for file_info in files_to_index:
            rel_path = file_info["file_path"]
            lang = file_info.get("language")
            full_path = workspace_path / rel_path

            try:
                content_bytes = full_path.read_bytes()
                content_str = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                content_bytes = b""
                content_str = ""

            file_node = RepositoryGraphNode(
                repository_id=repo.id,
                node_type="FILE",
                qualified_name=rel_path,
                name=os.path.basename(rel_path),
                file_path=rel_path,
                language=lang,
                start_line=1,
                end_line=file_info.get("lines_count", 1),
                content_hash=file_info.get("content_hash"),
                meta_info={
                    "size_bytes": file_info.get("size_bytes", 0),
                    "lines_count": file_info.get("lines_count", 0),
                    "commit_sha": current_sha,
                },
            )
            db.add(file_node)
            file_node_map[rel_path] = file_node
            nodes_created_count += 1

            # Parse language content
            if lang == "Python":
                syms, imps, calls, valid, err = self.extractor.parse_python(content_str, rel_path)
                all_raw_symbols.extend(syms)
                all_raw_imports.extend(imps)
            elif lang in {"JavaScript", "TypeScript", "TypeScript (React)", "Go", "Java"}:
                syms, imps, calls, valid, err = self.extractor.parse_treesitter_generic(content_bytes, lang, rel_path)
                all_raw_symbols.extend(syms)
                all_raw_imports.extend(imps)

        await db.flush()

        # Edge uniqueness tracking
        added_edge_keys: Set[Tuple[uuid.UUID, Optional[uuid.UUID], str, Optional[str]]] = set()
        existing_edges_stmt = select(
            RepositoryGraphEdge.source_node_id,
            RepositoryGraphEdge.target_node_id,
            RepositoryGraphEdge.edge_type,
            RepositoryGraphEdge.target_symbol,
        ).where(RepositoryGraphEdge.repository_id == repo.id)
        existing_edges = (await db.execute(existing_edges_stmt)).all()
        for ee in existing_edges:
            added_edge_keys.add((ee[0], ee[1], ee[2], ee[3]))

        edges_created_count = 0

        def add_edge_if_unique(edge: RepositoryGraphEdge) -> bool:
            nonlocal edges_created_count
            key = (edge.source_node_id, edge.target_node_id, edge.edge_type, edge.target_symbol)
            if key not in added_edge_keys:
                added_edge_keys.add(key)
                db.add(edge)
                edges_created_count += 1
                return True
            return False

        # Connect DIRECTORY -> FILE with CONTAINS edges
        for rel_path, file_node in file_node_map.items():
            parent_dir = str(Path(rel_path).parent)
            parent_node = dir_node_map.get(parent_dir) or root_node
            add_edge_if_unique(
                RepositoryGraphEdge(
                    repository_id=repo.id,
                    source_node_id=parent_node.id,
                    target_node_id=file_node.id,
                    edge_type="CONTAINS",
                    confidence=1.0,
                    resolution_status="RESOLVED",
                    meta_info={"structural": True},
                )
            )

        # 6. Insert Symbol Nodes (Classes, Functions, Methods, Constants)
        for sym in all_raw_symbols:
            sym_node = RepositoryGraphNode(
                repository_id=repo.id,
                node_type=sym.node_type,
                qualified_name=sym.qualified_name,
                name=sym.name,
                file_path=sym.file_path,
                language=sym.language,
                start_line=sym.start_line,
                end_line=sym.end_line,
                meta_info=sym.metadata,
            )
            db.add(sym_node)
            symbol_node_map[sym.qualified_name] = sym_node
            nodes_created_count += 1

        await db.flush()

        # Connect FILE / CLASS -> SYMBOL with DEFINES edges
        for sym in all_raw_symbols:
            sym_node = symbol_node_map.get(sym.qualified_name)
            if not sym_node:
                continue

            if sym.parent_name:
                parent_qname = f"{sym.file_path}:{sym.parent_name}"
                parent_node = symbol_node_map.get(parent_qname) or file_node_map.get(sym.file_path)
            else:
                parent_node = file_node_map.get(sym.file_path)

            if parent_node:
                add_edge_if_unique(
                    RepositoryGraphEdge(
                        repository_id=repo.id,
                        source_node_id=parent_node.id,
                        target_node_id=sym_node.id,
                        edge_type="DEFINES",
                        confidence=1.0,
                        resolution_status="RESOLVED",
                        meta_info={"symbol_type": sym.node_type},
                    )
                )

        # 7. Pass 2: Cross-File Import & Dependency Resolution
        unresolved_count = 0
        file_dependencies: Set[Tuple[uuid.UUID, uuid.UUID]] = set()

        for imp in all_raw_imports:
            src_file_node = file_node_map.get(imp.file_path)
            if not src_file_node:
                continue

            lang = src_file_node.language or "Python"
            if lang == "Python":
                target_file_path, res_status = resolve_python_module_path(
                    source_file_path=imp.file_path,
                    raw_import=imp,
                    all_file_paths=all_file_paths,
                )
            else:
                target_file_path, res_status = resolve_js_ts_module_path(
                    source_file_path=imp.file_path,
                    raw_import=imp,
                    all_file_paths=all_file_paths,
                )

            if res_status == "RESOLVED" and target_file_path:
                target_file_node = file_node_map.get(target_file_path)
                if target_file_node:
                    # Link file-level IMPORTS edge
                    add_edge_if_unique(
                        RepositoryGraphEdge(
                            repository_id=repo.id,
                            source_node_id=src_file_node.id,
                            target_node_id=target_file_node.id,
                            edge_type="IMPORTS",
                            confidence=1.0,
                            resolution_status="RESOLVED",
                            target_symbol=imp.module_str,
                            meta_info={"line": imp.line_number, "raw": imp.raw_statement},
                        )
                    )
                    file_dependencies.add((src_file_node.id, target_file_node.id))

                    # If specific symbols were imported, link to them as well
                    for sym_name in imp.imported_symbols:
                        target_sym_qname = f"{target_file_path}:{sym_name}"
                        target_sym_node = symbol_node_map.get(target_sym_qname)
                        if target_sym_node:
                            add_edge_if_unique(
                                RepositoryGraphEdge(
                                    repository_id=repo.id,
                                    source_node_id=src_file_node.id,
                                    target_node_id=target_sym_node.id,
                                    edge_type="REFERENCES",
                                    confidence=1.0,
                                    resolution_status="RESOLVED",
                                    target_symbol=sym_name,
                                    meta_info={"line": imp.line_number},
                                )
                            )

            elif res_status == "EXTERNAL":
                # Third-party or stdlib package
                add_edge_if_unique(
                    RepositoryGraphEdge(
                        repository_id=repo.id,
                        source_node_id=src_file_node.id,
                        target_node_id=None,
                        edge_type="IMPORTS",
                        confidence=1.0,
                        resolution_status="EXTERNAL",
                        target_symbol=imp.module_str,
                        meta_info={"line": imp.line_number, "raw": imp.raw_statement},
                    )
                )

            else:
                # UNRESOLVED
                unresolved_count += 1
                add_edge_if_unique(
                    RepositoryGraphEdge(
                        repository_id=repo.id,
                        source_node_id=src_file_node.id,
                        target_node_id=None,
                        edge_type="IMPORTS",
                        confidence=0.0,
                        resolution_status="UNRESOLVED",
                        target_symbol=imp.module_str or imp.raw_statement,
                        meta_info={"line": imp.line_number, "raw": imp.raw_statement},
                    )
                )

        # 8. Add high-level DEPENDS_ON edges between files
        for src_id, tgt_id in file_dependencies:
            if src_id != tgt_id:
                add_edge_if_unique(
                    RepositoryGraphEdge(
                        repository_id=repo.id,
                        source_node_id=src_id,
                        target_node_id=tgt_id,
                        edge_type="DEPENDS_ON",
                        confidence=1.0,
                        resolution_status="RESOLVED",
                        meta_info={"module_dependency": True},
                    )
                )

        # 9. Resolve Class INHERITS edges
        for sym in all_raw_symbols:
            if sym.node_type == "CLASS":
                class_node = symbol_node_map.get(sym.qualified_name)
                bases = sym.metadata.get("bases", [])
                for base in bases:
                    base_clean = base.split(".")[-1]
                    same_file_qname = f"{sym.file_path}:{base_clean}"
                    target_base_node = symbol_node_map.get(same_file_qname)

                    if target_base_node and class_node:
                        add_edge_if_unique(
                            RepositoryGraphEdge(
                                repository_id=repo.id,
                                source_node_id=class_node.id,
                                target_node_id=target_base_node.id,
                                edge_type="INHERITS",
                                confidence=1.0,
                                resolution_status="RESOLVED",
                                target_symbol=base,
                                meta_info={"base_class": base},
                            )
                        )
                    elif class_node:
                        add_edge_if_unique(
                            RepositoryGraphEdge(
                                repository_id=repo.id,
                                source_node_id=class_node.id,
                                target_node_id=None,
                                edge_type="INHERITS",
                                confidence=0.8,
                                resolution_status="EXTERNAL" if base in {"BaseModel", "object", "Base", "TestCase"} else "UNRESOLVED",
                                target_symbol=base,
                                meta_info={"base_class": base},
                            )
                        )

        # 10. Update repository indexing state
        repo.indexing_status = "INDEXED"
        repo.last_indexed_at = datetime.now(timezone.utc)
        repo.current_commit_sha = current_sha
        await db.commit()

        duration = round(time.time() - start_time, 2)
        logger.info(
            "repository_graph_indexed",
            repo_id=str(repo.id),
            nodes_created=nodes_created_count,
            edges_created=edges_created_count,
            unresolved=unresolved_count,
            duration=duration,
        )

        return GraphIndexingResponse(
            repository_id=str(repo.id),
            status="INDEXED",
            commit_sha=current_sha,
            total_files=total_files,
            files_indexed=len(files_to_index),
            files_skipped=files_skipped,
            nodes_created=nodes_created_count,
            edges_created=edges_created_count,
            unresolved_references=unresolved_count,
            duration_seconds=duration,
            message=f"Indexed {len(files_to_index)} files ({files_skipped} skipped), created {nodes_created_count} nodes and {edges_created_count} relationships in {duration}s",
        )

    async def get_summary(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> RepositoryGraphSummaryResponse:
        """Compute aggregate graph metrics, node/edge type breakdowns, and resolution counters."""
        repo = await self.get_repository_for_user(repository_id, user_id, db)

        # Node counts and breakdown
        node_stmt = (
            select(
                RepositoryGraphNode.node_type,
                func.count(RepositoryGraphNode.id),
            )
            .where(RepositoryGraphNode.repository_id == repo.id)
            .group_by(RepositoryGraphNode.node_type)
        )
        node_rows = (await db.execute(node_stmt)).all()
        node_types_breakdown = {r[0]: r[1] for r in node_rows}
        total_nodes = sum(node_types_breakdown.values())

        # Languages breakdown
        lang_stmt = (
            select(
                RepositoryGraphNode.language,
                func.count(RepositoryGraphNode.id),
            )
            .where(
                RepositoryGraphNode.repository_id == repo.id,
                RepositoryGraphNode.language.is_not(None),
            )
            .group_by(RepositoryGraphNode.language)
        )
        lang_rows = (await db.execute(lang_stmt)).all()
        languages_breakdown = {r[0]: r[1] for r in lang_rows if r[0]}

        # Edge counts and breakdown
        edge_stmt = (
            select(
                RepositoryGraphEdge.edge_type,
                func.count(RepositoryGraphEdge.id),
            )
            .where(RepositoryGraphEdge.repository_id == repo.id)
            .group_by(RepositoryGraphEdge.edge_type)
        )
        edge_rows = (await db.execute(edge_stmt)).all()
        edge_types_breakdown = {r[0]: r[1] for r in edge_rows}
        total_edges = sum(edge_types_breakdown.values())

        # Unresolved & external counts
        res_stmt = (
            select(
                RepositoryGraphEdge.resolution_status,
                func.count(RepositoryGraphEdge.id),
            )
            .where(RepositoryGraphEdge.repository_id == repo.id)
            .group_by(RepositoryGraphEdge.resolution_status)
        )
        res_rows = (await db.execute(res_stmt)).all()
        res_counts = {r[0]: r[1] for r in res_rows}

        return RepositoryGraphSummaryResponse(
            repository_id=str(repo.id),
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_types_breakdown=node_types_breakdown,
            edge_types_breakdown=edge_types_breakdown,
            languages_breakdown=languages_breakdown,
            unresolved_count=res_counts.get("UNRESOLVED", 0),
            external_count=res_counts.get("EXTERNAL", 0),
            last_indexed_at=repo.last_indexed_at,
            current_commit_sha=repo.current_commit_sha,
            indexing_status=repo.indexing_status,
        )

    async def get_nodes(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
        node_type: Optional[str] = None,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> GraphNodesListResponse:
        """Query paginated graph nodes with optional filtering."""
        repo = await self.get_repository_for_user(repository_id, user_id, db)

        conditions = [RepositoryGraphNode.repository_id == repo.id]
        if node_type:
            conditions.append(RepositoryGraphNode.node_type == node_type.upper())
        if language:
            conditions.append(RepositoryGraphNode.language == language)
        if file_path:
            conditions.append(RepositoryGraphNode.file_path == file_path)
        if search_query:
            conditions.append(
                or_(
                    RepositoryGraphNode.name.ilike(f"%{search_query}%"),
                    RepositoryGraphNode.qualified_name.ilike(f"%{search_query}%"),
                )
            )

        # Count total
        count_stmt = select(func.count(RepositoryGraphNode.id)).where(*conditions)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Query items
        items_stmt = (
            select(RepositoryGraphNode)
            .where(*conditions)
            .order_by(RepositoryGraphNode.node_type, RepositoryGraphNode.name)
            .limit(limit)
            .offset(offset)
        )
        nodes = (await db.execute(items_stmt)).scalars().all()

        node_items = [
            GraphNodeItem(
                id=str(n.id),
                repository_id=str(n.repository_id),
                node_type=n.node_type,
                qualified_name=n.qualified_name,
                name=n.name,
                file_path=n.file_path,
                language=n.language,
                start_line=n.start_line,
                end_line=n.end_line,
                metadata=n.meta_info or {},
                content_hash=n.content_hash,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in nodes
        ]

        return GraphNodesListResponse(
            total=total,
            limit=limit,
            offset=offset,
            nodes=node_items,
        )

    async def get_node_detail(
        self,
        repository_id: uuid.UUID,
        node_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> GraphNodeDetailResponse:
        """Fetch node details along with its direct incoming and outgoing relationships."""
        repo = await self.get_repository_for_user(repository_id, user_id, db)

        stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.id == node_id,
            RepositoryGraphNode.repository_id == repo.id,
        )
        node = (await db.execute(stmt)).scalar_one_or_none()
        if not node:
            raise NotFoundException("RepositoryGraphNode", node_id)

        # Incoming edges
        in_stmt = select(RepositoryGraphEdge).where(
            RepositoryGraphEdge.target_node_id == node.id,
            RepositoryGraphEdge.repository_id == repo.id,
        )
        in_edges = (await db.execute(in_stmt)).scalars().all()

        # Outgoing edges
        out_stmt = select(RepositoryGraphEdge).where(
            RepositoryGraphEdge.source_node_id == node.id,
            RepositoryGraphEdge.repository_id == repo.id,
        )
        out_edges = (await db.execute(out_stmt)).scalars().all()

        # Collect peer node IDs
        peer_ids = {e.source_node_id for e in in_edges} | {e.target_node_id for e in out_edges if e.target_node_id}
        related_nodes: Dict[str, GraphNodeItem] = {}
        if peer_ids:
            peers_stmt = select(RepositoryGraphNode).where(RepositoryGraphNode.id.in_(peer_ids))
            peers = (await db.execute(peers_stmt)).scalars().all()
            for p in peers:
                related_nodes[str(p.id)] = GraphNodeItem(
                    id=str(p.id),
                    repository_id=str(p.repository_id),
                    node_type=p.node_type,
                    qualified_name=p.qualified_name,
                    name=p.name,
                    file_path=p.file_path,
                    language=p.language,
                    start_line=p.start_line,
                    end_line=p.end_line,
                    metadata=p.meta_info or {},
                    content_hash=p.content_hash,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )

        node_item = GraphNodeItem(
            id=str(node.id),
            repository_id=str(node.repository_id),
            node_type=node.node_type,
            qualified_name=node.qualified_name,
            name=node.name,
            file_path=node.file_path,
            language=node.language,
            start_line=node.start_line,
            end_line=node.end_line,
            metadata=node.meta_info or {},
            content_hash=node.content_hash,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

        in_items = [
            GraphEdgeItem(
                id=str(e.id),
                repository_id=str(e.repository_id),
                source_node_id=str(e.source_node_id),
                target_node_id=str(e.target_node_id) if e.target_node_id else None,
                edge_type=e.edge_type,
                confidence=e.confidence,
                resolution_status=e.resolution_status,
                target_symbol=e.target_symbol,
                metadata=e.meta_info or {},
                created_at=e.created_at,
            )
            for e in in_edges
        ]

        out_items = [
            GraphEdgeItem(
                id=str(e.id),
                repository_id=str(e.repository_id),
                source_node_id=str(e.source_node_id),
                target_node_id=str(e.target_node_id) if e.target_node_id else None,
                edge_type=e.edge_type,
                confidence=e.confidence,
                resolution_status=e.resolution_status,
                target_symbol=e.target_symbol,
                metadata=e.meta_info or {},
                created_at=e.created_at,
            )
            for e in out_edges
        ]

        return GraphNodeDetailResponse(
            node=node_item,
            incoming_edges=in_items,
            outgoing_edges=out_items,
            related_nodes=related_nodes,
        )

    async def get_dependencies(
        self,
        repository_id: uuid.UUID,
        root_node_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
        direction: str = "outgoing",
        max_depth: int = 2,
        edge_type: Optional[str] = None,
        limit: int = 100,
    ) -> GraphDependenciesResponse:
        """Bounded breadth-first search traversing the dependency subgraph from a root node."""
        repo = await self.get_repository_for_user(repository_id, user_id, db)
        bounded_depth = max(1, min(max_depth, 5))

        # Check root node exists
        root_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.id == root_node_id,
            RepositoryGraphNode.repository_id == repo.id,
        )
        root = (await db.execute(root_stmt)).scalar_one_or_none()
        if not root:
            raise NotFoundException("RepositoryGraphNode", root_node_id)

        visited_node_ids: Set[uuid.UUID] = {root.id}
        discovered_edges: List[RepositoryGraphEdge] = []
        queue: deque[Tuple[uuid.UUID, int]] = deque([(root.id, 0)])

        while queue and len(visited_node_ids) < limit:
            current_id, depth = queue.popleft()
            if depth >= bounded_depth:
                continue

            # Query outgoing edges
            if direction in ("outgoing", "both"):
                out_conditions = [
                    RepositoryGraphEdge.repository_id == repo.id,
                    RepositoryGraphEdge.source_node_id == current_id,
                ]
                if edge_type:
                    out_conditions.append(RepositoryGraphEdge.edge_type == edge_type.upper())

                out_stmt = select(RepositoryGraphEdge).where(*out_conditions)
                out_edges = (await db.execute(out_stmt)).scalars().all()
                for e in out_edges:
                    discovered_edges.append(e)
                    if e.target_node_id and e.target_node_id not in visited_node_ids:
                        visited_node_ids.add(e.target_node_id)
                        queue.append((e.target_node_id, depth + 1))

            # Query incoming edges
            if direction in ("incoming", "both"):
                in_conditions = [
                    RepositoryGraphEdge.repository_id == repo.id,
                    RepositoryGraphEdge.target_node_id == current_id,
                ]
                if edge_type:
                    in_conditions.append(RepositoryGraphEdge.edge_type == edge_type.upper())

                in_stmt = select(RepositoryGraphEdge).where(*in_conditions)
                in_edges = (await db.execute(in_stmt)).scalars().all()
                for e in in_edges:
                    discovered_edges.append(e)
                    if e.source_node_id and e.source_node_id not in visited_node_ids:
                        visited_node_ids.add(e.source_node_id)
                        queue.append((e.source_node_id, depth + 1))

        # Fetch full node records for all visited IDs
        nodes_stmt = select(RepositoryGraphNode).where(RepositoryGraphNode.id.in_(visited_node_ids))
        nodes = (await db.execute(nodes_stmt)).scalars().all()

        node_items = [
            GraphNodeItem(
                id=str(n.id),
                repository_id=str(n.repository_id),
                node_type=n.node_type,
                qualified_name=n.qualified_name,
                name=n.name,
                file_path=n.file_path,
                language=n.language,
                start_line=n.start_line,
                end_line=n.end_line,
                metadata=n.meta_info or {},
                content_hash=n.content_hash,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in nodes
        ]

        # De-duplicate edges
        seen_edges = set()
        edge_items = []
        for e in discovered_edges:
            if e.id not in seen_edges:
                seen_edges.add(e.id)
                edge_items.append(
                    GraphEdgeItem(
                        id=str(e.id),
                        repository_id=str(e.repository_id),
                        source_node_id=str(e.source_node_id),
                        target_node_id=str(e.target_node_id) if e.target_node_id else None,
                        edge_type=e.edge_type,
                        confidence=e.confidence,
                        resolution_status=e.resolution_status,
                        target_symbol=e.target_symbol,
                        metadata=e.meta_info or {},
                        created_at=e.created_at,
                    )
                )

        return GraphDependenciesResponse(
            root_node_id=str(root.id),
            direction=direction,
            max_depth=bounded_depth,
            nodes=node_items,
            edges=edge_items,
        )

    async def get_unresolved_references(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> GraphUnresolvedReferencesResponse:
        """Fetch unresolved cross-file dependencies and external imports for diagnostic inspection."""
        repo = await self.get_repository_for_user(repository_id, user_id, db)

        conditions = [
            RepositoryGraphEdge.repository_id == repo.id,
            RepositoryGraphEdge.resolution_status.in_(["UNRESOLVED", "AMBIGUOUS"]),
        ]

        # Count total
        count_stmt = select(func.count(RepositoryGraphEdge.id)).where(*conditions)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Query edges with source node join
        query_stmt = (
            select(
                RepositoryGraphEdge,
                RepositoryGraphNode.file_path,
                RepositoryGraphNode.name,
            )
            .join(RepositoryGraphNode, RepositoryGraphEdge.source_node_id == RepositoryGraphNode.id)
            .where(*conditions)
            .order_by(RepositoryGraphEdge.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await db.execute(query_stmt)).all()

        unresolved_items = []
        for edge, src_file, src_name in rows:
            meta = edge.meta_info or {}
            unresolved_items.append(
                UnresolvedReferenceItem(
                    edge_id=str(edge.id),
                    source_file=src_file or "unknown",
                    source_symbol=src_name or "unknown",
                    target_symbol=edge.target_symbol or "unknown",
                    edge_type=edge.edge_type,
                    resolution_status=edge.resolution_status,
                    line_number=meta.get("line"),
                )
            )

        return GraphUnresolvedReferencesResponse(
            total=total,
            limit=limit,
            offset=offset,
            unresolved=unresolved_items,
        )
