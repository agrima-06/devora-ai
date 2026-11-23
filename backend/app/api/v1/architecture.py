"""API Router for Phase 10 Stage 10.4: Semantic Architecture & Pattern Inference Engine."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.architecture import (
    ArchitectureAskRequest,
    ArchitectureAskResponse,
    ArchitectureConventionItem,
    ArchitecturePatternItem,
    ArchitectureSummaryResponse,
    HybridSearchRequest,
    HybridSearchResponse,
)
from app.schemas.drift import (
    ArchitectureDriftResponse,
    TechnicalDebtFindingItem,
    TechnicalDebtFindingsResponse,
    TechnicalDebtSummaryResponse,
    TechnicalDebtTrendsResponse,
)
from app.services.architecture_drift_service import ArchitectureDriftService
from app.services.architecture_inference_service import ArchitectureInferenceService
from app.services.search_service import CodeSearchService
from app.services.technical_debt_service import TechnicalDebtService

router = APIRouter(prefix="/repositories/{repository_id}", tags=["Architecture & Hybrid Search"])


@router.post(
    "/search/hybrid",
    response_model=HybridSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Multi-modal hybrid repository search (Lexical + Semantic + Structural)",
)
async def search_hybrid(
    repository_id: uuid.UUID,
    payload: HybridSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HybridSearchResponse:
    """Execute hybrid search combining identifier matching, vector semantic embeddings,

    and structural AST/dependency graph centrality using Reciprocal Rank Fusion.
    """
    search_service = CodeSearchService()
    return await search_service.search_hybrid(
        repository_id=repository_id,
        query=payload.query,
        user=current_user,
        db=db,
        filters=payload.filters,
        limit=payload.limit,
        offset=payload.offset,
        lexical_weight=payload.lexical_weight,
        semantic_weight=payload.semantic_weight,
        structural_weight=payload.structural_weight,
    )


@router.get(
    "/architecture",
    response_model=ArchitectureSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get unified repository architecture summary and patterns",
)
async def get_architecture_summary(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureSummaryResponse:
    """Retrieve inferred software architecture patterns, verified confidence ratings,

    and extracted coding conventions for the repository.
    """
    service = ArchitectureInferenceService()
    return await service.get_architecture_summary(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )


@router.post(
    "/architecture/analyze",
    response_model=ArchitectureSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger on-demand architectural pattern re-analysis",
)
async def analyze_architecture(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureSummaryResponse:
    """Force re-analysis of repository evidence (AST, graph topology, file layout, configs)

    and persist newly inferred patterns and conventions.
    """
    service = ArchitectureInferenceService()
    return await service.analyze_repository_architecture(
        repository_id=repository_id,
        user=current_user,
        db=db,
        force_refresh=True,
    )


@router.get(
    "/architecture/patterns",
    response_model=List[ArchitecturePatternItem],
    status_code=status.HTTP_200_OK,
    summary="List inferred architectural patterns",
)
async def list_patterns(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by category: application, backend, frontend, ai_agent, data"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score threshold"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ArchitecturePatternItem]:
    """List all detected architectural patterns with supporting files, symbols, and status."""
    service = ArchitectureInferenceService()
    return await service.list_patterns(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
        min_confidence=min_confidence,
    )


@router.get(
    "/architecture/patterns/{pattern_id}",
    response_model=ArchitecturePatternItem,
    status_code=status.HTTP_200_OK,
    summary="Get details of a specific architectural pattern",
)
async def get_pattern(
    repository_id: uuid.UUID,
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitecturePatternItem:
    """Get detailed evidence, supporting files, and counterexamples for a specific pattern."""
    service = ArchitectureInferenceService()
    patterns = await service.list_patterns(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )
    for p in patterns:
        if p.pattern_id == pattern_id or (p.id and p.id == pattern_id):
            return p
    raise NotFoundException("ArchitecturePattern", pattern_id)


@router.get(
    "/architecture/conventions",
    response_model=List[ArchitectureConventionItem],
    status_code=status.HTTP_200_OK,
    summary="List extracted project coding and architectural conventions",
)
async def list_conventions(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by category: service, api, database, error, test, agent"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ArchitectureConventionItem]:
    """Retrieve discovered repository conventions across services, APIs, tests, and error handling."""
    service = ArchitectureInferenceService()
    return await service.list_conventions(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
    )


@router.post(
    "/architecture/ask",
    response_model=ArchitectureAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask an architectural question grounded in codebase evidence",
)
async def ask_architecture(
    repository_id: uuid.UUID,
    payload: ArchitectureAskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureAskResponse:
    """Ask a natural-language architecture question and receive an explanation

    grounded in empirical hybrid code matches and verified design patterns.
    """
    service = ArchitectureInferenceService()
    return await service.ask_architecture(
        repository_id=repository_id,
        request=payload,
        user=current_user,
        db=db,
    )


# -----------------------------------------------------------------------------
# Phase 10 Stage 10.5: Architectural Drift & Technical Debt Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/architecture/drift",
    response_model=ArchitectureDriftResponse,
    status_code=status.HTTP_200_OK,
    summary="Get architectural drift summary and violations",
)
async def get_architecture_drift(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureDriftResponse:
    """Retrieve architectural drift status, layering violations, circular dependencies,

    package boundary breaches, and convention deviations compared to baseline.
    """
    service = ArchitectureDriftService()
    return await service.get_drift_summary(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )


@router.post(
    "/architecture/drift/analyze",
    response_model=ArchitectureDriftResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger on-demand architectural drift analysis",
)
async def analyze_architecture_drift(
    repository_id: uuid.UUID,
    baseline_commit_sha: Optional[str] = Query(None, description="Optional baseline commit SHA to compare against"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureDriftResponse:
    """Trigger drift analysis comparing current repository implementation against established patterns."""
    service = ArchitectureDriftService()
    return await service.analyze_drift(
        repository_id=repository_id,
        user=current_user,
        db=db,
        baseline_commit_sha=baseline_commit_sha,
    )


@router.get(
    "/technical-debt",
    response_model=TechnicalDebtSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get repository-level technical debt summary and dimension scores",
)
async def get_technical_debt(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalDebtSummaryResponse:
    """Retrieve deterministic 0-100 technical debt score, severity band, confidence,

    and breakdown across complexity, duplication, dependencies, testing, and maintainability.
    """
    service = TechnicalDebtService()
    return await service.get_technical_debt_summary(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )


@router.post(
    "/technical-debt/analyze",
    response_model=TechnicalDebtSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger on-demand technical debt re-evaluation",
)
async def analyze_technical_debt(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalDebtSummaryResponse:
    """Force re-measurement of code duplication, complexity, dependency cycles, and test deficit."""
    service = TechnicalDebtService()
    return await service.analyze_technical_debt(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )


@router.get(
    "/technical-debt/findings",
    response_model=TechnicalDebtFindingsResponse,
    status_code=status.HTTP_200_OK,
    summary="List paginated technical debt findings with filters",
)
async def get_technical_debt_findings(
    repository_id: uuid.UUID,
    category: Optional[str] = Query(None, description="Filter by category: complexity, duplication, dependency, maintainability, test"),
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalDebtFindingsResponse:
    """Retrieve detailed, actionable technical debt findings with measured metrics and remediation steps."""
    service = TechnicalDebtService()
    return await service.get_findings(
        repository_id=repository_id,
        user=current_user,
        db=db,
        category=category,
        severity=severity,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/technical-debt/findings/{finding_id}",
    response_model=TechnicalDebtFindingItem,
    status_code=status.HTTP_200_OK,
    summary="Get single technical debt finding details",
)
async def get_technical_debt_finding_detail(
    repository_id: uuid.UUID,
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalDebtFindingItem:
    """Retrieve full details, code snippet evidence, and remediation advice for a single finding."""
    service = TechnicalDebtService()
    findings_resp = await service.get_findings(
        repository_id=repository_id,
        user=current_user,
        db=db,
        limit=200,
        offset=0,
    )
    for f in findings_resp.findings:
        if f.finding_id == finding_id:
            return f
    raise NotFoundException("TechnicalDebtFinding", finding_id)


@router.get(
    "/technical-debt/trends",
    response_model=TechnicalDebtTrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get historical technical debt score progression",
)
async def get_technical_debt_trends(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalDebtTrendsResponse:
    """Retrieve historical progression of technical debt scores across commit snapshots."""
    service = TechnicalDebtService()
    return await service.get_debt_trends(
        repository_id=repository_id,
        user=current_user,
        db=db,
    )
