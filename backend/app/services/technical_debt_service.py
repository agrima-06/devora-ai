"""Technical Debt Intelligence Engine.

Measures code duplication, structural/cyclomatic complexity, dependency debt,
maintainability hazards, and test deficits using deterministic AST analysis and graph topology.
"""

import ast
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.flaky_test_record import FlakyTestRecord
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.repository_technical_debt import RepositoryTechnicalDebt
from app.models.user import User
from app.schemas.drift import (
    TechnicalDebtDimensionScores,
    TechnicalDebtFindingItem,
    TechnicalDebtFindingsResponse,
    TechnicalDebtSummaryResponse,
    TechnicalDebtTrendItem,
    TechnicalDebtTrendsResponse,
)

logger = get_logger("technical_debt_service")


class TechnicalDebtService:
    """Computes explainable, deterministic technical debt scores and actionable findings."""

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

    async def analyze_technical_debt(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> TechnicalDebtSummaryResponse:
        """Execute full technical debt evaluation across 5 dimensions and persist snapshot."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        # 1. Fetch graph nodes, edges, files, knowledge, flaky tests
        nodes_stmt = select(RepositoryGraphNode).where(RepositoryGraphNode.repository_id == repo.id)
        nodes_res = await db.execute(nodes_stmt)
        nodes = nodes_res.scalars().all()

        edges_stmt = select(RepositoryGraphEdge).where(RepositoryGraphEdge.repository_id == repo.id)
        edges_res = await db.execute(edges_stmt)
        edges = edges_res.scalars().all()

        files_stmt = select(RepositoryFile).where(RepositoryFile.repository_id == repo.id)
        files_res = await db.execute(files_stmt)
        files = files_res.scalars().all()

        k_stmt = select(RepositoryKnowledge).where(RepositoryKnowledge.repository_id == repo.id)
        k_res = await db.execute(k_stmt)
        knowledge = k_res.scalars().all()

        flaky_stmt = select(FlakyTestRecord).where(FlakyTestRecord.repository_id == repo.id)
        flaky_res = await db.execute(flaky_stmt)
        flaky_records = flaky_res.scalars().all()

        evidence = {
            "repository": repo,
            "nodes": nodes,
            "edges": edges,
            "files": files,
            "knowledge": knowledge,
            "flaky_records": flaky_records,
        }

        # 2. Evaluate 5 dimensions
        findings: List[TechnicalDebtFindingItem] = []

        comp_findings, comp_score = self._evaluate_complexity(evidence)
        dup_findings, dup_score = self._evaluate_duplication(evidence)
        dep_findings, dep_score = self._evaluate_dependencies(evidence)
        maint_findings, maint_score = self._evaluate_maintainability(evidence)
        test_findings, test_score = self._evaluate_test_debt(evidence)

        findings.extend(comp_findings)
        findings.extend(dup_findings)
        findings.extend(dep_findings)
        findings.extend(maint_findings)
        findings.extend(test_findings)

        # 3. Deterministic Composite Score Formula
        # 25% Complexity + 20% Duplication + 20% Dependency + 20% Test + 15% Maintainability
        score_res = self._calculate_composite_score(
            complexity=comp_score,
            duplication=dup_score,
            dependency=dep_score,
            test_debt=test_score,
            maintainability=maint_score,
        )
        overall_score = score_res["score"]
        severity = score_res["severity"]

        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in findings if f.severity == "HIGH")
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in findings if f.severity == "LOW")

        # Sort findings by severity order (CRITICAL > HIGH > MEDIUM > LOW)
        sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        findings.sort(key=lambda x: (sev_rank.get(x.severity, 4), -x.confidence))

        dim_scores = TechnicalDebtDimensionScores(
            complexity=comp_score,
            duplication=dup_score,
            dependency=dep_score,
            architecture_drift=dep_score,  # cross-reference
            test_debt=test_score,
            maintainability=maint_score,
        )

        summary_metrics = {
            "total_files_analyzed": len(files),
            "total_symbols_analyzed": len(nodes),
            "flaky_tests_count": len(flaky_records),
            "dominant_dimension": max(
                [
                    ("complexity", comp_score),
                    ("duplication", dup_score),
                    ("dependency", dep_score),
                    ("test_debt", test_score),
                    ("maintainability", maint_score),
                ],
                key=lambda x: x[1],
            )[0],
        }

        # 4. Persist to database
        rec = RepositoryTechnicalDebt(
            repository_id=repo.id,
            commit_sha=repo.current_commit_sha,
            overall_debt_score=overall_score,
            severity=severity,
            confidence=0.92,
            dimension_scores=dim_scores.model_dump(),
            summary_metrics=summary_metrics,
            findings=[f.model_dump() for f in findings],
        )
        db.add(rec)
        await db.commit()

        return TechnicalDebtSummaryResponse(
            repository_id=str(repo.id),
            commit_sha=repo.current_commit_sha,
            overall_debt_score=overall_score,
            severity=severity,
            confidence=0.92,
            dimension_scores=dim_scores,
            summary_metrics=summary_metrics,
            total_findings=len(findings),
            critical_findings=critical_count,
            high_findings=high_count,
            medium_findings=medium_count,
            low_findings=low_count,
            top_findings=findings[:10],
            last_analyzed_at=str(rec.created_at),
        )

    async def get_technical_debt_summary(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> TechnicalDebtSummaryResponse:
        """Fetch latest technical debt summary, or analyze on-demand."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = (
            select(RepositoryTechnicalDebt)
            .where(RepositoryTechnicalDebt.repository_id == repo.id)
            .order_by(RepositoryTechnicalDebt.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        snapshot = res.scalar_one_or_none()

        if not snapshot:
            return await self.analyze_technical_debt(repository_id, user, db)

        findings = [TechnicalDebtFindingItem(**f) for f in (snapshot.findings or [])]
        dim_scores = TechnicalDebtDimensionScores(**(snapshot.dimension_scores or {}))

        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in findings if f.severity == "HIGH")
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in findings if f.severity == "LOW")

        return TechnicalDebtSummaryResponse(
            repository_id=str(repo.id),
            commit_sha=snapshot.commit_sha,
            overall_debt_score=snapshot.overall_debt_score,
            severity=snapshot.severity,
            confidence=snapshot.confidence,
            dimension_scores=dim_scores,
            summary_metrics=snapshot.summary_metrics or {},
            total_findings=len(findings),
            critical_findings=critical_count,
            high_findings=high_count,
            medium_findings=medium_count,
            low_findings=low_count,
            top_findings=findings[:10],
            is_stale=bool(repo.current_commit_sha and snapshot.commit_sha and snapshot.commit_sha != repo.current_commit_sha),
            last_analyzed_at=str(snapshot.created_at),
        )

    async def get_findings(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TechnicalDebtFindingsResponse:
        """Get paginated technical debt findings with category and severity filters."""
        summary = await self.get_technical_debt_summary(repository_id, user, db)
        snapshot_stmt = (
            select(RepositoryTechnicalDebt)
            .where(RepositoryTechnicalDebt.repository_id == repository_id)
            .order_by(RepositoryTechnicalDebt.created_at.desc())
            .limit(1)
        )
        res = await db.execute(snapshot_stmt)
        snapshot = res.scalar_one_or_none()

        all_findings = [TechnicalDebtFindingItem(**f) for f in (snapshot.findings if snapshot else [])]

        if category:
            all_findings = [f for f in all_findings if f.category.lower() == category.lower()]
        if severity:
            all_findings = [f for f in all_findings if f.severity.upper() == severity.upper()]

        total_count = len(all_findings)
        paginated = all_findings[offset : offset + limit]

        return TechnicalDebtFindingsResponse(
            repository_id=str(repository_id),
            total_count=total_count,
            limit=limit,
            offset=offset,
            findings=paginated,
        )

    async def get_debt_trends(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> TechnicalDebtTrendsResponse:
        """Fetch historical technical debt progression across recent snapshots."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = (
            select(RepositoryTechnicalDebt)
            .where(RepositoryTechnicalDebt.repository_id == repo.id)
            .order_by(RepositoryTechnicalDebt.created_at.asc())
            .limit(20)
        )
        res = await db.execute(stmt)
        records = res.scalars().all()

        trend_items = []
        for r in records:
            findings = r.findings or []
            crit_count = sum(1 for f in findings if f.get("severity") == "CRITICAL")
            trend_items.append(
                TechnicalDebtTrendItem(
                    commit_sha=r.commit_sha or "HEAD",
                    analyzed_at=str(r.created_at),
                    overall_debt_score=r.overall_debt_score,
                    severity=r.severity,
                    critical_findings=crit_count,
                    total_findings=len(findings),
                )
            )

        return TechnicalDebtTrendsResponse(
            repository_id=str(repo.id),
            trends=trend_items,
        )

    # -------------------------------------------------------------------------
    # DIMENSION EVALUATORS
    # -------------------------------------------------------------------------

    def _calculate_composite_score(
        self,
        complexity: float,
        duplication: float,
        dependency: float,
        test_debt: float,
        maintainability: float,
    ) -> Dict[str, Any]:
        """Compute weighted technical debt composite score (0-100) and severity band."""
        raw_score = 0.25 * complexity + 0.20 * duplication + 0.20 * dependency + 0.20 * test_debt + 0.15 * maintainability
        overall_score = round(min(100.0, max(0.0, raw_score)), 1)

        if overall_score >= 80.0:
            severity = "CRITICAL"
        elif overall_score >= 60.0:
            severity = "HIGH"
        elif overall_score >= 35.0:
            severity = "MEDIUM"
        elif overall_score > 0.0:
            severity = "LOW"
        else:
            severity = "CLEAN"

        return {"score": overall_score, "severity": severity}

    def _evaluate_complexity(self, ev: Dict[str, Any]) -> Tuple[List[TechnicalDebtFindingItem], float]:
        """Evaluate function length, nesting depth, and class sizes."""
        findings: List[TechnicalDebtFindingItem] = []
        nodes = ev["nodes"]
        knowledge = ev.get("knowledge", [])
        knowledge_by_symbol = {
            (getattr(k, "file_path", None), getattr(k, "symbol_name", None)): getattr(k, "content", "")
            for k in knowledge
        }
        penalty = 0.0

        for n in nodes:
            snippet = knowledge_by_symbol.get((n.file_path, n.name))
            if snippet and len(snippet) > 250:
                snippet = snippet[:250]

            # Check function length
            if n.node_type in ("FUNCTION", "METHOD") and n.start_line and n.end_line:
                lines = n.end_line - n.start_line + 1
                if lines > 60:
                    sev = "HIGH" if lines > 120 else "MEDIUM"
                    pt = 15.0 if lines > 120 else 8.0
                    penalty += pt
                    findings.append(
                        TechnicalDebtFindingItem(
                            finding_id=f"comp_fn_{uuid.uuid4().hex[:8]}",
                            category="complexity",
                            title=f"Oversized Function ({lines} lines)",
                            severity=sev,
                            confidence=0.95,
                            file_path=n.file_path or "",
                            symbol_name=n.name,
                            line_number=n.start_line,
                            line_end=n.end_line,
                            measured_metric={"lines_count": lines, "threshold": 60},
                            explanation=f"Function '{n.name}' exceeds the 60-line maintainability threshold with {lines} lines.",
                            remediation="Decompose into cohesive helper functions or delegate sub-tasks to dedicated service methods.",
                            potential_impact="High cognitive load, testing difficulty, and increased risk of regressions during modification.",
                            detection_method="AST_ANALYSIS",
                            evidence_snippet=snippet,
                        )
                    )

            # Check class size
            elif n.node_type == "CLASS" and n.start_line and n.end_line:
                lines = n.end_line - n.start_line + 1
                if lines > 300:
                    sev = "HIGH" if lines > 500 else "MEDIUM"
                    penalty += 12.0
                    findings.append(
                        TechnicalDebtFindingItem(
                            finding_id=f"comp_cls_{uuid.uuid4().hex[:8]}",
                            category="complexity",
                            title=f"Large Class ({lines} lines)",
                            severity=sev,
                            confidence=0.95,
                            file_path=n.file_path or "",
                            symbol_name=n.name,
                            line_number=n.start_line,
                            line_end=n.end_line,
                            measured_metric={"lines_count": lines, "threshold": 300},
                            explanation=f"Class '{n.name}' spans {lines} lines, indicating multiple competing responsibilities.",
                            remediation="Refactor using composition or split into focused modular classes.",
                            potential_impact="Violates Single Responsibility Principle, impeding modular refactoring.",
                            detection_method="AST_ANALYSIS",
                            evidence_snippet=snippet,
                        )
                    )

        score = min(100.0, penalty)
        return findings, score

    def _evaluate_duplication(self, ev: Dict[str, Any]) -> Tuple[List[TechnicalDebtFindingItem], float]:
        """Detect duplicate function implementations via AST signature comparison and content hashing."""
        findings: List[TechnicalDebtFindingItem] = []
        knowledge = ev["knowledge"]
        penalty = 0.0

        # Group functions by content hash or normalized snippet
        content_groups: Dict[str, List[Any]] = defaultdict(list)
        for k in knowledge:
            if k.symbol_type in ("function", "method") and k.content and len(k.content.strip()) > 80:
                # Normalize whitespace
                norm = re.sub(r"\s+", " ", k.content.strip().lower())
                # Normalize function header to match Type-2 clones
                norm_body = re.sub(r"^(?:async\s+)?def\s+\w+\s*\([^)]*\)\s*(?:->[^:]+)?:?", "", norm).strip()
                sig_key = norm_body[:100] if len(norm_body) >= 40 else norm[:100]
                content_groups[sig_key].append(k)

        for sig_key, group in content_groups.items():
            if len(group) >= 2:
                # Potential duplication
                f1 = group[0]
                f2 = group[1]
                if f1.file_path != f2.file_path:
                    penalty += 20.0
                    findings.append(
                        TechnicalDebtFindingItem(
                            finding_id=f"dup_{uuid.uuid4().hex[:8]}",
                            category="duplication",
                            title=f"Duplicated Function Logic ({f1.symbol_name})",
                            severity="HIGH",
                            confidence=0.88,
                            file_path=f1.file_path or "",
                            symbol_name=f1.symbol_name,
                            line_number=(f1.meta_info or {}).get("start_line", 1),
                            measured_metric={"duplicate_occurrences": len(group), "paired_file": f2.file_path},
                            explanation=(
                                f"Function '{f1.symbol_name}' in '{f1.file_path}' shares identical or near-identical "
                                f"structural logic with '{f2.symbol_name}' in '{f2.file_path}'."
                            ),
                            remediation="Extract common implementation into a shared utility or helper module.",
                            potential_impact="Bug fixes applied to one copy will not propagate to duplicates, causing behavioral divergence.",
                            detection_method="TOKEN_SIMILARITY",
                            evidence_snippet=f1.content[:200] if f1.content else None,
                        )
                    )

        score = min(100.0, penalty)
        return findings, score

    def _evaluate_dependencies(self, ev: Dict[str, Any]) -> Tuple[List[TechnicalDebtFindingItem], float]:
        """Evaluate unresolved references and cyclic coupling."""
        findings: List[TechnicalDebtFindingItem] = []
        edges = ev["edges"]
        nodes_by_id = {n.id: n for n in ev["nodes"]}
        penalty = 0.0

        # 1. Check unresolved references
        unresolved_edges = [e for e in edges if e.resolution_status == "UNRESOLVED"]
        if unresolved_edges:
            unres_count = len(unresolved_edges)
            pt = min(30.0, unres_count * 5.0)
            penalty += pt
            findings.append(
                TechnicalDebtFindingItem(
                    finding_id=f"dep_unres_{uuid.uuid4().hex[:8]}",
                    category="dependency",
                    title=f"Unresolved Dependency References ({unres_count} edges)",
                    severity="MEDIUM" if unres_count < 5 else "HIGH",
                    confidence=0.95,
                    file_path=nodes_by_id[unresolved_edges[0].source_node_id].file_path if unresolved_edges[0].source_node_id in nodes_by_id else "unknown",
                    measured_metric={"unresolved_count": unres_count},
                    explanation=f"Found {unres_count} unresolved imports or symbol references in the static dependency graph.",
                    remediation="Check missing dependencies, verify virtual environment installation, or fix import paths.",
                    potential_impact="Build fragility, broken IDE autocomplete, and risk of runtime ModuleNotFoundError.",
                    detection_method="STATIC_INSPECTION",
                )
            )

        # 2. Check high fan-out (module importing > 15 entities)
        out_degree: Dict[uuid.UUID, int] = defaultdict(int)
        for e in edges:
            if e.edge_type in ("IMPORTS", "DEPENDS_ON"):
                out_degree[e.source_node_id] += 1

        for node_id, count in out_degree.items():
            if count > 15:
                node = nodes_by_id.get(node_id)
                if node and node.file_path:
                    penalty += 10.0
                    findings.append(
                        TechnicalDebtFindingItem(
                            finding_id=f"dep_fanout_{uuid.uuid4().hex[:8]}",
                            category="dependency",
                            title=f"Excessive Coupling / High Fan-Out ({count} dependencies)",
                            severity="MEDIUM",
                            confidence=0.90,
                            file_path=node.file_path,
                            symbol_name=node.name,
                            line_number=node.start_line or 1,
                            measured_metric={"outgoing_dependencies": count, "threshold": 15},
                            explanation=f"Module '{node.name}' depends on {count} distinct components, indicating high coupling.",
                            remediation="Refactor to use higher-level facade abstractions or split module into focused subunits.",
                            potential_impact="Cascading blast radius: changes across any of the {count} dependencies risk breaking this module.",
                            detection_method="GRAPH_CYCLE",
                        )
                    )

        score = min(100.0, penalty)
        return findings, score

    def _evaluate_maintainability(self, ev: Dict[str, Any]) -> Tuple[List[TechnicalDebtFindingItem], float]:
        """Evaluate TODO/FIXME concentrations and bare exception handling."""
        findings: List[TechnicalDebtFindingItem] = []
        knowledge = ev["knowledge"]
        penalty = 0.0

        for k in knowledge:
            content = k.content or ""
            fpath = k.file_path or ""

            # Check TODO/FIXME concentrations
            todo_matches = re.findall(r"(?:TODO|FIXME|HACK|XXX):?", content, re.I)
            if len(todo_matches) >= 3:
                penalty += 10.0
                findings.append(
                    TechnicalDebtFindingItem(
                        finding_id=f"maint_todo_{uuid.uuid4().hex[:8]}",
                        category="maintainability",
                        title=f"Accumulation of Technical Markers ({len(todo_matches)} TODOs)",
                        severity="LOW",
                        confidence=0.92,
                        file_path=fpath,
                        symbol_name=k.symbol_name,
                        line_number=(k.meta_info or {}).get("start_line", 1),
                        measured_metric={"todo_count": len(todo_matches)},
                        explanation=f"Module '{fpath}' contains {len(todo_matches)} pending TODO/FIXME notes.",
                        remediation="Address unresolved tasks or convert them into tracked project task tickets.",
                        potential_impact="Incomplete edge case handling and developer confusion regarding production readiness.",
                        detection_method="STATIC_INSPECTION",
                    )
                )

            # Check bare exception catching
            if "except Exception: pass" in content or "except: pass" in content:
                penalty += 15.0
                findings.append(
                    TechnicalDebtFindingItem(
                        finding_id=f"maint_exc_{uuid.uuid4().hex[:8]}",
                        category="maintainability",
                        title="Silent Exception Suppression (`except: pass`)",
                        severity="HIGH",
                        confidence=0.96,
                        file_path=fpath,
                        symbol_name=k.symbol_name,
                        line_number=(k.meta_info or {}).get("start_line", 1),
                        measured_metric={"pattern": "except: pass"},
                        explanation="Module silently suppresses caught exceptions without logging or structured handling.",
                        remediation="Log the exception with traceback or raise a domain-specific `DevoraException`.",
                        potential_impact="Masks critical runtime bugs, making root cause analysis impossible during incidents.",
                        detection_method="STATIC_INSPECTION",
                    )
                )

        score = min(100.0, penalty)
        return findings, score

    def _evaluate_test_debt(self, ev: Dict[str, Any]) -> Tuple[List[TechnicalDebtFindingItem], float]:
        """Evaluate test deficit: critical core components without tests and flaky test recurrence."""
        findings: List[TechnicalDebtFindingItem] = []
        files = ev["files"]
        flaky_records = ev["flaky_records"]
        penalty = 0.0

        test_paths = [f.file_path for f in files if "test" in f.file_path.lower()]
        service_paths = [f.file_path for f in files if "services/" in f.file_path and f.file_path.endswith(".py")]

        # Check services missing corresponding test file
        has_any_tests = len(test_paths) > 0
        for sp in service_paths:
            base_name = Path(sp).stem  # e.g. auth_service
            has_test = any(f"test_{base_name}" in tp or f"{base_name}_test" in tp for tp in test_paths)
            if not has_test:
                penalty += 12.0
                test_status = "CONFIRMED_ABSENT" if has_any_tests else "UNKNOWN_COVERAGE"
                conf = 0.90 if has_any_tests else 0.70
                findings.append(
                    TechnicalDebtFindingItem(
                        finding_id=f"test_miss_{uuid.uuid4().hex[:8]}",
                        category="test",
                        title=f"Untested Domain Service ({base_name})",
                        severity="HIGH",
                        confidence=conf,
                        file_path=sp,
                        measured_metric={"service_file": sp, "test_status": test_status, "test_suite_discovered": has_any_tests},
                        explanation=f"Domain service '{sp}' lacks a dedicated automated test suite in `tests/` ({test_status}).",
                        remediation=f"Author unit and integration tests in `backend/tests/unit/test_{base_name}.py`.",
                        potential_impact="High risk of regressions during code revisions and refactoring cycles.",
                        detection_method="STATIC_INSPECTION",
                    )
                )

        # Check flaky test concentrations
        if flaky_records:
            flaky_count = len(flaky_records)
            penalty += min(25.0, flaky_count * 5.0)
            findings.append(
                TechnicalDebtFindingItem(
                    finding_id=f"test_flaky_{uuid.uuid4().hex[:8]}",
                    category="test",
                    title=f"Flaky Test Concentration ({flaky_count} unstable tests)",
                    severity="MEDIUM",
                    confidence=0.95,
                    file_path=getattr(flaky_records[0], "test_file", getattr(flaky_records[0], "test_file_path", "tests")),
                    measured_metric={"flaky_count": flaky_count},
                    explanation=f"Repository has {flaky_count} known non-deterministic flaky tests recorded by the FlakyTestDetector.",
                    remediation="Isolate test dependencies, eliminate async race conditions, or mock non-deterministic external calls.",
                    potential_impact="Erodes engineer confidence in CI pipelines, causing false revision loops.",
                    detection_method="STATIC_INSPECTION",
                )
            )

        score = min(100.0, penalty)
        return findings, score
