"""Architecture Drift Detection Engine.

Compares repository implementation against inferred architectural patterns,
detecting layering violations, circular dependencies, package boundary breaches,
convention deviations, and security boundary bypasses.
"""

import ast
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_architecture_drift import RepositoryArchitectureDrift
from app.models.repository_architecture_pattern import RepositoryArchitecturePattern
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User
from app.schemas.drift import ArchitectureDriftResponse, DriftViolationItem
from app.services.architecture_inference_service import ArchitectureInferenceService

logger = get_logger("architecture_drift_service")


class ArchitectureDriftService:
    """Detects deviations from established architectural baselines and coding conventions."""

    def __init__(
        self,
        inference_service: Optional[ArchitectureInferenceService] = None,
    ) -> None:
        self.inference_service = inference_service or ArchitectureInferenceService()

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

    async def analyze_drift(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        baseline_commit_sha: Optional[str] = None,
    ) -> ArchitectureDriftResponse:
        """Execute full architectural drift analysis against baseline patterns and persist snapshot."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        # 1. Fetch established architecture patterns & conventions
        arch_summary = await self.inference_service.get_architecture_summary(repository_id, user, db)
        patterns_map = {p.pattern_id: p for p in arch_summary.patterns}
        conventions = arch_summary.conventions

        # 2. Collect graph nodes, edges, files, and knowledge
        nodes_stmt = select(RepositoryGraphNode).where(RepositoryGraphNode.repository_id == repo.id)
        nodes_res = await db.execute(nodes_stmt)
        nodes = nodes_res.scalars().all()

        edges_stmt = select(RepositoryGraphEdge).where(RepositoryGraphEdge.repository_id == repo.id)
        edges_res = await db.execute(edges_stmt)
        edges = edges_res.scalars().all()

        files_stmt = select(RepositoryFile).where(RepositoryFile.repository_id == repo.id)
        files_res = await db.execute(files_stmt)
        files = files_res.scalars().all()
        file_paths = [f.file_path for f in files]

        k_stmt = select(RepositoryKnowledge).where(RepositoryKnowledge.repository_id == repo.id)
        k_res = await db.execute(k_stmt)
        knowledge = k_res.scalars().all()

        evidence = {
            "repository": repo,
            "patterns": patterns_map,
            "conventions": conventions,
            "nodes": nodes,
            "edges": edges,
            "files": files,
            "file_paths": file_paths,
            "knowledge": knowledge,
        }

        # 3. Execute drift detectors
        violations: List[DriftViolationItem] = []
        violations.extend(self._detect_layering_violations(evidence))
        violations.extend(self._detect_circular_dependencies(evidence))
        violations.extend(self._detect_package_boundary_violations(evidence))
        violations.extend(self._detect_convention_violations(evidence))
        violations.extend(self._detect_security_boundary_violations(evidence))

        # 4. Fetch prior baseline drift snapshot to detect resolved vs new violations
        prev_stmt = (
            select(RepositoryArchitectureDrift)
            .where(RepositoryArchitectureDrift.repository_id == repo.id)
            .order_by(RepositoryArchitectureDrift.created_at.desc())
            .limit(1)
        )
        prev_res = await db.execute(prev_stmt)
        prev_snapshot = prev_res.scalar_one_or_none()

        resolved_violations: List[DriftViolationItem] = []
        if prev_snapshot and prev_snapshot.violations:
            curr_rule_files = {(v.rule_id, v.source_file) for v in violations}
            for prev_v_dict in prev_snapshot.violations:
                p_item = DriftViolationItem(**prev_v_dict)
                if (p_item.rule_id, p_item.source_file) not in curr_rule_files:
                    resolved_violations.append(p_item)

        # 5. Determine overall drift status
        critical_count = sum(1 for v in violations if v.severity == "CRITICAL")
        high_count = sum(1 for v in violations if v.severity == "HIGH")
        medium_count = sum(1 for v in violations if v.severity == "MEDIUM")
        low_count = sum(1 for v in violations if v.severity == "LOW")

        drift_status = self._determine_drift_status(violations)

        summary_metrics = {
            "total_violations": len(violations),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "resolved_count": len(resolved_violations),
            "dominant_category": self._find_dominant_category(violations),
        }

        # 6. Persist snapshot
        rec = RepositoryArchitectureDrift(
            repository_id=repo.id,
            commit_sha=repo.current_commit_sha,
            baseline_commit_sha=baseline_commit_sha or (prev_snapshot.commit_sha if prev_snapshot else repo.current_commit_sha),
            drift_status=drift_status,
            total_violations=len(violations),
            critical_violations=critical_count,
            high_violations=high_count,
            medium_violations=medium_count,
            low_violations=low_count,
            violations=[v.model_dump() for v in violations],
            resolved_violations=[v.model_dump() for v in resolved_violations],
            summary=summary_metrics,
        )
        db.add(rec)
        await db.commit()

        return ArchitectureDriftResponse(
            repository_id=str(repo.id),
            commit_sha=repo.current_commit_sha,
            baseline_commit_sha=rec.baseline_commit_sha,
            drift_status=drift_status,
            total_violations=len(violations),
            critical_violations=critical_count,
            high_violations=high_count,
            medium_violations=medium_count,
            low_violations=low_count,
            violations=violations,
            resolved_violations=resolved_violations,
            summary=summary_metrics,
            is_stale=False,
            last_analyzed_at=str(rec.created_at),
        )

    async def get_drift_summary(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> ArchitectureDriftResponse:
        """Fetch latest drift analysis snapshot, or run on-demand if none exists."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = (
            select(RepositoryArchitectureDrift)
            .where(RepositoryArchitectureDrift.repository_id == repo.id)
            .order_by(RepositoryArchitectureDrift.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        snapshot = res.scalar_one_or_none()

        if not snapshot:
            return await self.analyze_drift(repository_id, user, db)

        violations = [DriftViolationItem(**v) for v in (snapshot.violations or [])]
        resolved = [DriftViolationItem(**v) for v in (snapshot.resolved_violations or [])]

        return ArchitectureDriftResponse(
            repository_id=str(repo.id),
            commit_sha=snapshot.commit_sha,
            baseline_commit_sha=snapshot.baseline_commit_sha,
            drift_status=snapshot.drift_status,
            total_violations=snapshot.total_violations,
            critical_violations=snapshot.critical_violations,
            high_violations=snapshot.high_violations,
            medium_violations=snapshot.medium_violations,
            low_violations=snapshot.low_violations,
            violations=violations,
            resolved_violations=resolved,
            summary=snapshot.summary or {},
            is_stale=bool(repo.current_commit_sha and snapshot.commit_sha and snapshot.commit_sha != repo.current_commit_sha),
            last_analyzed_at=str(snapshot.created_at),
        )

    # -------------------------------------------------------------------------
    # DRIFT DETECTORS
    # -------------------------------------------------------------------------

    def _determine_drift_status(self, violations: List[Any]) -> str:
        """Calculate overall drift status based on violation severity distribution."""
        def get_sev(v: Any) -> str:
            if hasattr(v, "severity"):
                return str(v.severity).upper()
            if isinstance(v, dict):
                return str(v.get("severity", "")).upper()
            return ""

        critical_count = sum(1 for v in violations if get_sev(v) == "CRITICAL")
        high_count = sum(1 for v in violations if get_sev(v) == "HIGH")
        medium_count = sum(1 for v in violations if get_sev(v) == "MEDIUM")
        low_count = sum(1 for v in violations if get_sev(v) == "LOW")

        if critical_count > 0 or high_count >= 3:
            return "CRITICAL_DRIFT"
        elif (high_count + medium_count + low_count) > 0:
            return "DRIFT_DETECTED"
        return "HEALTHY"

    def _detect_layering_violations(self, ev: Dict[str, Any]) -> List[DriftViolationItem]:
        """Detect Presentation -> Database direct access bypassing Service layer."""
        violations: List[DriftViolationItem] = []
        knowledge = ev["knowledge"]

        # Check API routes for direct DB queries or raw SQL execution
        for k in knowledge:
            fpath = k.file_path or ""
            content = k.content or ""
            if not ("api/v1/" in fpath or "routes/" in fpath or "controllers/" in fpath):
                continue

            # Check if route directly executes select(...) or raw SQL queries bypassing service
            has_direct_query = (
                "await db.execute(select(" in content
                or "db.execute(text(" in content
                or "db.scalars(" in content
            )
            has_service_delegation = (
                "Service(" in content
                or "_service." in content
                or "Service." in content
            )

            if has_direct_query and not has_service_delegation:
                violations.append(
                    DriftViolationItem(
                        id=f"layering_{uuid.uuid4().hex[:8]}",
                        rule_id="layering_violation",
                        category="layering",
                        name="Direct Database Query in API Route",
                        severity="HIGH",
                        confidence=0.92,
                        source_file=fpath,
                        source_symbol=k.symbol_name,
                        line_number=(k.meta_info or {}).get("start_line", 1),
                        explanation=(
                            f"API route handler '{k.symbol_name or fpath}' directly executes database queries "
                            "without delegating to a domain Service layer, violating the Router-Service-Model architecture pattern."
                        ),
                        remediation_recommendation=(
                            "Encapsulate the database query inside a dedicated service in `backend/app/services/` "
                            "and call the service method from the route handler."
                        ),
                        evidence_snippet=content[:250],
                    )
                )

        return violations

    def _detect_circular_dependencies(self, ev: Dict[str, Any]) -> List[DriftViolationItem]:
        """Detect circular dependencies between modules or packages using cycle detection."""
        violations: List[DriftViolationItem] = []
        edges = ev["edges"]
        nodes_by_id = {n.id: n for n in ev["nodes"]}

        # Build adjacency graph of IMPORTS, DEPENDS_ON, PACKAGE_DEPENDS_ON edges
        adj: Dict[uuid.UUID, Set[uuid.UUID]] = {}
        for e in edges:
            if e.edge_type in ("IMPORTS", "DEPENDS_ON", "PACKAGE_DEPENDS_ON") and e.target_node_id:
                if e.source_node_id != e.target_node_id:
                    adj.setdefault(e.source_node_id, set()).add(e.target_node_id)

        # Detect 2-cycles (A -> B and B -> A)
        visited_pairs: Set[Tuple[uuid.UUID, uuid.UUID]] = set()
        for u, neighbors in adj.items():
            for v in neighbors:
                if v in adj and u in adj[v]:
                    pair_key = (min(u, v), max(u, v))
                    if pair_key not in visited_pairs:
                        visited_pairs.add(pair_key)
                        node_u = nodes_by_id.get(u)
                        node_v = nodes_by_id.get(v)
                        if node_u and node_v:
                            file_u = node_u.file_path or node_u.name
                            file_v = node_v.file_path or node_v.name
                            violations.append(
                                DriftViolationItem(
                                    id=f"cycle_{uuid.uuid4().hex[:8]}",
                                    rule_id="circular_dependency",
                                    category="dependency",
                                    name="Circular Dependency Cycle",
                                    severity="CRITICAL",
                                    confidence=0.98,
                                    source_file=file_u,
                                    target_file=file_v,
                                    source_symbol=node_u.name,
                                    target_symbol=node_v.name,
                                    explanation=(
                                        f"Mutual circular dependency detected between '{node_u.name}' ({file_u}) "
                                        f"and '{node_v.name}' ({file_v}). Circular imports degrade modularity and risk runtime ImportError."
                                    ),
                                    remediation_recommendation=(
                                        "Extract shared interfaces, types, or utilities into a common lower-tier module "
                                        "or inject dependencies via callables to break the cycle."
                                    ),
                                )
                            )

        return violations

    def _detect_package_boundary_violations(self, ev: Dict[str, Any]) -> List[DriftViolationItem]:
        """Detect cross-package encapsulation breaches (e.g. importing private internals)."""
        violations: List[DriftViolationItem] = []
        edges = ev["edges"]
        nodes_by_id = {n.id: n for n in ev["nodes"]}

        for e in edges:
            if e.edge_type in ("IMPORTS", "DEPENDS_ON") and e.target_node_id:
                src_node = nodes_by_id.get(e.source_node_id)
                tgt_node = nodes_by_id.get(e.target_node_id)
                if not src_node or not tgt_node:
                    continue

                src_pkg = (src_node.meta_info or {}).get("package_name")
                tgt_pkg = (tgt_node.meta_info or {}).get("package_name")

                # If crossing package boundaries
                if src_pkg and tgt_pkg and src_pkg != tgt_pkg:
                    tgt_path = tgt_node.file_path or ""
                    # If target is a private internal file (e.g. inside /internal/, /private/, or starting with _)
                    if "/internal/" in tgt_path or "/private/" in tgt_path or Path(tgt_path).name.startswith("_"):
                        violations.append(
                            DriftViolationItem(
                                id=f"boundary_{uuid.uuid4().hex[:8]}",
                                rule_id="package_boundary",
                                category="dependency",
                                name="Forbidden Cross-Package Internal Import",
                                severity="HIGH",
                                confidence=0.90,
                                source_file=src_node.file_path or src_node.name,
                                target_file=tgt_path,
                                source_symbol=src_node.name,
                                target_symbol=tgt_node.name,
                                explanation=(
                                    f"Package '{src_pkg}' directly imports internal private module '{tgt_path}' from package '{tgt_pkg}', "
                                    "violating monorepo package encapsulation."
                                ),
                                remediation_recommendation=(
                                    f"Export the required symbol via package '{tgt_pkg}' public barrel/index export or public API."
                                ),
                            )
                        )

        return violations

    def _detect_convention_violations(self, ev: Dict[str, Any]) -> List[DriftViolationItem]:
        """Detect violations of discovered coding conventions."""
        violations: List[DriftViolationItem] = []
        paths = ev["file_paths"]
        nodes = ev["nodes"]

        # 1. Service class naming convention: classes in services/ must end with 'Service'
        for n in nodes:
            fpath = n.file_path or ""
            if "services/" in fpath and n.node_type == "CLASS":
                if not n.name.endswith("Service") and not n.name.endswith("Base"):
                    violations.append(
                        DriftViolationItem(
                            id=f"conv_svc_{uuid.uuid4().hex[:8]}",
                            rule_id="convention_deviation",
                            category="convention",
                            name="Non-Conforming Service Class Naming",
                            severity="MEDIUM",
                            confidence=0.88,
                            source_file=fpath,
                            source_symbol=n.name,
                            line_number=n.start_line or 1,
                            explanation=(
                                f"Class '{n.name}' in '{fpath}' does not follow the project convention of suffixing service classes with 'Service'."
                            ),
                            remediation_recommendation=f"Rename '{n.name}' to '{n.name}Service' to conform to repository naming standards.",
                        )
                    )

        # 2. API route versioning convention: route files under app/api/ must be under /api/v1/
        for p in paths:
            if "app/api/" in p and p.endswith(".py") and not p.endswith("__init__.py") and not p.endswith("deps.py"):
                if not ("api/v1/" in p or "app/api/v1" in p):
                    violations.append(
                        DriftViolationItem(
                            id=f"conv_api_{uuid.uuid4().hex[:8]}",
                            rule_id="convention_deviation",
                            category="convention",
                            name="Unversioned API Route Module",
                            severity="MEDIUM",
                            confidence=0.85,
                            source_file=p,
                            explanation=(
                                f"API route file '{p}' is not located in the versioned `/api/v1/` directory hierarchy."
                            ),
                            remediation_recommendation="Relocate API route modules under `backend/app/api/v1/`.",
                        )
                    )

        return violations

    def _detect_security_boundary_violations(self, ev: Dict[str, Any]) -> List[DriftViolationItem]:
        """Detect violations of security-sensitive boundaries (bypassing ModelGateway, auth, sandbox)."""
        violations: List[DriftViolationItem] = []
        knowledge = ev["knowledge"]

        for k in knowledge:
            fpath = k.file_path or ""
            content = k.content or ""

            # Check for direct LLM calls bypassing ModelGateway
            if "app/agents/" in fpath and not ("gateway" in fpath or "test_" in fpath):
                has_direct_llm = (
                    "google.generativeai" in content
                    or "openai.ChatCompletion" in content
                    or "anthropic.Client" in content
                )
                if has_direct_llm:
                    violations.append(
                        DriftViolationItem(
                            id=f"sec_gw_{uuid.uuid4().hex[:8]}",
                            rule_id="security_boundary",
                            category="security",
                            name="Bypassing ModelGateway for LLM Call",
                            severity="CRITICAL",
                            confidence=0.95,
                            source_file=fpath,
                            source_symbol=k.symbol_name,
                            line_number=(k.meta_info or {}).get("start_line", 1),
                            explanation=(
                                f"Module '{fpath}' directly instantiates third-party LLM SDKs rather than routing requests through ModelGateway. "
                                "This bypasses circuit breaking, retries, fallback providers, and token accounting."
                            ),
                            remediation_recommendation="Route all LLM invocations through `ModelGateway.get_instance().generate_structured()`.",
                            evidence_snippet=content[:200],
                        )
                    )

        return violations

    def _find_dominant_category(self, violations: List[DriftViolationItem]) -> str:
        if not violations:
            return "none"
        counts: Dict[str, int] = {}
        for v in violations:
            counts[v.category] = counts.get(v.category, 0) + 1
        return max(counts.items(), key=lambda x: x[1])[0]
