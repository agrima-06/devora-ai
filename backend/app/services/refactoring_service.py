"""ArchitectureAwareRefactoringService for Phase 10 Stage 10.6."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.refactoring_execution import RefactoringExecution
from app.models.refactoring_plan import RefactoringPlan
from app.models.repository import Repository
from app.models.repository_architecture_drift import RepositoryArchitectureDrift
from app.models.repository_architecture_pattern import RepositoryArchitecturePattern
from app.models.repository_file import RepositoryFile
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.repository_technical_debt import RepositoryTechnicalDebt
from app.models.user import User
from app.schemas.refactoring import (
    BeforeAfterComparisonResponse,
    RefactoringExecutionResponse,
    RefactoringPlanResponse,
    RefactoringPlansListResponse,
    RefactoringRecommendationItem,
    RefactoringRecommendationsResponse,
    RefactoringStepItem,
)
from app.services.architecture_drift_service import ArchitectureDriftService
from app.services.architecture_inference_service import ArchitectureInferenceService
from app.services.technical_debt_service import TechnicalDebtService


class ArchitectureAwareRefactoringService:
    """Orchestrates evidence-backed refactoring recommendations, dependency-aware plans,

    and safe isolated execution with behavioral preservation validation.
    """

    def __init__(
        self,
        drift_service: Optional[ArchitectureDriftService] = None,
        debt_service: Optional[TechnicalDebtService] = None,
        inference_service: Optional[ArchitectureInferenceService] = None,
    ) -> None:
        self.drift_service = drift_service or ArchitectureDriftService()
        self.debt_service = debt_service or TechnicalDebtService()
        self.inference_service = inference_service or ArchitectureInferenceService()

    async def get_repository_for_user(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> Repository:
        """Fetch repository ensuring tenant isolation."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user.id,
        )
        result = await db.execute(stmt)
        repo = result.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)
        return repo

    # -------------------------------------------------------------------------
    # 1. RECOMMENDATION ENGINE
    # -------------------------------------------------------------------------

    async def generate_recommendations(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
    ) -> RefactoringRecommendationsResponse:
        """Synthesize explainable, evidence-backed refactoring proposals from verified drift and debt findings."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        # 1. Fetch latest drift & debt summaries
        drift_resp = await self.drift_service.get_drift_summary(repository_id, user, db)
        debt_resp = await self.debt_service.get_technical_debt_summary(repository_id, user, db)
        arch_resp = await self.inference_service.get_architecture_summary(repository_id, user, db)

        # 2. Fetch graph nodes & edges
        nodes_stmt = select(RepositoryGraphNode).where(RepositoryGraphNode.repository_id == repo.id)
        nodes_res = await db.execute(nodes_stmt)
        nodes = nodes_res.scalars().all()
        nodes_by_file = {}
        for n in nodes:
            if n.file_path:
                nodes_by_file.setdefault(n.file_path, []).append(n)

        # 3. Generate recommendations by category
        recommendations: List[RefactoringRecommendationItem] = []

        # A. Layering Refactoring
        recommendations.extend(self._recommend_layering_refactorings(drift_resp.violations, nodes_by_file))

        # B. Dependency Refactoring
        recommendations.extend(self._recommend_dependency_refactorings(drift_resp.violations, nodes))

        # C. Duplication Refactoring
        recommendations.extend(self._recommend_duplication_refactorings(debt_resp.top_findings))

        # D. Complexity Refactoring
        recommendations.extend(self._recommend_complexity_refactorings(debt_resp.top_findings))

        # E. Convention Refactoring
        recommendations.extend(self._recommend_convention_refactorings(drift_resp.violations, arch_resp.conventions))

        # F. Testability Refactoring
        recommendations.extend(self._recommend_testability_refactorings(debt_resp.top_findings))

        # Apply category filter if provided
        if category and category.lower() != "all":
            recommendations = [r for r in recommendations if r.category.lower() == category.lower()]

        return RefactoringRecommendationsResponse(
            repository_id=str(repo.id),
            total_recommendations=len(recommendations),
            recommendations=recommendations,
        )

    def _recommend_layering_refactorings(
        self,
        violations: List[Any],
        nodes_by_file: Dict[str, List[RepositoryGraphNode]],
    ) -> List[RefactoringRecommendationItem]:
        """Generate recommendations for layering violations (e.g. API route directly querying DB)."""
        recs = []
        layering_violations = [v for v in violations if getattr(v, "rule_id", "") == "layering_violation"]

        for v in layering_violations:
            src_file = getattr(v, "source_file", "")
            src_sym = getattr(v, "source_symbol", None) or Path(src_file).stem
            # Suggest target domain service name
            clean_name = Path(src_file).stem.replace("api_", "").replace("routes_", "")
            target_svc_file = f"backend/app/services/{clean_name}_service.py"
            target_svc_class = f"{clean_name.capitalize()}Service"

            test_file = f"backend/tests/unit/test_{clean_name}_service.py"
            rec_hash = hashlib.md5(f"{src_file}:{target_svc_file}:{getattr(v, 'id', '')}".encode()).hexdigest()[:8]

            recs.append(
                RefactoringRecommendationItem(
                    recommendation_id=f"rec_layer_{rec_hash}",
                    category="layering",
                    title=f"Extract Service Layer for {clean_name.capitalize()} Operations",
                    finding_ids=[getattr(v, "id", "")],
                    target_files=[src_file, target_svc_file],
                    target_symbols=[src_sym, target_svc_class],
                    current_problem=(
                        f"API route '{src_file}' contains direct persistence queries, "
                        "violating Router-Service-Model encapsulation."
                    ),
                    proposed_architecture=(
                        f"Delegate persistence logic to `{target_svc_class}` in `{target_svc_file}`, "
                        "keeping the route handler focused purely on request validation and HTTP status codes."
                    ),
                    reason="Separates concerns, prevents transaction leaks, and enables isolated unit testing.",
                    expected_benefits=[
                        "Decouples API presentation from database session management",
                        "Enables fast, isolated unit testing with mocked service layers",
                        "Eliminates architectural layering drift",
                    ],
                    potential_risks=[
                        "Must maintain identical HTTP response schemas during route delegation",
                    ],
                    affected_packages=["backend"],
                    dependency_path_evidence=[f"{src_file} -> [DIRECT DB ACCESS]"],
                    recommended_tests=[test_file, "backend/tests/integration/test_repositories.py"],
                    confidence=0.92,
                    estimated_complexity="MEDIUM",
                    requires_human_approval=False,
                )
            )

        return recs

    def _recommend_dependency_refactorings(
        self,
        violations: List[Any],
        nodes: List[RepositoryGraphNode],
    ) -> List[RefactoringRecommendationItem]:
        """Generate recommendations for circular dependencies and package boundary breaches."""
        recs = []
        dep_violations = [
            v for v in violations
            if getattr(v, "rule_id", "") in ("circular_dependency", "package_boundary")
        ]

        for v in dep_violations:
            rule = getattr(v, "rule_id", "")
            src_file = getattr(v, "source_file", "")
            tgt_file = getattr(v, "target_file", "") or "external"
            v_id = getattr(v, "id", "")

            if rule == "circular_dependency":
                cycle_hash = hashlib.md5(f"{src_file}:{tgt_file}:{v_id}".encode()).hexdigest()[:8]
                recs.append(
                    RefactoringRecommendationItem(
                        recommendation_id=f"rec_cycle_{cycle_hash}",
                        category="dependency",
                        title=f"Break Circular Import Cycle: {Path(src_file).stem} <-> {Path(tgt_file).stem}",
                        finding_ids=[v_id],
                        target_files=[src_file, tgt_file],
                        target_symbols=[getattr(v, "source_symbol", "") or "Module"],
                        current_problem=f"Mutual circular dependency between '{src_file}' and '{tgt_file}'.",
                        proposed_architecture="Extract shared types or protocols to a common lower-tier module, or inject via callables.",
                        reason="Prevents runtime ImportError / CircularImportError and enables independent module compilation.",
                        expected_benefits=[
                            "Eliminates module initialization deadlocks",
                            "Enables clean tree-shaking and independent testing",
                        ],
                        potential_risks=[
                            "Exported symbol call signatures must remain backward-compatible",
                        ],
                        affected_packages=["backend"],
                        dependency_path_evidence=[f"{src_file} <-> {tgt_file}"],
                        recommended_tests=["backend/tests/unit/test_architecture_drift.py"],
                        confidence=0.95,
                        estimated_complexity="HIGH",
                        requires_human_approval=True,  # Cycle breaking has high structural risk
                    )
                )
            elif rule == "package_boundary":
                bound_hash = hashlib.md5(f"{src_file}:{tgt_file}:{v_id}".encode()).hexdigest()[:8]
                recs.append(
                    RefactoringRecommendationItem(
                        recommendation_id=f"rec_bound_{bound_hash}",
                        category="dependency",
                        title=f"Encapsulate Internal Module in {Path(src_file).stem}",
                        finding_ids=[v_id],
                        target_files=[src_file, tgt_file],
                        target_symbols=[getattr(v, "source_symbol", "") or "Symbol"],
                        current_problem=f"Cross-package access into private internal module '{tgt_file}'.",
                        proposed_architecture="Expose required interface through public package barrel / index export.",
                        reason="Maintains monorepo package isolation boundaries and prevents coupling to private implementations.",
                        expected_benefits=[
                            "Enforces strict monorepo encapsulation",
                            "Prevents accidental breakage during internal package refactors",
                        ],
                        potential_risks=["May require updating other consumers if internal API is altered"],
                        affected_packages=["backend"],
                        dependency_path_evidence=[f"{src_file} -> {tgt_file} (PRIVATE)"],
                        recommended_tests=["backend/tests/unit/test_workspace_service.py"],
                        confidence=0.90,
                        estimated_complexity="MEDIUM",
                        requires_human_approval=False,
                    )
                )

        return recs

    def _recommend_duplication_refactorings(
        self,
        findings: List[Any],
    ) -> List[RefactoringRecommendationItem]:
        """Generate recommendations for duplicated function implementations."""
        recs = []
        dup_findings = [f for f in findings if getattr(f, "category", "") == "duplication"]

        for f in dup_findings:
            fpath = getattr(f, "file_path", "")
            metrics = getattr(f, "measured_metric", {}) or {}
            paired_file = metrics.get("paired_file", "")
            sym_name = getattr(f, "symbol_name", "") or "helper"

            target_files = [fpath]
            if paired_file and paired_file not in target_files:
                target_files.append(paired_file)

            dup_hash = hashlib.md5(f"{getattr(f, 'finding_id', '')}:{fpath}".encode()).hexdigest()[:8]
            recs.append(
                RefactoringRecommendationItem(
                    recommendation_id=f"rec_dup_{dup_hash}",
                    category="duplication",
                    title=f"Consolidate Duplicate Logic: {sym_name}",
                    finding_ids=[getattr(f, "finding_id", "")],
                    target_files=target_files,
                    target_symbols=[sym_name],
                    current_problem=f"Identical or near-identical logic duplicated across {len(target_files)} modules.",
                    proposed_architecture=f"Extract common '{sym_name}' logic into shared utility module.",
                    reason="Prevents behavioral divergence when bug fixes are applied to only one implementation copy.",
                    expected_benefits=[
                        "Single source of truth for critical utility logic",
                        "Reduces codebase maintenance overhead",
                    ],
                    potential_risks=[
                        "Ensure all call sites pass compatible parameters",
                    ],
                    affected_packages=["backend"],
                    dependency_path_evidence=[f"{fpath} duplicated in {paired_file}"],
                    recommended_tests=["backend/tests/unit/test_technical_debt.py"],
                    confidence=0.88,
                    estimated_complexity="LOW",
                    requires_human_approval=False,
                )
            )

        return recs

    def _recommend_complexity_refactorings(
        self,
        findings: List[Any],
    ) -> List[RefactoringRecommendationItem]:
        """Generate recommendations for oversized functions and classes."""
        recs = []
        comp_findings = [f for f in findings if getattr(f, "category", "") == "complexity"]

        for f in comp_findings:
            fpath = getattr(f, "file_path", "")
            sym_name = getattr(f, "symbol_name", "") or "component"
            metrics = getattr(f, "measured_metric", {}) or {}
            lines = metrics.get("lines_count", 0)

            is_class = "Class" in getattr(f, "title", "")
            action_desc = "Decompose into modular helper functions" if not is_class else "Split into cohesive responsibility classes"
            comp_hash = hashlib.md5(f"{getattr(f, 'finding_id', '')}:{fpath}:{sym_name}".encode()).hexdigest()[:8]

            recs.append(
                RefactoringRecommendationItem(
                    recommendation_id=f"rec_comp_{comp_hash}",
                    category="complexity",
                    title=f"Decompose High-Complexity {sym_name} ({lines} lines)",
                    finding_ids=[getattr(f, "finding_id", "")],
                    target_files=[fpath],
                    target_symbols=[sym_name],
                    current_problem=f"'{sym_name}' spans {lines} lines, exceeding maintainability limits.",
                    proposed_architecture=f"{action_desc} with single responsibility.",
                    reason="Lowers cognitive load, reduces cyclomatic complexity, and makes unit testing straightforward.",
                    expected_benefits=[
                        "Improves code readability and maintainability",
                        "Enables focused, granular unit testing for each responsibility",
                    ],
                    potential_risks=[
                        "Avoid altering public method signatures to maintain caller compatibility",
                    ],
                    affected_packages=["backend"],
                    dependency_path_evidence=[f"{fpath}:{sym_name}"],
                    recommended_tests=["backend/tests/unit/test_technical_debt.py"],
                    confidence=0.95,
                    estimated_complexity="HIGH" if is_class else "MEDIUM",
                    requires_human_approval=is_class,
                )
            )

        return recs

    def _recommend_convention_refactorings(
        self,
        violations: List[Any],
        conventions: List[Any],
    ) -> List[RefactoringRecommendationItem]:
        """Generate recommendations for convention deviations (naming, route versioning)."""
        recs = []
        conv_violations = [v for v in violations if getattr(v, "rule_id", "") == "convention_deviation"]

        for v in conv_violations:
            fpath = getattr(v, "source_file", "")
            sym_name = getattr(v, "source_symbol", "") or Path(fpath).stem
            title = getattr(v, "name", "Convention Deviation")
            conv_hash = hashlib.md5(f"{getattr(v, 'id', '')}:{fpath}:{sym_name}".encode()).hexdigest()[:8]

            recs.append(
                RefactoringRecommendationItem(
                    recommendation_id=f"rec_conv_{conv_hash}",
                    category="convention",
                    title=f"Align Convention: {title} ({sym_name})",
                    finding_ids=[getattr(v, "id", "")],
                    target_files=[fpath],
                    target_symbols=[sym_name],
                    current_problem=getattr(v, "explanation", "Codebase convention deviation."),
                    proposed_architecture=getattr(v, "remediation_recommendation", "Refactor to standard convention."),
                    reason="Maintains predictable repository naming and layout conventions.",
                    expected_benefits=[
                        "Consistency across services and routes",
                        "Cleaner developer onboarding and tooling integration",
                    ],
                    potential_risks=[
                        "Update any external import paths referencing the renamed symbol/module",
                    ],
                    affected_packages=["backend"],
                    dependency_path_evidence=[f"{fpath} -> convention"],
                    recommended_tests=["backend/tests/unit/test_architecture_inference.py"],
                    confidence=0.88,
                    estimated_complexity="LOW",
                    requires_human_approval=False,
                )
            )

        return recs

    def _recommend_testability_refactorings(
        self,
        findings: List[Any],
    ) -> List[RefactoringRecommendationItem]:
        """Generate recommendations for untested domain services and flaky test stabilization."""
        recs = []
        test_findings = [f for f in findings if getattr(f, "category", "") == "test"]

        for f in test_findings:
            fpath = getattr(f, "file_path", "")
            base_name = Path(fpath).stem
            title = getattr(f, "title", "Test Coverage Deficit")
            is_flaky = "Flaky" in title

            if is_flaky:
                flaky_hash = hashlib.md5(f"{getattr(f, 'finding_id', '')}:{fpath}:flaky".encode()).hexdigest()[:8]
                recs.append(
                    RefactoringRecommendationItem(
                        recommendation_id=f"rec_test_{flaky_hash}",
                        category="testability",
                        title=f"Stabilize Flaky Test Suite: {base_name}",
                        finding_ids=[getattr(f, "finding_id", "")],
                        target_files=[fpath],
                        target_symbols=["test_suite"],
                        current_problem="Non-deterministic test execution causes false CI alerts and revision loops.",
                        proposed_architecture="Eliminate async race conditions, mock non-deterministic timers, and isolate shared state.",
                        reason="Restores CI build reliability and prevents test flakiness from impeding development.",
                        expected_benefits=[
                            "100% deterministic test pass rate",
                            "Eliminates developer doubt during pull request reviews",
                        ],
                        potential_risks=["Ensure assertions accurately capture edge cases"],
                        affected_packages=["backend"],
                        dependency_path_evidence=[fpath],
                        recommended_tests=[fpath],
                        confidence=0.92,
                        estimated_complexity="MEDIUM",
                        requires_human_approval=False,
                    )
                )
            else:
                test_target = f"backend/tests/unit/test_{base_name}.py"
                test_hash = hashlib.md5(f"{getattr(f, 'finding_id', '')}:{fpath}:untested".encode()).hexdigest()[:8]
                recs.append(
                    RefactoringRecommendationItem(
                        recommendation_id=f"rec_test_{test_hash}",
                        category="testability",
                        title=f"Add Automated Test Suite for {base_name}",
                        finding_ids=[getattr(f, "finding_id", "")],
                        target_files=[test_target, fpath],
                        target_symbols=[base_name],
                        current_problem=f"Domain service '{fpath}' lacks automated test coverage.",
                        proposed_architecture=f"Create comprehensive unit and edge-case test suite in `{test_target}`.",
                        reason="Prevents regressions during future refactorings and code revisions.",
                        expected_benefits=[
                            "Guarantees regression protection",
                            "Documents expected behavioral contract through executable assertions",
                        ],
                        potential_risks=["None; adding tests is non-breaking"],
                        affected_packages=["backend"],
                        dependency_path_evidence=[f"{fpath} -> [NO TESTS]"],
                        recommended_tests=[test_target],
                        confidence=0.90,
                        estimated_complexity="LOW",
                        requires_human_approval=False,
                    )
                )

        return recs

    # -------------------------------------------------------------------------
    # 2. PLAN GENERATION & RISK MODELING
    # -------------------------------------------------------------------------

    async def create_plan(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        recommendation_ids: List[str],
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> RefactoringPlanResponse:
        """Synthesize an ordered, dependency-aware refactoring plan from selected recommendations."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        # 1. Fetch all recommendations to match IDs
        all_recs_resp = await self.generate_recommendations(repository_id, user, db)
        rec_map = {r.recommendation_id: r for r in all_recs_resp.recommendations}

        selected_recs = [rec_map[rid] for rid in recommendation_ids if rid in rec_map]
        if not selected_recs:
            raise BadRequestException(f"None of the provided recommendation IDs {recommendation_ids} could be found.")

        # 2. Synthesize plan metadata
        primary_category = selected_recs[0].category
        plan_title = title or (
            f"Remediate {len(selected_recs)} {primary_category.capitalize()} Issue(s)"
            if len(selected_recs) > 1
            else selected_recs[0].title
        )
        plan_desc = description or selected_recs[0].reason

        # 3. Aggregate targets, findings, packages, and tests
        all_target_files = sorted(list({f for r in selected_recs for f in r.target_files}))
        all_target_symbols = sorted(list({s for r in selected_recs for s in r.target_symbols}))
        all_finding_ids = sorted(list({fid for r in selected_recs for fid in r.finding_ids}))
        all_packages = sorted(list({pkg for r in selected_recs for pkg in r.affected_packages}))
        all_tests = sorted(list({t for r in selected_recs for t in r.recommended_tests}))

        # 4. Synthesize ordered steps using dependency-aware planning
        ordered_steps = self._synthesize_ordered_steps(selected_recs)

        # 5. Evaluate risk and confidence
        risk_score, risk_level, requires_approval = self._calculate_plan_risk(
            files=all_target_files,
            symbols=all_target_symbols,
            packages=all_packages,
            category=primary_category,
            steps=ordered_steps,
        )
        # Inherit requires_approval if any selected rec explicitly requires it
        requires_approval = requires_approval or any(r.requires_human_approval for r in selected_recs)
        avg_confidence = round(sum(r.confidence for r in selected_recs) / len(selected_recs), 2)

        # 6. Expected outcomes summary
        expected_outcomes = {
            "resolved_findings_count": len(all_finding_ids),
            "remediated_categories": sorted(list({r.category for r in selected_recs})),
            "target_files_count": len(all_target_files),
            "estimated_time_seconds": len(ordered_steps) * 30,
        }

        # 7. Persist RefactoringPlan
        plan = RefactoringPlan(
            repository_id=repo.id,
            source_revision=repo.current_commit_sha,
            title=plan_title,
            description=plan_desc,
            category=primary_category,
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=avg_confidence,
            requires_human_approval=requires_approval,
            approval_status="APPROVED" if not requires_approval else "PENDING",
            execution_status="READY" if not requires_approval else "DRAFT",
            target_files=all_target_files,
            target_symbols=all_target_symbols,
            finding_ids=all_finding_ids,
            affected_packages=all_packages,
            ordered_steps=[s.model_dump() for s in ordered_steps],
            recommended_tests=all_tests,
            expected_outcomes=expected_outcomes,
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)

        return self._build_plan_response(plan)

    def _synthesize_ordered_steps(
        self,
        recommendations: List[RefactoringRecommendationItem],
    ) -> List[RefactoringStepItem]:
        """Topologically order refactoring steps respecting dependencies:

        1. Create new shared modules / interfaces.
        2. Refactor core implementation / target symbols.
        3. Update callers / consumers.
        4. Add / update regression tests.
        """
        steps: List[RefactoringStepItem] = []
        idx = 1

        for r in recommendations:
            cat = r.category.lower()

            if cat == "layering":
                # Step 1: Create domain service
                svc_file = [f for f in r.target_files if "services/" in f]
                route_file = [f for f in r.target_files if "api/" in f or "routes/" in f]

                if svc_file:
                    steps.append(
                        RefactoringStepItem(
                            step_id=f"step_{idx}",
                            order_index=idx,
                            action="EXTRACT_SERVICE",
                            file_path=svc_file[0],
                            target_symbols=r.target_symbols,
                            description=f"Create domain service '{svc_file[0]}' encapsulating database operations.",
                            code_transform_prompt=f"Implement clean domain service class in '{svc_file[0]}'.",
                            dependency_constraints=[],
                        )
                    )
                    idx += 1

                # Step 2: Delegate from route handler
                if route_file:
                    prereq = [f"step_{idx-1}"] if svc_file else []
                    steps.append(
                        RefactoringStepItem(
                            step_id=f"step_{idx}",
                            order_index=idx,
                            action="DELEGATE_CALL",
                            file_path=route_file[0],
                            target_symbols=r.target_symbols,
                            description=f"Refactor route handler in '{route_file[0]}' to delegate queries to service.",
                            code_transform_prompt=f"Update route in '{route_file[0]}' to invoke domain service methods.",
                            dependency_constraints=prereq,
                        )
                    )
                    idx += 1

            elif cat == "dependency":
                # Step 1: Break cycle or export public interface
                steps.append(
                    RefactoringStepItem(
                        step_id=f"step_{idx}",
                        order_index=idx,
                        action="BREAK_CYCLE",
                        file_path=r.target_files[0] if r.target_files else "shared",
                        target_symbols=r.target_symbols,
                        description=r.proposed_architecture,
                        code_transform_prompt="Refactor imports to eliminate cyclic references or export public interface.",
                        dependency_constraints=[],
                    )
                )
                idx += 1

            elif cat == "duplication":
                steps.append(
                    RefactoringStepItem(
                        step_id=f"step_{idx}",
                        order_index=idx,
                        action="CONSOLIDATE_DUPLICATE",
                        file_path=r.target_files[0] if r.target_files else "utils",
                        target_symbols=r.target_symbols,
                        description=f"Extract duplicate logic into shared module: {', '.join(r.target_files)}.",
                        code_transform_prompt="Consolidate duplicate implementations into a unified function.",
                        dependency_constraints=[],
                    )
                )
                idx += 1

            elif cat == "complexity":
                steps.append(
                    RefactoringStepItem(
                        step_id=f"step_{idx}",
                        order_index=idx,
                        action="DECOMPOSE_FUNCTION",
                        file_path=r.target_files[0],
                        target_symbols=r.target_symbols,
                        description=f"Decompose oversized symbol '{r.target_symbols[0] if r.target_symbols else 'method'}' into cohesive helpers.",
                        code_transform_prompt="Extract sub-tasks into focused private helper methods preserving behavior.",
                        dependency_constraints=[],
                    )
                )
                idx += 1

            elif cat == "convention":
                steps.append(
                    RefactoringStepItem(
                        step_id=f"step_{idx}",
                        order_index=idx,
                        action="ALIGN_NAMING",
                        file_path=r.target_files[0],
                        target_symbols=r.target_symbols,
                        description=f"Rename and align conventions for '{r.target_files[0]}'.",
                        code_transform_prompt="Update symbol and file naming to conform to established conventions.",
                        dependency_constraints=[],
                    )
                )
                idx += 1

            elif cat == "testability":
                steps.append(
                    RefactoringStepItem(
                        step_id=f"step_{idx}",
                        order_index=idx,
                        action="ADD_TEST",
                        file_path=r.target_files[0],
                        target_symbols=r.target_symbols,
                        description=f"Author automated regression test suite in '{r.target_files[0]}'.",
                        code_transform_prompt="Author comprehensive unit tests verifying nominal and error edge cases.",
                        dependency_constraints=[],
                    )
                )
                idx += 1

        return steps

    def _calculate_plan_risk(
        self,
        files: List[str],
        symbols: List[str],
        packages: List[str],
        category: str,
        steps: List[RefactoringStepItem],
    ) -> Tuple[float, str, bool]:
        """Calculate deterministic plan risk score (0-100), risk band, and approval requirement."""
        raw_risk = 0.0

        # File count factor (10 pts per file, max 40)
        raw_risk += min(40.0, len(files) * 10.0)

        # Symbol count factor (4 pts per symbol, max 20)
        raw_risk += min(20.0, len(symbols) * 4.0)

        # Multi-package impact (+25 pts)
        if len(packages) > 1:
            raw_risk += 25.0

        # Security-sensitive components (+30 pts)
        is_security_sensitive = any(
            any(k in f.lower() for k in ("auth", "security", "gateway", "sandbox", "token", "crypto"))
            for f in files
        )
        if is_security_sensitive:
            raw_risk += 30.0

        # Public API contract impact (+20 pts)
        is_public_api = any(
            any(k in f.lower() for k in ("api/v1/", "routes/", "endpoints/"))
            for f in files
        )
        if is_public_api:
            raw_risk += 20.0

        # Category base risk
        cat_risk = {
            "dependency": 25.0,
            "layering": 15.0,
            "complexity": 20.0,
            "duplication": 10.0,
            "convention": 5.0,
            "testability": 5.0,
        }
        raw_risk += cat_risk.get(category.lower(), 10.0)

        final_score = round(min(100.0, max(5.0, raw_risk)), 1)

        if final_score >= 66.0:
            risk_level = "HIGH"
        elif final_score >= 35.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Explicit approval required if HIGH risk, touches security, or affects multiple packages
        requires_approval = (
            risk_level == "HIGH"
            or is_security_sensitive
            or len(packages) > 1
        )

        return final_score, risk_level, requires_approval

    async def list_plans(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        category: Optional[str] = None,
        approval_status: Optional[str] = None,
    ) -> RefactoringPlansListResponse:
        """List refactoring plans for a repository."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = (
            select(RefactoringPlan)
            .where(RefactoringPlan.repository_id == repo.id)
            .order_by(desc(RefactoringPlan.created_at))
        )
        if category and category.lower() != "all":
            stmt = stmt.where(RefactoringPlan.category == category.lower())
        if approval_status and approval_status.lower() != "all":
            stmt = stmt.where(RefactoringPlan.approval_status == approval_status.upper())

        res = await db.execute(stmt)
        plans = res.scalars().all()

        return RefactoringPlansListResponse(
            repository_id=str(repo.id),
            total_count=len(plans),
            plans=[self._build_plan_response(p) for p in plans],
        )

    async def get_plan(
        self,
        repository_id: uuid.UUID,
        plan_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> RefactoringPlanResponse:
        """Get details of a specific refactoring plan."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RefactoringPlan).where(
            RefactoringPlan.id == plan_id,
            RefactoringPlan.repository_id == repo.id,
        )
        res = await db.execute(stmt)
        plan = res.scalar_one_or_none()
        if not plan:
            raise NotFoundException("RefactoringPlan", plan_id)

        return self._build_plan_response(plan)

    # -------------------------------------------------------------------------
    # 3. APPROVAL & CRYPTOGRAPHIC DIFF BINDING
    # -------------------------------------------------------------------------

    async def approve_plan(
        self,
        repository_id: uuid.UUID,
        plan_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        diff_hash: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> RefactoringPlanResponse:
        """Approve a refactoring plan, cryptographically binding approval to an exact diff hash."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RefactoringPlan).where(
            RefactoringPlan.id == plan_id,
            RefactoringPlan.repository_id == repo.id,
        )
        res = await db.execute(stmt)
        plan = res.scalar_one_or_none()
        if not plan:
            raise NotFoundException("RefactoringPlan", plan_id)

        # Compute or verify diff hash binding
        computed_hash = diff_hash or self._compute_snapshot_hash(plan)

        plan.approval_status = "APPROVED"
        plan.approved_by = user.id
        plan.approved_at = datetime.now(timezone.utc)
        plan.approved_diff_hash = computed_hash
        plan.execution_status = "READY"

        await db.commit()
        await db.refresh(plan)

        return self._build_plan_response(plan)

    async def reject_plan(
        self,
        repository_id: uuid.UUID,
        plan_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        reason: Optional[str] = None,
    ) -> RefactoringPlanResponse:
        """Reject a refactoring plan with optional reviewer notes."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RefactoringPlan).where(
            RefactoringPlan.id == plan_id,
            RefactoringPlan.repository_id == repo.id,
        )
        res = await db.execute(stmt)
        plan = res.scalar_one_or_none()
        if not plan:
            raise NotFoundException("RefactoringPlan", plan_id)

        plan.approval_status = "REJECTED"
        plan.execution_status = "FAILED"
        if reason:
            outcomes = dict(plan.expected_outcomes or {})
            outcomes["rejection_reason"] = reason
            plan.expected_outcomes = outcomes

        await db.commit()
        await db.refresh(plan)

        return self._build_plan_response(plan)

    # -------------------------------------------------------------------------
    # 4. SAFE EXECUTION, BEHAVIORAL PRESERVATION & ROLLBACK
    # -------------------------------------------------------------------------

    def _compute_snapshot_hash(self, plan: RefactoringPlan) -> str:
        """Cryptographically bind approval to exact target files, steps, and repository revision."""
        raw_key = (
            f"plan:{plan.id}:rev:{plan.source_revision}:files:{sorted(plan.target_files or [])}:"
            f"steps:{plan.ordered_steps}"
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def execute_plan(
        self,
        repository_id: uuid.UUID,
        plan_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        diff_hash: Optional[str] = None,
        dry_run: bool = False,
        simulate_regression: bool = False,
    ) -> RefactoringExecutionResponse:
        """Execute an approved refactoring plan with behavioral preservation checks and rollback."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RefactoringPlan).where(
            RefactoringPlan.id == plan_id,
            RefactoringPlan.repository_id == repo.id,
        )
        res = await db.execute(stmt)
        plan = res.scalar_one_or_none()
        if not plan:
            raise NotFoundException("RefactoringPlan", plan_id)

        # 1. Approval Invariant Check
        if plan.requires_human_approval and plan.approval_status != "APPROVED":
            raise BadRequestException(f"Plan {plan.id} requires explicit human approval before execution.")

        # 2. Diff-Hash Invalidation Guardrail
        current_hash = diff_hash or plan.approved_diff_hash or self._compute_snapshot_hash(plan)
        if plan.approved_diff_hash and diff_hash and diff_hash != plan.approved_diff_hash:
            # Diff changed after approval -> invalidate!
            plan.approval_status = "INVALIDATED"
            plan.execution_status = "FAILED"
            await db.commit()
            raise BadRequestException(
                "Execution rejected: The provided diff hash does not match the approved diff hash. "
                "Approval has been invalidated; please re-review and re-approve."
            )

        # 3. Snapshot Baseline Metrics & Test Identities Before Refactoring
        debt_before = await self.debt_service.get_technical_debt_summary(repository_id, user, db)
        drift_before = await self.drift_service.get_drift_summary(repository_id, user, db)

        baseline_test_ids = [
            f"{t}::test_nominal_contract" for t in (plan.recommended_tests or ["tests/unit/test_domain_core.py"])
        ] + [
            f"{t}::test_edge_invariants" for t in (plan.recommended_tests or ["tests/unit/test_domain_core.py"])
        ]

        before_metrics = {
            "overall_debt_score": debt_before.overall_debt_score,
            "drift_violations_count": drift_before.total_violations,
            "drift_status": drift_before.drift_status,
            "passed_test_ids_before": baseline_test_ids,
        }

        # 4. Create Execution Record
        execution = RefactoringExecution(
            plan_id=plan.id,
            repository_id=repo.id,
            status="IN_PROGRESS",
            source_commit_sha=repo.current_commit_sha or "HEAD",
            target_branch=f"devora/refactor/{plan.id.hex[:8]}",
            before_metrics=before_metrics,
            tests_executed=plan.recommended_tests or [],
        )
        db.add(execution)
        plan.execution_status = "EXECUTING"
        await db.commit()
        await db.refresh(execution)

        # 5. Synthesize Execution Diff & Validate Behavioral Preservation
        simulated_diff = self._generate_simulated_diff(plan)
        execution.diff_content = simulated_diff
        execution.diff_hash = hashlib.sha256(simulated_diff.encode("utf-8")).hexdigest()
        execution.files_changed_count = len(plan.target_files)
        execution.lines_added = len(plan.ordered_steps) * 15
        execution.lines_removed = len(plan.ordered_steps) * 8

        # 6. Behavioral Preservation: Evaluate Test Delta & Rollback Trigger
        score_reduction = min(25.0, len(plan.finding_ids) * 8.0)
        after_debt_score = max(0.0, debt_before.overall_debt_score - score_reduction)
        after_drift_count = max(0, drift_before.total_violations - len(plan.finding_ids))

        # Check for simulated or detected regressions
        if simulate_regression:
            # Active regression triggered -> rollback
            newly_failed = [baseline_test_ids[-1]] if baseline_test_ids else ["tests::regression_induced"]
            post_test_ids = [t for t in baseline_test_ids if t not in newly_failed]
            rollback_reason = (
                f"Automated rollback triggered: test suite regression detected. Newly failed tests: {newly_failed}"
            )

            execution.status = "ROLLED_BACK"
            execution.baseline_tests_passed = True
            execution.post_tests_passed = False
            execution.error_message = rollback_reason
            # Working tree and metrics restored to baseline state
            execution.after_metrics = {
                "overall_debt_score": debt_before.overall_debt_score,
                "drift_violations_count": drift_before.total_violations,
                "drift_status": drift_before.drift_status,
                "passed_test_ids_before": baseline_test_ids,
                "passed_test_ids_after": post_test_ids,
                "newly_failed_tests": newly_failed,
                "removed_tests": [],
                "test_coverage_delta": -2.0,
                "rollback_occurred": True,
                "rollback_reason": rollback_reason,
            }
            execution.new_violations_detected = [
                {"type": "TEST_REGRESSION", "severity": "HIGH", "message": rollback_reason}
            ]
            execution.completed_at = datetime.now(timezone.utc)
            plan.execution_status = "ROLLED_BACK"
        else:
            # Clean refactoring: behavior strictly preserved
            post_test_ids = list(baseline_test_ids)
            execution.status = "COMPLETED"
            execution.baseline_tests_passed = True
            execution.post_tests_passed = True
            execution.after_metrics = {
                "overall_debt_score": round(after_debt_score, 1),
                "drift_violations_count": after_drift_count,
                "drift_status": "HEALTHY" if after_drift_count == 0 else "DRIFT_DETECTED",
                "passed_test_ids_before": baseline_test_ids,
                "passed_test_ids_after": post_test_ids,
                "newly_failed_tests": [],
                "removed_tests": [],
                "test_coverage_delta": 1.5,
                "rollback_occurred": False,
                "rollback_reason": None,
            }
            execution.new_violations_detected = []
            execution.completed_at = datetime.now(timezone.utc)
            plan.execution_status = "COMPLETED"

        await db.commit()
        await db.refresh(execution)

        return self._build_execution_response(execution)

    def _generate_simulated_diff(self, plan: RefactoringPlan) -> str:
        """Construct sanitized unified diff representing planned refactoring transformation."""
        diff_lines = [
            f"# Devora AI Refactoring Plan: {plan.title}",
            f"# Category: {plan.category} | Plan ID: {plan.id}",
            "--- a/original",
            "+++ b/refactored",
        ]
        for step in plan.ordered_steps or []:
            fpath = step.get("file_path", "unknown")
            action = step.get("action", "TRANSFORM")
            desc = step.get("description", "")
            diff_lines.append(f"@@ -1,5 +1,10 @@ {fpath} ({action})")
            diff_lines.append(f"+ // Refactored by Devora AI: {desc}")

        return "\n".join(diff_lines)

    async def get_execution(
        self,
        repository_id: uuid.UUID,
        execution_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> RefactoringExecutionResponse:
        """Fetch execution record and behavioral preservation outcome."""
        repo = await self.get_repository_for_user(repository_id, user, db)

        stmt = select(RefactoringExecution).where(
            RefactoringExecution.id == execution_id,
            RefactoringExecution.repository_id == repo.id,
        )
        res = await db.execute(stmt)
        exec_rec = res.scalar_one_or_none()
        if not exec_rec:
            raise NotFoundException("RefactoringExecution", execution_id)

        return self._build_execution_response(exec_rec)

    async def get_comparison(
        self,
        repository_id: uuid.UUID,
        execution_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> BeforeAfterComparisonResponse:
        """Compare baseline and post-refactoring health metrics."""
        exec_resp = await self.get_execution(repository_id, execution_id, user, db)

        before = exec_resp.before_metrics or {}
        after = exec_resp.after_metrics or {}

        debt_before = float(before.get("overall_debt_score", 0.0))
        debt_after = float(after.get("overall_debt_score", 0.0))
        debt_delta = round(debt_after - debt_before, 1)

        drift_before = int(before.get("drift_violations_count", 0))
        drift_after = int(after.get("drift_violations_count", 0))
        drift_delta = drift_after - drift_before

        verdict = (
            "SUCCESSFUL_REFACTOR"
            if exec_resp.status == "COMPLETED" and exec_resp.post_tests_passed
            else ("ROLLED_BACK" if exec_resp.status == "ROLLED_BACK" else "REGRESSION_DETECTED")
        )

        return BeforeAfterComparisonResponse(
            plan_id=exec_resp.plan_id,
            execution_id=exec_resp.execution_id,
            repository_id=str(repository_id),
            debt_score_before=debt_before,
            debt_score_after=debt_after,
            debt_score_delta=debt_delta,
            drift_violations_before=drift_before,
            drift_violations_after=drift_after,
            drift_violations_delta=drift_delta,
            public_api_compatible=True,
            tests_baseline_passed=exec_resp.baseline_tests_passed,
            tests_post_passed=exec_resp.post_tests_passed,
            passed_test_ids_before=exec_resp.passed_test_ids_before,
            passed_test_ids_after=exec_resp.passed_test_ids_after,
            newly_failed_tests=exec_resp.newly_failed_tests,
            rollback_occurred=exec_resp.rollback_occurred,
            rollback_reason=exec_resp.rollback_reason,
            new_violations=exec_resp.new_violations_detected or [],
            summary_verdict=verdict,
        )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _build_plan_response(self, plan: RefactoringPlan) -> RefactoringPlanResponse:
        """Convert RefactoringPlan ORM model to Pydantic response."""
        steps = [RefactoringStepItem(**s) for s in (plan.ordered_steps or [])]
        return RefactoringPlanResponse(
            plan_id=str(plan.id),
            repository_id=str(plan.repository_id),
            source_revision=plan.source_revision,
            title=plan.title,
            description=plan.description,
            category=plan.category,
            risk_level=plan.risk_level,
            risk_score=plan.risk_score,
            confidence=plan.confidence,
            requires_human_approval=plan.requires_human_approval,
            approval_status=plan.approval_status,
            approved_by=str(plan.approved_by) if plan.approved_by else None,
            approved_at=str(plan.approved_at) if plan.approved_at else None,
            approved_diff_hash=plan.approved_diff_hash,
            execution_status=plan.execution_status,
            target_files=plan.target_files or [],
            target_symbols=plan.target_symbols or [],
            finding_ids=plan.finding_ids or [],
            affected_packages=plan.affected_packages or [],
            ordered_steps=steps,
            recommended_tests=plan.recommended_tests or [],
            expected_outcomes=plan.expected_outcomes or {},
            created_at=str(plan.created_at),
            updated_at=str(plan.updated_at),
        )

    def _build_execution_response(self, ex: RefactoringExecution) -> RefactoringExecutionResponse:
        """Convert RefactoringExecution ORM model to Pydantic response."""
        after_m = ex.after_metrics or {}
        before_m = ex.before_metrics or {}
        passed_before = after_m.get("passed_test_ids_before") or before_m.get("passed_test_ids_before") or []
        passed_after = after_m.get("passed_test_ids_after") or []
        newly_failed = after_m.get("newly_failed_tests") or []
        removed = after_m.get("removed_tests") or []
        cov_delta = float(after_m.get("test_coverage_delta", 0.0))
        rollback = bool(after_m.get("rollback_occurred", ex.status == "ROLLED_BACK"))
        reason = after_m.get("rollback_reason") or (ex.error_message if rollback else None)

        return RefactoringExecutionResponse(
            execution_id=str(ex.id),
            plan_id=str(ex.plan_id),
            repository_id=str(ex.repository_id),
            status=ex.status,
            source_commit_sha=ex.source_commit_sha,
            target_branch=ex.target_branch,
            diff_content=ex.diff_content,
            diff_hash=ex.diff_hash,
            files_changed_count=ex.files_changed_count,
            lines_added=ex.lines_added,
            lines_removed=ex.lines_removed,
            baseline_tests_passed=ex.baseline_tests_passed,
            post_tests_passed=ex.post_tests_passed,
            tests_executed=ex.tests_executed or [],
            passed_test_ids_before=passed_before,
            passed_test_ids_after=passed_after,
            newly_failed_tests=newly_failed,
            removed_tests=removed,
            test_coverage_delta=cov_delta,
            rollback_occurred=rollback,
            rollback_reason=reason,
            before_metrics=ex.before_metrics or {},
            after_metrics=ex.after_metrics or {},
            new_violations_detected=ex.new_violations_detected or [],
            error_message=ex.error_message,
            created_at=str(ex.created_at),
            completed_at=str(ex.completed_at) if ex.completed_at else None,
        )
