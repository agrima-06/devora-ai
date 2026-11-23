"""Blast Radius and Change Impact Analysis Engine.

Performs reverse dependency traversal over the persistent repository graph,
reconstructs explainable dependency paths, calculates deterministic impact scores,
and correlates test recommendations with test framework discovery.
"""
import math
import os
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, UnauthorizedException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.user import User
from app.schemas.impact import (
    DependencyHop,
    DependencyPathItem,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    ImpactScoreBreakdown,
    ImpactSummaryMetrics,
    ImpactTarget,
    ImpactedNodeItem,
    RecommendedTestItem,
    UnresolvedWarningItem,
)
from app.services.test_discovery_service import TestDiscoveryService

logger = get_logger("impact_analysis_service")

# Edge types that carry consumer impact semantics when traversed in REVERSE
VALID_CONSUMER_EDGE_TYPES: Set[str] = {
    "IMPORTS",
    "DEPENDS_ON",
    "CALLS",
    "INHERITS",
    "IMPLEMENTS",
    "REFERENCES",
}

# Regex / naming patterns for test files
TEST_FILE_INDICATORS = (
    "/test_",
    "/tests/",
    "_test.",
    ".test.",
    ".spec.",
    "Test.java",
    "TestCase.java",
)


class ImpactAnalysisService:
    """Core engine for computing change impact, dependency blast radius, and test recommendations."""

    def __init__(self):
        self.test_discovery = TestDiscoveryService()

    async def get_repository_for_user(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Repository:
        """Fetch repository ensuring tenant isolation and ownership."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
        repo = (await db.execute(stmt)).scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)
        return repo

    async def analyze_impact(
        self,
        repository_id: uuid.UUID,
        request: ImpactAnalysisRequest,
        user_id: uuid.UUID,
        db: AsyncSession,
        workspace_path: Optional[Path] = None,
    ) -> ImpactAnalysisResponse:
        """Execute deterministic blast radius analysis for the requested file and symbol targets."""
        start_time = time.time()
        repo = await self.get_repository_for_user(repository_id, user_id, db)

        # 1. Check Graph Staleness
        is_stale = False
        staleness_reason = None
        if repo.indexing_status != "INDEXED":
            is_stale = True
            staleness_reason = f"Repository graph is not indexed (status: '{repo.indexing_status}')."
        elif not repo.last_indexed_at:
            is_stale = True
            staleness_reason = "Repository has no recorded indexing timestamp."

        bounded_depth = max(1, min(request.max_depth, 5))
        max_nodes = max(1, min(request.max_impacted_nodes, 200))

        # 2. Resolve Target Nodes
        target_nodes, targets_meta = await self._resolve_target_nodes(
            repository_id=repo.id,
            request=request,
            db=db,
        )

        if not target_nodes:
            duration = round(time.time() - start_time, 4)
            return ImpactAnalysisResponse(
                repository_id=str(repo.id),
                commit_sha=repo.current_commit_sha,
                is_stale=is_stale,
                staleness_reason=staleness_reason,
                targets=[],
                impact_score=0,
                severity="UNKNOWN",
                confidence=1.0,
                score_explanation="No target files or symbols could be resolved in the repository graph.",
                score_breakdown=ImpactScoreBreakdown(
                    files_score=0,
                    symbols_score=0,
                    depth_score=0,
                    coupling_score=0,
                    untested_penalty=0,
                ),
                summary=ImpactSummaryMetrics(
                    total_affected_files=0,
                    total_affected_symbols=0,
                    direct_impact_count=0,
                    transitive_impact_count=0,
                    recommended_tests_count=0,
                    unresolved_warnings_count=0,
                ),
                affected_files=[],
                impacted_nodes=[],
                dependency_paths=[],
                recommended_tests=[],
                unresolved_warnings=[],
                execution_duration_seconds=duration,
            )

        # 3. Perform Reverse Traversal (BFS)
        target_ids = {t.id for t in target_nodes}
        visited_ids: Set[uuid.UUID] = set(target_ids)
        
        # Mapping: node_id -> ImpactedNodeItem accumulator
        impacted_map: Dict[uuid.UUID, Dict[str, Any]] = {}
        paths_list: List[DependencyPathItem] = []
        unresolved_warnings: List[UnresolvedWarningItem] = []
        traversed_edges: List[RepositoryGraphEdge] = []

        # Queue elements: (current_node, current_depth, list_of_hops)
        # Seed queue with all resolved target nodes
        queue: deque[Tuple[RepositoryGraphNode, int, List[DependencyHop]]] = deque()
        for t in target_nodes:
            queue.append((t, 0, []))

        # Direct targets that are FILE nodes: expand to defined symbols as starting seeds
        file_target_ids = [t.id for t in target_nodes if t.node_type == "FILE"]
        if file_target_ids:
            defines_stmt = select(RepositoryGraphEdge).where(
                RepositoryGraphEdge.repository_id == repo.id,
                RepositoryGraphEdge.source_node_id.in_(file_target_ids),
                RepositoryGraphEdge.edge_type == "DEFINES",
            )
            defines_edges = (await db.execute(defines_stmt)).scalars().all()
            defined_sym_ids = [e.target_node_id for e in defines_edges if e.target_node_id]
            if defined_sym_ids:
                sym_nodes_stmt = select(RepositoryGraphNode).where(
                    RepositoryGraphNode.id.in_(defined_sym_ids)
                )
                sym_nodes = (await db.execute(sym_nodes_stmt)).scalars().all()
                for sn in sym_nodes:
                    if sn.id not in visited_ids:
                        visited_ids.add(sn.id)
                        queue.append((sn, 0, []))

        max_depth_reached = 0

        while queue and len(impacted_map) < max_nodes:
            curr_node, curr_depth, current_hops = queue.popleft()

            if curr_depth >= bounded_depth:
                continue

            # Query incoming edges (who depends on curr_node?)
            # Valid consumer edge: source_node -> [IMPORTS|CALLS|INHERITS|...] -> target_node (curr_node)
            incoming_stmt = (
                select(RepositoryGraphEdge)
                .where(
                    RepositoryGraphEdge.repository_id == repo.id,
                    RepositoryGraphEdge.target_node_id == curr_node.id,
                    RepositoryGraphEdge.edge_type.in_(VALID_CONSUMER_EDGE_TYPES),
                )
                .options(selectinload(RepositoryGraphEdge.source_node))
            )
            incoming_edges = (await db.execute(incoming_stmt)).scalars().all()

            for edge in incoming_edges:
                traversed_edges.append(edge)
                source_node = edge.source_node
                if not source_node:
                    continue

                # Flag unresolved or external edges
                if edge.resolution_status != "RESOLVED" or edge.confidence < 0.8:
                    unresolved_warnings.append(
                        UnresolvedWarningItem(
                            edge_id=str(edge.id),
                            source_node_name=source_node.name,
                            source_file=source_node.file_path,
                            target_symbol=edge.target_symbol or curr_node.name,
                            edge_type=edge.edge_type,
                            resolution_status=edge.resolution_status,
                            message=f"Consumer '{source_node.name}' has {edge.resolution_status} {edge.edge_type} reference to '{curr_node.name}'",
                        )
                    )

                next_depth = curr_depth + 1
                if next_depth > max_depth_reached:
                    max_depth_reached = next_depth

                hop = DependencyHop(
                    source_node_id=str(source_node.id),
                    source_name=source_node.name,
                    source_type=source_node.node_type,
                    edge_type=edge.edge_type,
                    target_node_id=str(curr_node.id),
                    target_name=curr_node.name,
                    confidence=edge.confidence,
                    resolution_status=edge.resolution_status,
                )
                new_hops = current_hops + [hop]

                # If this node is not one of the original target seeds, record as impacted
                if source_node.id not in target_ids:
                    is_direct = (next_depth == 1)
                    if source_node.id not in impacted_map:
                        impacted_map[source_node.id] = {
                            "node": source_node,
                            "depth": next_depth,
                            "is_direct": is_direct,
                            "primary_reason": f"Directly {edge.edge_type.lower()} by {curr_node.name}" if is_direct else f"Transitively depends on {curr_node.name} via {edge.edge_type}",
                            "confidence": edge.confidence,
                            "resolution_status": edge.resolution_status,
                            "paths_count": 1,
                        }
                    else:
                        impacted_map[source_node.id]["paths_count"] += 1
                        if next_depth < impacted_map[source_node.id]["depth"]:
                            impacted_map[source_node.id]["depth"] = next_depth
                            impacted_map[source_node.id]["is_direct"] = (next_depth == 1)

                    # Build dependency path explanation
                    if len(paths_list) < (max_nodes * 2):
                        explanation_parts = [f"{h.source_name} ({h.source_type}) -[{h.edge_type}]->" for h in new_hops]
                        final_target = target_nodes[0].name if target_nodes else "target"
                        full_expl = " ".join(explanation_parts) + f" {final_target}"
                        paths_list.append(
                            DependencyPathItem(
                                target_name=curr_node.name,
                                impacted_node_id=str(source_node.id),
                                impacted_name=source_node.name,
                                impacted_file_path=source_node.file_path,
                                depth=next_depth,
                                hops=new_hops,
                                explanation=full_expl,
                            )
                        )

                # Queue for transitive exploration if not visited yet
                if source_node.id not in visited_ids:
                    visited_ids.add(source_node.id)
                    queue.append((source_node, next_depth, new_hops))

        # 4. Construct Impacted Node Items and Aggregate File Lists
        impacted_nodes_output: List[ImpactedNodeItem] = []
        affected_files_set: Set[str] = set()

        for t in target_nodes:
            if t.file_path:
                affected_files_set.add(t.file_path)

        direct_count = 0
        transitive_count = 0

        for nid, info in impacted_map.items():
            n: RepositoryGraphNode = info["node"]
            if n.file_path:
                affected_files_set.add(n.file_path)

            if info["is_direct"]:
                direct_count += 1
            else:
                transitive_count += 1

            impacted_nodes_output.append(
                ImpactedNodeItem(
                    node_id=str(n.id),
                    node_type=n.node_type,
                    qualified_name=n.qualified_name,
                    name=n.name,
                    file_path=n.file_path,
                    language=n.language,
                    start_line=n.start_line,
                    end_line=n.end_line,
                    depth=info["depth"],
                    is_direct=info["is_direct"],
                    primary_reason=info["primary_reason"],
                    confidence=info["confidence"],
                    resolution_status=info["resolution_status"],
                    paths_count=info["paths_count"],
                    metadata=n.meta_info or {},
                )
            )

        # Sort impacted nodes: direct first, then by depth ascending, then name
        impacted_nodes_output.sort(key=lambda x: (x.depth, x.node_type, x.name))

        # 5. Recommend Relevant Tests
        recommended_tests: List[RecommendedTestItem] = []
        if request.include_tests:
            recommended_tests = await self._discover_recommended_tests(
                repository=repo,
                target_nodes=target_nodes,
                impacted_nodes=impacted_nodes_output,
                affected_files=affected_files_set,
                db=db,
                workspace_path=workspace_path,
            )

        # 6. Calculate Explainable Deterministic Score & Confidence
        score, severity, breakdown, explanation = self._calculate_impact_score(
            affected_files_count=len(affected_files_set),
            direct_symbols_count=direct_count,
            transitive_symbols_count=transitive_count,
            max_depth=max_depth_reached,
            paths_count=len(paths_list),
            distinct_directories_count=len({str(Path(f).parent) for f in affected_files_set if f}),
            recommended_tests_count=len(recommended_tests),
        )

        # 7. Workspace and Package Boundary Resolution
        pkg_nodes = (
            await db.execute(
                select(RepositoryGraphNode).where(
                    RepositoryGraphNode.repository_id == repo.id,
                    RepositoryGraphNode.node_type == "PACKAGE",
                )
            )
        ).scalars().all()

        affected_packages_set: Set[str] = set()
        target_packages_set: Set[str] = set()
        cross_package_boundaries = False

        if pkg_nodes:
            for pnode in pkg_nodes:
                pkg_path = pnode.file_path or ""
                pkg_prefix = f"{pkg_path}/" if pkg_path and pkg_path != "." else ""

                for t in targets_meta:
                    tf = t.file_path or ""
                    if pkg_path and (tf.startswith(pkg_prefix) or tf == pkg_path):
                        target_packages_set.add(pnode.name)

                for af in affected_files_set:
                    if pkg_path and (af.startswith(pkg_prefix) or af == pkg_path):
                        affected_packages_set.add(pnode.name)

            if len(affected_packages_set) > 1 or (target_packages_set and (affected_packages_set - target_packages_set)):
                cross_package_boundaries = True
                explanation += f" Impact crosses package boundaries affecting: {', '.join(sorted(affected_packages_set))}."

        overall_confidence = self._calculate_overall_confidence(traversed_edges)

        summary_metrics = ImpactSummaryMetrics(
            total_affected_files=len(affected_files_set),
            total_affected_symbols=len(impacted_nodes_output),
            direct_impact_count=direct_count,
            transitive_impact_count=transitive_count,
            recommended_tests_count=len(recommended_tests),
            unresolved_warnings_count=len(unresolved_warnings),
        )

        duration = round(time.time() - start_time, 4)
        logger.info(
            "impact_analysis_completed",
            repo_id=str(repo.id),
            targets_count=len(target_nodes),
            affected_files=len(affected_files_set),
            affected_symbols=len(impacted_nodes_output),
            score=score,
            severity=severity,
            duration=duration,
        )

        return ImpactAnalysisResponse(
            repository_id=str(repo.id),
            commit_sha=repo.current_commit_sha,
            is_stale=is_stale,
            staleness_reason=staleness_reason,
            targets=targets_meta,
            impact_score=score,
            severity=severity,
            confidence=overall_confidence,
            score_explanation=explanation,
            score_breakdown=breakdown,
            summary=summary_metrics,
            affected_files=sorted(list(affected_files_set)),
            affected_packages=sorted(list(affected_packages_set)),
            cross_package_boundaries=cross_package_boundaries,
            impacted_nodes=impacted_nodes_output,
            dependency_paths=paths_list[:50],  # cap returned paths
            recommended_tests=recommended_tests,
            unresolved_warnings=unresolved_warnings[:30],
            execution_duration_seconds=duration,
        )

    # ---------------------------------------------------------------------------
    # Internal Target Resolution
    # ---------------------------------------------------------------------------

    async def _resolve_target_nodes(
        self,
        repository_id: uuid.UUID,
        request: ImpactAnalysisRequest,
        db: AsyncSession,
    ) -> Tuple[List[RepositoryGraphNode], List[ImpactTarget]]:
        """Resolve requested file paths, symbol IDs, and qualified names to concrete graph nodes."""
        resolved_nodes: List[RepositoryGraphNode] = []
        targets_meta: List[ImpactTarget] = []

        conditions = []
        if request.symbol_ids:
            parsed_ids = []
            for sid in request.symbol_ids:
                try:
                    parsed_ids.append(uuid.UUID(sid))
                except Exception:
                    pass
            if parsed_ids:
                conditions.append(RepositoryGraphNode.id.in_(parsed_ids))

        if request.qualified_names:
            conditions.append(RepositoryGraphNode.qualified_name.in_(request.qualified_names))

        if request.file_paths:
            clean_paths = [f.strip().lstrip("/") for f in request.file_paths if f.strip()]
            if clean_paths:
                conditions.append(
                    RepositoryGraphNode.file_path.in_(clean_paths),
                )

        if not conditions:
            return [], []

        stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repository_id,
            or_(*conditions),
        )
        nodes = (await db.execute(stmt)).scalars().all()

        for n in nodes:
            resolved_nodes.append(n)
            targets_meta.append(
                ImpactTarget(
                    node_id=str(n.id),
                    node_type=n.node_type,
                    qualified_name=n.qualified_name,
                    name=n.name,
                    file_path=n.file_path,
                )
            )

        return resolved_nodes, targets_meta

    # ---------------------------------------------------------------------------
    # Test Discovery Correlation
    # ---------------------------------------------------------------------------

    async def _discover_recommended_tests(
        self,
        repository: Repository,
        target_nodes: List[RepositoryGraphNode],
        impacted_nodes: List[ImpactedNodeItem],
        affected_files: Set[str],
        db: AsyncSession,
        workspace_path: Optional[Path] = None,
    ) -> List[RecommendedTestItem]:
        """Correlate confirmed graph test dependencies with naming heuristics."""
        recommended: List[RecommendedTestItem] = []
        seen_test_files: Set[str] = set()

        # 1. Confirmed Test Nodes in the Impact Graph (Incoming IMPORTS or CALLS from test files)
        test_node_candidates = [
            n for n in impacted_nodes
            if (n.file_path and any(ind in (n.file_path or "") for ind in TEST_FILE_INDICATORS))
        ]

        for tn in test_node_candidates:
            if tn.file_path and tn.file_path not in seen_test_files:
                seen_test_files.add(tn.file_path)
                recommended.append(
                    RecommendedTestItem(
                        test_file_path=tn.file_path,
                        test_framework="pytest" if tn.language == "Python" else "jest",
                        recommendation_type="CONFIRMED",
                        confidence=0.98,
                        reason=f"Test file '{tn.file_path}' has confirmed graph dependency on changed symbol '{tn.name}'",
                        target_symbol_or_file=tn.name,
                    )
                )

        # 2. Query DB directly for test files that import any of the affected files
        if affected_files:
            file_nodes_stmt = select(RepositoryGraphNode.id, RepositoryGraphNode.file_path).where(
                RepositoryGraphNode.repository_id == repository.id,
                RepositoryGraphNode.file_path.in_(list(affected_files)),
            )
            file_rows = (await db.execute(file_nodes_stmt)).all()
            target_file_ids = [r[0] for r in file_rows]

            if target_file_ids:
                incoming_test_edges_stmt = (
                    select(RepositoryGraphEdge)
                    .where(
                        RepositoryGraphEdge.repository_id == repository.id,
                        RepositoryGraphEdge.target_node_id.in_(target_file_ids),
                        RepositoryGraphEdge.edge_type.in_(["IMPORTS", "DEPENDS_ON"]),
                    )
                    .options(selectinload(RepositoryGraphEdge.source_node))
                )
                test_edges = (await db.execute(incoming_test_edges_stmt)).scalars().all()
                for te in test_edges:
                    src = te.source_node
                    if src and src.file_path and any(ind in src.file_path for ind in TEST_FILE_INDICATORS):
                        if src.file_path not in seen_test_files:
                            seen_test_files.add(src.file_path)
                            recommended.append(
                                RecommendedTestItem(
                                    test_file_path=src.file_path,
                                    test_framework="pytest" if src.language == "Python" else "jest",
                                    recommendation_type="CONFIRMED",
                                    confidence=0.95,
                                    reason=f"Test file '{src.file_path}' directly imports affected file '{src.name}'",
                                    target_symbol_or_file=src.file_path,
                                )
                            )

        # 3. Heuristic Naming Matching (e.g. tests/test_<stem>.py)
        all_test_files_stmt = select(RepositoryGraphNode.file_path, RepositoryGraphNode.language).where(
            RepositoryGraphNode.repository_id == repository.id,
            RepositoryGraphNode.node_type == "FILE",
        )
        all_files = (await db.execute(all_test_files_stmt)).all()
        repo_test_files = [
            (r[0], r[1]) for r in all_files
            if r[0] and any(ind in r[0] for ind in TEST_FILE_INDICATORS)
        ]

        for aff_file in affected_files:
            stem = Path(aff_file).stem
            if stem.startswith("test_") or stem.endswith("_test"):
                continue  # Skip test files themselves

            for tf_path, tf_lang in repo_test_files:
                if tf_path in seen_test_files:
                    continue
                tf_stem = Path(tf_path).stem
                # Check naming matches
                if (
                    tf_stem in (f"test_{stem}", f"{stem}_test")
                    or tf_stem.startswith(f"{stem}.test")
                    or tf_stem.startswith(f"{stem}.spec")
                    or tf_stem in (f"{stem}Test", f"Test{stem}")
                ):
                    seen_test_files.add(tf_path)
                    recommended.append(
                        RecommendedTestItem(
                            test_file_path=tf_path,
                            test_framework="pytest" if tf_lang == "Python" else "jest",
                            recommendation_type="HEURISTIC",
                            confidence=0.75,
                            reason=f"Test file '{tf_path}' matches source module stem '{stem}' by naming convention",
                            target_symbol_or_file=aff_file,
                        )
                    )

        # Sort recommendations: CONFIRMED first, then by confidence descending
        recommended.sort(key=lambda r: (0 if r.recommendation_type == "CONFIRMED" else 1, -r.confidence))
        return recommended

    # ---------------------------------------------------------------------------
    # Deterministic Scoring Engine
    # ---------------------------------------------------------------------------

    def _calculate_impact_score(
        self,
        affected_files_count: int,
        direct_symbols_count: int,
        transitive_symbols_count: int,
        max_depth: int,
        paths_count: int,
        distinct_directories_count: int,
        recommended_tests_count: int,
    ) -> Tuple[int, str, ImpactScoreBreakdown, str]:
        """Compute deterministic 0-100 impact score and severity band."""
        # 1. Affected files contribution: up to 30 points
        files_score = min(30, affected_files_count * 6)

        # 2. Affected symbols contribution: up to 25 points
        symbols_score = min(25, int(direct_symbols_count * 4 + transitive_symbols_count * 1.5))

        # 3. Traversal depth & reach: up to 20 points
        depth_score = min(20, max_depth * 4 + min(10, paths_count))

        # 4. Cross-module / directory coupling: up to 15 points
        coupling_score = min(15, distinct_directories_count * 5)

        # 5. Untested risk penalty: 10 points if 0 tests are mapped
        untested_penalty = 10 if (recommended_tests_count == 0 and affected_files_count > 0) else 0

        raw_total = files_score + symbols_score + depth_score + coupling_score + untested_penalty
        total_score = min(100, raw_total)

        # Severity categorization
        if total_score >= 80:
            severity = "CRITICAL"
            explanation = f"Critical impact (score {total_score}/100): Wide multi-module blast radius affecting {affected_files_count} files and {direct_symbols_count + transitive_symbols_count} symbols across {distinct_directories_count} directories."
        elif total_score >= 60:
            severity = "HIGH"
            explanation = f"High impact (score {total_score}/100): Significant coupling across {affected_files_count} files and {direct_symbols_count + transitive_symbols_count} symbols with traversal depth {max_depth}."
        elif total_score >= 30:
            severity = "MEDIUM"
            explanation = f"Medium impact (score {total_score}/100): Moderate localized blast radius affecting {affected_files_count} files and {direct_symbols_count + transitive_symbols_count} symbols."
        elif total_score > 0:
            severity = "LOW"
            explanation = f"Low impact (score {total_score}/100): Localized change with minimal downstream consumers."
        else:
            severity = "UNKNOWN"
            explanation = "No downstream consumers identified in the repository graph."

        breakdown = ImpactScoreBreakdown(
            files_score=files_score,
            symbols_score=symbols_score,
            depth_score=depth_score,
            coupling_score=coupling_score,
            untested_penalty=untested_penalty,
        )

        return total_score, severity, breakdown, explanation

    def _calculate_overall_confidence(
        self,
        edges: List[RepositoryGraphEdge],
    ) -> float:
        """Calculate weighted confidence rating [0.0, 1.0] across all traversed edges."""
        if not edges:
            return 1.0

        total_weight = 0.0
        weighted_sum = 0.0

        for e in edges:
            status_multiplier = 1.0
            if e.resolution_status == "EXTERNAL":
                status_multiplier = 0.8
            elif e.resolution_status in ("UNRESOLVED", "AMBIGUOUS"):
                status_multiplier = 0.5

            score = e.confidence * status_multiplier
            weighted_sum += score
            total_weight += 1.0

        if total_weight == 0.0:
            return 1.0

        return round(weighted_sum / total_weight, 2)
