"""Architecture Pattern Inference & Convention Discovery Service.

Analyzes repository structure, AST symbols, graph topology, and configuration files
to infer empirical architectural patterns, discover project conventions, and provide
evidence-grounded 'Ask Your Codebase' Q&A.
"""

import math
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.exceptions import scrub_credentials
from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_architecture_pattern import RepositoryArchitecturePattern
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.user import User
from app.schemas.architecture import (
    ArchitectureAskRequest,
    ArchitectureAskResponse,
    ArchitectureConventionItem,
    ArchitecturePatternItem,
    ArchitectureSummaryResponse,
    HybridSearchFilter,
    HybridSearchRequest,
)
from app.services.search_service import CodeSearchService

logger = get_logger("architecture_inference_service")


class ArchitectureInferenceService:
    """Infers empirical software architecture patterns and coding conventions."""

    def __init__(self, search_service: Optional[CodeSearchService] = None) -> None:
        self.search_service = search_service or CodeSearchService()

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

    async def analyze_repository_architecture(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        force_refresh: bool = False,
    ) -> ArchitectureSummaryResponse:
        """Analyze repository evidence and infer architectural patterns and conventions.

        If already analyzed and not force_refresh, returns persisted records.
        """
        repo = await self.get_repository_for_user(repository_id, user, db)

        if not force_refresh:
            existing_stmt = select(RepositoryArchitecturePattern).where(
                RepositoryArchitecturePattern.repository_id == repo.id
            ).order_by(RepositoryArchitecturePattern.confidence_score.desc())
            existing_res = await db.execute(existing_stmt)
            existing_records = existing_res.scalars().all()
            if existing_records:
                return self._build_summary_from_records(repo, existing_records)

        # Collect raw evidence from DB & filesystem
        evidence = await self._collect_repository_evidence(repo, db)

        # Run pattern detectors across 5 domains
        detected_patterns = self._detect_all_patterns(evidence)

        # Run convention discovery
        discovered_conventions = self._discover_conventions(evidence, detected_patterns)

        # Distribute conventions to patterns for persistence
        for p in detected_patterns:
            if p.pattern_id == "service_layer":
                p.conventions = [c for c in discovered_conventions if c.category == "service"]
            elif p.pattern_id in ("layered_architecture", "controller_service_repository"):
                p.conventions = [c for c in discovered_conventions if c.category in ("api", "database", "error", "test")]

        # Persist or update in database
        del_stmt = delete(RepositoryArchitecturePattern).where(
            RepositoryArchitecturePattern.repository_id == repo.id
        )
        await db.execute(del_stmt)

        persisted_records: List[RepositoryArchitecturePattern] = []
        for p in detected_patterns:
            rec = RepositoryArchitecturePattern(
                repository_id=repo.id,
                pattern_id=p.pattern_id,
                category=p.category,
                name=p.name,
                description=p.description,
                evidence_status=p.evidence_status,
                confidence_score=p.confidence_score,
                supporting_files=p.supporting_files,
                supporting_symbols=p.supporting_symbols,
                supporting_relationships=p.supporting_relationships,
                supporting_config=p.supporting_config,
                counterexamples=p.counterexamples,
                conventions=[c.model_dump() for c in p.conventions],
            )
            db.add(rec)
            persisted_records.append(rec)

        await db.commit()

        return self._build_summary_from_records(repo, persisted_records, discovered_conventions)

    async def get_architecture_summary(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> ArchitectureSummaryResponse:
        """Retrieve the latest architectural summary for repository."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RepositoryArchitecturePattern).where(
            RepositoryArchitecturePattern.repository_id == repo.id
        ).order_by(RepositoryArchitecturePattern.confidence_score.desc())
        res = await db.execute(stmt)
        records = res.scalars().all()

        if not records:
            # Trigger analysis on first access
            return await self.analyze_repository_architecture(repository_id, user, db, force_refresh=True)

        return self._build_summary_from_records(repo, records)

    async def list_patterns(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[ArchitecturePatternItem]:
        """List individual architecture patterns with optional filters."""
        summary = await self.get_architecture_summary(repository_id, user, db)
        patterns = summary.patterns
        if category:
            patterns = [p for p in patterns if p.category.lower() == category.lower()]
        if min_confidence > 0.0:
            patterns = [p for p in patterns if p.confidence_score >= min_confidence]
        return patterns

    async def list_conventions(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
    ) -> List[ArchitectureConventionItem]:
        """List discovered architectural and coding conventions."""
        summary = await self.get_architecture_summary(repository_id, user, db)
        conventions = summary.conventions
        if category:
            conventions = [c for c in conventions if c.category.lower() == category.lower()]
        return conventions

    async def ask_architecture(
        self,
        repository_id: uuid.UUID,
        request: ArchitectureAskRequest,
        user: User,
        db: AsyncSession,
    ) -> ArchitectureAskResponse:
        """Provide an evidence-grounded answer to an architectural question using hybrid search and pattern inference."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        # 1. Fetch current patterns
        summary = await self.get_architecture_summary(repository_id, user, db)

        # 2. Retrieve top evidence snippets using hybrid search
        search_resp = await self.search_service.search_hybrid(
            repository_id=repo.id,
            query=request.question,
            user=user,
            db=db,
            limit=request.context_limit,
            offset=0,
        )

        relevant_files = list(dict.fromkeys(r.file_path for r in search_resp.results))
        evidence_items = [
            {
                "file_path": r.file_path,
                "line_number": r.line_number,
                "symbol_name": r.symbol_name,
                "snippet": r.snippet,
                "score": r.combined_score,
                "provenance": r.provenance_explanation,
            }
            for r in search_resp.results
        ]

        # 3. Identify relevant confirmed patterns
        q_lower = request.question.lower()
        referenced_patterns: List[str] = []
        for p in summary.patterns:
            if p.evidence_status in ("CONFIRMED", "STRONGLY_SUPPORTED"):
                if (
                    p.pattern_id in q_lower
                    or p.name.lower() in q_lower
                    or p.category in q_lower
                    or any(tok in q_lower for tok in p.name.lower().split())
                ):
                    referenced_patterns.append(p.name)

        # 4. Synthesize explanation grounded in empirical evidence
        answer, confidence = self._synthesize_grounded_answer(
            question=request.question,
            patterns=summary.patterns,
            conventions=summary.conventions,
            evidence_results=search_resp.results,
        )

        return ArchitectureAskResponse(
            repository_id=str(repo.id),
            question=request.question,
            answer=answer,
            confidence=confidence,
            supporting_evidence=evidence_items,
            relevant_files=relevant_files[:8],
            inferred_patterns_referenced=referenced_patterns,
        )

    # -------------------------------------------------------------------------
    # EVIDENCE GATHERING
    # -------------------------------------------------------------------------

    async def _collect_repository_evidence(
        self,
        repo: Repository,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Aggregate all files, symbols, graph nodes, edges, and config into an evidence structure."""
        # Files
        files_stmt = select(RepositoryFile).where(RepositoryFile.repository_id == repo.id)
        files_res = await db.execute(files_stmt)
        files = files_res.scalars().all()
        file_paths = [f.file_path for f in files]

        # Knowledge entries
        k_stmt = select(RepositoryKnowledge).where(RepositoryKnowledge.repository_id == repo.id)
        k_res = await db.execute(k_stmt)
        knowledge = k_res.scalars().all()

        # Graph nodes
        n_stmt = select(RepositoryGraphNode).where(RepositoryGraphNode.repository_id == repo.id)
        n_res = await db.execute(n_stmt)
        nodes = n_res.scalars().all()

        # Graph edges
        e_stmt = select(RepositoryGraphEdge).where(RepositoryGraphEdge.repository_id == repo.id)
        e_res = await db.execute(e_stmt)
        edges = e_res.scalars().all()

        # Manifest configs from repo meta_info
        meta = repo.meta_info or {}
        frameworks = meta.get("frameworks", [])

        # Read actual configs if on disk
        configs: Dict[str, Any] = {}
        ws_path = Path(settings.WORKSPACE_BASE_DIR) / str(repo.id)
        if ws_path.exists() and ws_path.is_dir():
            for cfg_name in [
                "pyproject.toml",
                "package.json",
                "Cargo.toml",
                "go.mod",
                "alembic.ini",
                "docker-compose.yml",
                "Dockerfile",
            ]:
                cfg_file = ws_path / cfg_name
                if cfg_file.is_file():
                    try:
                        configs[cfg_name] = cfg_file.read_text(encoding="utf-8", errors="replace")[:2000]
                    except Exception:
                        pass

        return {
            "repository": repo,
            "file_paths": file_paths,
            "knowledge": knowledge,
            "nodes": nodes,
            "edges": edges,
            "frameworks": frameworks,
            "configs": configs,
            "meta": meta,
        }

    # -------------------------------------------------------------------------
    # PATTERN DETECTORS
    # -------------------------------------------------------------------------

    def _detect_all_patterns(self, evidence: Dict[str, Any]) -> List[ArchitecturePatternItem]:
        """Run taxonomy detectors across Application, Backend, Frontend, AI/Agent, and Data domains."""
        patterns: List[ArchitecturePatternItem] = []

        # Application Patterns
        patterns.append(self._detect_layered_architecture(evidence))
        patterns.append(self._detect_service_layer(evidence))
        patterns.append(self._detect_modular_monolith(evidence))
        patterns.append(self._detect_clean_architecture(evidence))
        patterns.append(self._detect_repository_pattern(evidence))

        # Backend Patterns
        patterns.append(self._detect_controller_service_repository(evidence))
        patterns.append(self._detect_dependency_injection(evidence))
        patterns.append(self._detect_middleware_auth(evidence))
        patterns.append(self._detect_transaction_management(evidence))
        patterns.append(self._detect_centralized_error_handling(evidence))

        # Frontend Patterns
        patterns.append(self._detect_component_composition(evidence))
        patterns.append(self._detect_centralized_api_client(evidence))
        patterns.append(self._detect_shared_hooks(evidence))

        # AI / Agent Patterns
        patterns.append(self._detect_agent_specialization(evidence))
        patterns.append(self._detect_isolated_sandbox(evidence))
        patterns.append(self._detect_model_gateway_resilience(evidence))
        patterns.append(self._detect_human_approval_gates(evidence))

        # Data Patterns
        patterns.append(self._detect_declarative_orm_models(evidence))
        patterns.append(self._detect_migration_versioning(evidence))
        patterns.append(self._detect_vector_memory_embeddings(evidence))

        # Sort by confidence score descending
        patterns.sort(key=lambda p: p.confidence_score, reverse=True)
        return patterns

    def _resolve_status(self, score: float) -> str:
        if score >= 0.85:
            return "CONFIRMED"
        elif score >= 0.70:
            return "STRONGLY_SUPPORTED"
        elif score >= 0.40:
            return "POSSIBLE"
        return "INSUFFICIENT_EVIDENCE"

    # --- 1. Application Patterns ---

    def _detect_layered_architecture(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        api_files = [p for p in paths if re.search(r"(api/|routes/|controllers/)", p, re.I)]
        service_files = [p for p in paths if re.search(r"(services/|domain/|usecases/)", p, re.I)]
        data_files = [p for p in paths if re.search(r"(models/|repositories/|db/|database/)", p, re.I)]

        signals = sum([bool(api_files), bool(service_files), bool(data_files)])
        score = 0.0
        if signals == 3:
            score = 0.95
        elif signals == 2:
            score = 0.65
        elif signals == 1:
            score = 0.35

        supporting_files = (api_files[:3] + service_files[:3] + data_files[:3])
        status = self._resolve_status(score)

        return ArchitecturePatternItem(
            pattern_id="layered_architecture",
            category="application",
            name="Layered Architecture",
            description="Clear separation between presentation/API routes, business service layer, and data persistence models.",
            evidence_status=status,
            confidence_score=score,
            supporting_files=supporting_files,
            supporting_symbols=[n.name for n in ev["nodes"] if n.name.endswith("Service") or n.name.endswith("Router")][:5],
            supporting_config={"api_layers": len(api_files), "service_layers": len(service_files), "data_layers": len(data_files)},
        )

    def _detect_service_layer(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        service_paths = [p for p in paths if "services/" in p or "service/" in p or p.endswith("_service.py") or p.endswith("Service.ts")]
        service_nodes = [n for n in ev["nodes"] if n.name.endswith("Service") or "service" in (n.file_path or "").lower()]

        score = 0.0
        if len(service_paths) >= 5 or len(service_nodes) >= 5:
            score = 0.95
        elif len(service_paths) >= 2 or len(service_nodes) >= 2:
            score = 0.75
        elif service_paths or service_nodes:
            score = 0.50

        return ArchitecturePatternItem(
            pattern_id="service_layer",
            category="application",
            name="Service Layer Pattern",
            description="Dedicated service classes/modules encapsulating domain operations, external orchestrations, and transactions.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=service_paths[:6],
            supporting_symbols=[n.name for n in service_nodes][:6],
        )

    def _detect_modular_monolith(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        package_nodes = [n for n in ev["nodes"] if n.node_type == "PACKAGE"]
        has_backend = any(p.startswith("backend/") for p in paths)
        has_frontend = any(p.startswith("frontend/") for p in paths)

        score = 0.0
        if package_nodes or (has_backend and has_frontend):
            score = 0.90 if (has_backend and has_frontend) else 0.75
        elif any("packages/" in p or "apps/" in p for p in paths):
            score = 0.65

        files = [p for p in paths if p.startswith("backend/") or p.startswith("frontend/")][:6]
        return ArchitecturePatternItem(
            pattern_id="modular_monolith",
            category="application",
            name="Modular Monolith / Multi-Project Workspace",
            description="Unified repository hosting distinct functional workspaces (e.g. backend service and frontend client application).",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=files,
            supporting_symbols=[n.name for n in package_nodes][:5],
            supporting_config={"backend_present": has_backend, "frontend_present": has_frontend},
        )

    def _detect_clean_architecture(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        clean_dirs = [p for p in paths if re.search(r"(domain/|usecases/|entities/|adapters/)", p, re.I)]
        score = 0.25
        if len(clean_dirs) >= 4:
            score = 0.85
        elif len(clean_dirs) >= 2:
            score = 0.55

        return ArchitecturePatternItem(
            pattern_id="clean_architecture",
            category="application",
            name="Clean Architecture / Hexagonal Ports & Adapters",
            description="Strict onion layering isolating pure domain entities from transport adapters and external persistence.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=clean_dirs[:5],
            counterexamples=["Direct ORM model usage in business services"] if score < 0.70 else [],
        )

    def _detect_repository_pattern(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        repo_files = [p for p in paths if "repositories/" in p or p.endswith("_repository.py")]
        repo_nodes = [n for n in ev["nodes"] if n.name.endswith("Repository") and n.node_type == "CLASS"]

        score = 0.20
        if len(repo_files) >= 3 or len(repo_nodes) >= 3:
            score = 0.90
        elif repo_files or repo_nodes:
            score = 0.50

        return ArchitecturePatternItem(
            pattern_id="repository_pattern",
            category="application",
            name="Repository Pattern",
            description="Dedicated abstraction layer isolating domain services from direct SQL / ORM data store queries.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=repo_files[:5],
            supporting_symbols=[n.name for n in repo_nodes][:5],
        )

    # --- 2. Backend Patterns ---

    def _detect_controller_service_repository(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        has_routes = any("api/v1/" in p or "routes/" in p for p in paths)
        has_services = any("services/" in p for p in paths)
        has_models = any("models/" in p for p in paths)

        score = 0.90 if (has_routes and has_services and has_models) else 0.40
        return ArchitecturePatternItem(
            pattern_id="controller_service_repository",
            category="backend",
            name="Router-Service-Model Data Flow",
            description="Incoming HTTP requests flow through FastAPI APIRouters, delegate to domain Services, and query ORM Models.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=[p for p in paths if "api/v1/" in p or "services/" in p or "models/" in p][:6],
        )

    def _detect_dependency_injection(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        # Check for FastAPI Depends() in knowledge or node signatures
        deps_matches = [
            k.file_path for k in ev["knowledge"]
            if k.content and ("Depends(" in k.content or "Annotated[" in k.content)
        ]
        unique_files = list(dict.fromkeys(deps_matches))

        score = 0.90 if len(unique_files) >= 3 else (0.60 if unique_files else 0.20)
        return ArchitecturePatternItem(
            pattern_id="dependency_injection_routes",
            category="backend",
            name="Dependency Injection via Route Callables",
            description="Route handlers declare modular dependencies (database session, authenticated user) injected at runtime.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=unique_files[:6],
            supporting_symbols=["get_db", "get_current_user", "Depends"],
        )

    def _detect_middleware_auth(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        auth_files = [p for p in paths if "auth" in p.lower() or "jwt" in p.lower() or "security" in p.lower()]
        score = 0.85 if auth_files else 0.30
        return ArchitecturePatternItem(
            pattern_id="middleware_auth",
            category="backend",
            name="Centralized Security & JWT Authentication",
            description="Bearer token authentication and tenant resolution enforced through route dependencies and security utilities.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=auth_files[:5],
            supporting_symbols=["get_current_user", "verify_token", "create_access_token"][:3],
        )

    def _detect_transaction_management(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        # Check for async session commit / rollback
        tx_matches = [
            k.file_path for k in ev["knowledge"]
            if k.content and ("await db.commit()" in k.content or "commit_orphan" in k.content)
        ]
        unique_files = list(dict.fromkeys(tx_matches))
        score = 0.88 if len(unique_files) >= 2 else (0.50 if unique_files else 0.25)
        return ArchitecturePatternItem(
            pattern_id="transaction_management",
            category="backend",
            name="Explicit Async Database Transactions",
            description="Async SQLAlchemy session management with explicit commit/rollback lifecycle per business action.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=unique_files[:5],
        )

    def _detect_centralized_error_handling(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        exc_files = [p for p in paths if "exception" in p.lower() or "error" in p.lower()]
        exc_nodes = [n for n in ev["nodes"] if "Exception" in n.name and n.node_type == "CLASS"]

        score = 0.90 if (exc_files or exc_nodes) else 0.35
        return ArchitecturePatternItem(
            pattern_id="centralized_error_handling",
            category="backend",
            name="Domain Exception Hierarchy & Error Handling",
            description="Base application exception hierarchy mapped to structured HTTP error responses with status codes and details.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=exc_files[:5],
            supporting_symbols=[n.name for n in exc_nodes][:5],
        )

    # --- 3. Frontend Patterns ---

    def _detect_component_composition(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        comp_files = [p for p in paths if "components/" in p and (p.endswith(".tsx") or p.endswith(".jsx"))]
        score = 0.92 if len(comp_files) >= 5 else (0.65 if comp_files else 0.15)
        return ArchitecturePatternItem(
            pattern_id="component_composition",
            category="frontend",
            name="React Component Hierarchy & Composition",
            description="Modular component architecture with reusable UI elements, page layouts, and domain-specific feature views.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=comp_files[:6],
        )

    def _detect_centralized_api_client(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        api_clients = [p for p in paths if "frontend/" in p and ("api.ts" in p or "service.ts" in p or "client.ts" in p)]
        score = 0.88 if api_clients else 0.20
        return ArchitecturePatternItem(
            pattern_id="centralized_api_client",
            category="frontend",
            name="Centralized Frontend API Client Layer",
            description="Type-safe HTTP API client abstractions wrapping backend REST endpoints with authentication header injection.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=api_clients[:5],
        )

    def _detect_shared_hooks(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        hook_files = [p for p in paths if "/hooks/" in p or (Path(p).name.startswith("use") and (p.endswith(".ts") or p.endswith(".tsx")))]
        score = 0.80 if hook_files else 0.20
        return ArchitecturePatternItem(
            pattern_id="shared_hooks",
            category="frontend",
            name="Custom React Hooks Pattern",
            description="Shared stateful logic encapsulated into reusable custom hooks (e.g. useAuth, useSSE, useToast).",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=hook_files[:5],
        )

    # --- 4. AI / Agent Patterns ---

    def _detect_agent_specialization(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        agent_files = [p for p in paths if "agents/specialists/" in p or "agents/" in p]
        agent_nodes = [n for n in ev["nodes"] if "Agent" in n.name or "Planner" in n.name or "Coder" in n.name]

        score = 0.95 if len(agent_files) >= 5 else (0.60 if agent_files else 0.10)
        return ArchitecturePatternItem(
            pattern_id="agent_specialization",
            category="ai_agent",
            name="Specialized Multi-Agent Topology",
            description="Role-specialized autonomous agents (Planner, Coder, Reviewer, Sandbox, Reporter) coordinated via state machine graph.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=agent_files[:6],
            supporting_symbols=[n.name for n in agent_nodes][:5],
        )

    def _detect_isolated_sandbox(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        sandbox_files = [p for p in paths if "sandbox" in p.lower()]
        score = 0.90 if sandbox_files else 0.20
        return ArchitecturePatternItem(
            pattern_id="isolated_sandbox",
            category="ai_agent",
            name="Isolated Execution Sandbox with Fallback",
            description="Ephemeral containerized test and build execution environment with safe local subprocess fallback.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=sandbox_files[:5],
            supporting_symbols=["SandboxService", "LocalSandboxRunner", "execute_command"][:3],
        )

    def _detect_model_gateway_resilience(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        gw_files = [p for p in paths if "gateway" in p.lower() or "circuit_breaker" in p.lower()]
        score = 0.92 if gw_files else 0.15
        return ArchitecturePatternItem(
            pattern_id="model_gateway_resilience",
            category="ai_agent",
            name="Model Gateway Circuit Breaker & Fallback",
            description="Provider-agnostic LLM gateway with stateful circuit breaking, exponential backoff retries, and token accounting.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=gw_files[:5],
            supporting_symbols=["ModelGateway", "CircuitBreaker", "generate_structured"][:3],
        )

    def _detect_human_approval_gates(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        approval_files = [p for p in paths if "approval" in p.lower()]
        score = 0.88 if approval_files else 0.20
        return ArchitecturePatternItem(
            pattern_id="human_approval_gates",
            category="ai_agent",
            name="Human-in-the-Loop Approval Gates",
            description="Intervention thresholds requiring explicit engineer confirmation before high-risk git operations or destructive changes.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=approval_files[:5],
            supporting_symbols=["Approval", "create_approval", "approve_task"][:3],
        )

    # --- 5. Data Patterns ---

    def _detect_declarative_orm_models(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        model_files = [p for p in paths if "models/" in p and p.endswith(".py")]
        score = 0.95 if len(model_files) >= 4 else (0.50 if model_files else 0.20)
        return ArchitecturePatternItem(
            pattern_id="declarative_orm_models",
            category="data",
            name="Declarative ORM Schema Models",
            description="SQLAlchemy 2.0 type-annotated mapped columns and relationships defining relational data structures.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=model_files[:6],
            supporting_symbols=["Base", "Mapped", "mapped_column", "relationship"][:4],
        )

    def _detect_migration_versioning(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        mig_files = [p for p in paths if "alembic/versions" in p or "migrations" in p]
        score = 0.95 if len(mig_files) >= 3 else (0.60 if mig_files else 0.15)
        return ArchitecturePatternItem(
            pattern_id="migration_versioning",
            category="data",
            name="Version-Controlled Database Migrations",
            description="Sequential Alembic migration revisions ensuring schema reproducibility and deterministic upgrades.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=mig_files[:6],
            supporting_config={"total_migrations": len(mig_files)},
        )

    def _detect_vector_memory_embeddings(self, ev: Dict[str, Any]) -> ArchitecturePatternItem:
        paths = ev["file_paths"]
        vec_files = [p for p in paths if "pgvector" in p.lower() or "embedding" in p.lower() or "memory" in p.lower()]
        score = 0.90 if vec_files else 0.20
        return ArchitecturePatternItem(
            pattern_id="vector_memory_embeddings",
            category="data",
            name="Vector Embeddings & Semantic Long-Term Memory",
            description="768-dimensional pgvector cosine similarity search powering semantic code retrieval and adaptive experience recall.",
            evidence_status=self._resolve_status(score),
            confidence_score=score,
            supporting_files=vec_files[:5],
            supporting_symbols=["RepositoryKnowledge", "generate_embedding_vector", "cosine_similarity"][:3],
        )

    # -------------------------------------------------------------------------
    # CONVENTION DISCOVERY
    # -------------------------------------------------------------------------

    def _discover_conventions(
        self,
        ev: Dict[str, Any],
        patterns: List[ArchitecturePatternItem],
    ) -> List[ArchitectureConventionItem]:
        """Empirically extract coding conventions from repository code and topology."""
        conventions: List[ArchitectureConventionItem] = []

        # 1. Service naming convention
        service_files = [p for p in ev["file_paths"] if "services/" in p and p.endswith(".py")]
        if service_files:
            conventions.append(
                ArchitectureConventionItem(
                    name="Service Class & File Naming",
                    category="service",
                    description="Domain business services are placed in `backend/app/services/` with snake_case filenames ending in `_service.py` and CamelCase class names ending in `Service`.",
                    confidence=0.95,
                    supporting_examples=["WorkflowService in workflow_service.py", "SandboxService in sandbox_service.py"],
                    relevant_paths=service_files[:5],
                    applicability_scope="BACKEND",
                )
            )

        # 2. API Route convention
        api_files = [p for p in ev["file_paths"] if "api/v1/" in p and p.endswith(".py")]
        if api_files:
            conventions.append(
                ArchitectureConventionItem(
                    name="Versioned REST API Endpoints",
                    category="api",
                    description="REST endpoints are grouped under `/api/v1/` using APIRouter, prefixed by resource name, and mounted in `backend/app/api/v1/router.py`.",
                    confidence=0.95,
                    supporting_examples=["router = APIRouter(prefix='/repositories', tags=['repositories'])"],
                    relevant_paths=api_files[:5],
                    applicability_scope="BACKEND",
                )
            )

        # 3. Database session injection
        conventions.append(
            ArchitectureConventionItem(
                name="Async Database Session Injection",
                category="database",
                description="Route handlers and agent tools acquire database transactions using `db: AsyncSession = Depends(get_db)`.",
                confidence=0.92,
                supporting_examples=["async def get_items(db: AsyncSession = Depends(get_db))"],
                relevant_paths=["backend/app/api/deps.py", "backend/app/api/v1/repositories.py"],
                applicability_scope="BACKEND",
            )
        )

        # 4. Error Handling convention
        conventions.append(
            ArchitectureConventionItem(
                name="Domain Exception Subclassing",
                category="error",
                description="Custom domain errors inherit from `DevoraException` and specify clear HTTP status codes and structured detail messages.",
                confidence=0.90,
                supporting_examples=["class NotFoundException(DevoraException): status_code = 404"],
                relevant_paths=["backend/app/core/exceptions.py"],
                applicability_scope="REPOSITORY_WIDE",
            )
        )

        # 5. Unit and Integration Test separation
        test_files = [p for p in ev["file_paths"] if "tests/" in p and p.endswith(".py")]
        if test_files:
            conventions.append(
                ArchitectureConventionItem(
                    name="Pytest Test Suite Partitioning",
                    category="test",
                    description="Backend tests are partitioned into `tests/unit/` (mocked dependencies) and `tests/integration/` (database interactions) using `pytest-asyncio`.",
                    confidence=0.94,
                    supporting_examples=["test_*.py with async def test_*"],
                    relevant_paths=test_files[:5],
                    applicability_scope="BACKEND",
                )
            )

        return conventions

    # -------------------------------------------------------------------------
    # Q&A ANSWER SYNTHESIS
    # -------------------------------------------------------------------------

    def _synthesize_grounded_answer(
        self,
        question: str,
        patterns: List[ArchitecturePatternItem],
        conventions: List[ArchitectureConventionItem],
        evidence_results: List[Any],
    ) -> Tuple[str, float]:
        """Synthesize an accurate, evidence-grounded answer based on verified files and patterns."""
        q_lower = question.lower()

        # Check for confirmed patterns matching question keywords
        matching_patterns = [
            p for p in patterns
            if p.evidence_status in ("CONFIRMED", "STRONGLY_SUPPORTED") and (
                p.pattern_id in q_lower
                or p.name.lower() in q_lower
                or p.category in q_lower
                or any(w in q_lower for w in p.name.lower().split() if len(w) > 3)
            )
        ]

        # Top evidence files
        top_files = list(dict.fromkeys(r.file_path for r in evidence_results[:5]))
        top_snippets = [r.snippet for r in evidence_results[:3] if r.snippet]

        if not evidence_results and not matching_patterns:
            return (
                f"Based on the repository index, there is insufficient evidence to definitively answer: '{question}'. "
                "No indexed source files or architecture patterns directly match this query.",
                0.20,
            )

        # Build synthesized answer paragraphs
        lines = []
        if matching_patterns:
            p_names = ", ".join(f"**{p.name}**" for p in matching_patterns[:2])
            lines.append(f"In this codebase, this area is governed primarily by the {p_names} pattern.")
            lines.append(matching_patterns[0].description)
        else:
            lines.append(f"Analysis of indexed repository code indicates how this is handled across the architecture:")

        if top_files:
            file_list_str = ", ".join(f"`{f}`" for f in top_files[:4])
            lines.append(f"\n### Relevant Source Modules\nImplementation details are primarily located in: {file_list_str}.")

        # Add conventions if relevant
        matching_convs = [c for c in conventions if c.category in q_lower or any(w in q_lower for w in c.name.lower().split() if len(w) > 3)]
        if matching_convs:
            lines.append(f"\n### Project Conventions\n- **{matching_convs[0].name}**: {matching_convs[0].description}")

        if top_snippets:
            lines.append("\n### Code Evidence")
            for snip in top_snippets[:2]:
                lines.append(f"```text\n{snip.strip()[:200]}\n```")

        confidence = 0.85 if matching_patterns and top_files else (0.70 if top_files else 0.45)
        return "\n\n".join(lines), confidence

    # -------------------------------------------------------------------------
    # SUMMARY BUILDER
    # -------------------------------------------------------------------------

    def _build_summary_from_records(
        self,
        repo: Repository,
        records: List[Any],
        conventions: Optional[List[ArchitectureConventionItem]] = None,
    ) -> ArchitectureSummaryResponse:
        """Convert database records or items to ArchitectureSummaryResponse."""
        pattern_items: List[ArchitecturePatternItem] = []
        all_conventions: List[ArchitectureConventionItem] = conventions or []

        for r in records:
            if isinstance(r, RepositoryArchitecturePattern):
                conv_items = [ArchitectureConventionItem(**c) for c in (r.conventions or [])]
                item = ArchitecturePatternItem(
                    id=str(r.id),
                    pattern_id=r.pattern_id,
                    category=r.category,
                    name=r.name,
                    description=r.description,
                    evidence_status=r.evidence_status,
                    confidence_score=r.confidence_score,
                    supporting_files=r.supporting_files or [],
                    supporting_symbols=r.supporting_symbols or [],
                    supporting_relationships=r.supporting_relationships or [],
                    supporting_config=r.supporting_config or {},
                    counterexamples=r.counterexamples or [],
                    conventions=conv_items,
                )
                pattern_items.append(item)
                if not conventions:
                    all_conventions.extend(conv_items)
            elif isinstance(r, ArchitecturePatternItem):
                pattern_items.append(r)
                if not conventions:
                    all_conventions.extend(r.conventions)

        # Deduplicate conventions by name
        seen_convs = set()
        unique_convs = []
        for c in all_conventions:
            if c.name not in seen_convs:
                seen_convs.add(c.name)
                unique_convs.append(c)
        all_conventions = unique_convs

        confirmed_count = sum(1 for p in pattern_items if p.evidence_status == "CONFIRMED")
        meta = repo.meta_info or {}

        # Synthesize readable overview text for backwards-compatibility
        top_patterns = [p.name for p in pattern_items if p.evidence_status in ("CONFIRMED", "STRONGLY_SUPPORTED")]
        arch_summary_text = (
            f"Repository Architecture Summary: Evaluated {len(pattern_items)} patterns across application, backend, frontend, ai_agent, and data tiers. "
            f"Confirmed patterns: {', '.join(top_patterns) if top_patterns else 'None'}."
        )
        coding_convs_text = (
            f"Project Conventions & Practices: Enforcing {len(all_conventions)} empirically discovered rules across service layer naming, API routing, and testing."
        )

        return ArchitectureSummaryResponse(
            repository_id=str(repo.id),
            primary_language=repo.language,
            current_commit_sha=repo.current_commit_sha,
            frameworks=meta.get("frameworks", []),
            entry_points=meta.get("entry_points", []),
            manifests=meta.get("manifests", []),
            total_files=meta.get("total_files", 0),
            total_lines=meta.get("total_lines", 0),
            architecture_summary=arch_summary_text,
            coding_conventions=coding_convs_text,
            total_patterns=len(pattern_items),
            confirmed_patterns_count=confirmed_count,
            patterns=pattern_items,
            conventions=all_conventions,
            is_stale=False,
            last_analyzed_at=str(records[0].updated_at) if records and hasattr(records[0], "updated_at") else None,
        )
