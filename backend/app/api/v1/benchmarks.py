"""API Router for Phase 10 Stage 10.7: Autonomous Engineering Intelligence Evaluation & Benchmarking Engine."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.benchmark import (
    BenchmarkReportResponse,
    BenchmarkRunComparisonRequest,
    BenchmarkRunComparisonResponse,
    BenchmarkScenarioCreate,
    BenchmarkScenarioResponse,
    BenchmarkScenariosListResponse,
    BenchmarkSuiteRunDetailResponse,
    BenchmarkSuiteRunRequest,
    BenchmarkSuiteRunResponse,
    BenchmarkSuiteRunsListResponse,
)
from app.services.benchmark_engine_service import BenchmarkEngineService, BenchmarkScoringService

router = APIRouter(prefix="/benchmarks", tags=["Evaluation & Benchmarking Engine"])


@router.get(
    "/scenarios",
    response_model=BenchmarkScenariosListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all benchmark evaluation scenarios",
)
async def list_scenarios(
    category: Optional[str] = Query(None, description="Filter by canonical category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkScenariosListResponse:
    """List registered ground-truth evaluation benchmark scenarios."""
    service = BenchmarkEngineService()
    return await service.list_scenarios(db=db, category=category, is_active=is_active)


@router.get(
    "/scenarios/{scenario_key}",
    response_model=BenchmarkScenarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details of a specific benchmark scenario",
)
async def get_scenario(
    scenario_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkScenarioResponse:
    """Fetch scenario metadata, input context, expected output assertions, and criteria."""
    service = BenchmarkEngineService()
    return await service.get_scenario(scenario_key_or_id=scenario_key, db=db)


@router.post(
    "/scenarios",
    response_model=BenchmarkScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new benchmark scenario",
)
async def create_scenario(
    payload: BenchmarkScenarioCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkScenarioResponse:
    """Register a new ground-truth benchmark scenario with deterministic evaluation criteria."""
    service = BenchmarkEngineService()
    return await service.create_scenario(payload=payload, db=db)


@router.post(
    "/runs",
    response_model=BenchmarkSuiteRunDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger benchmark suite execution",
)
async def trigger_suite_run(
    request: BenchmarkSuiteRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteRunDetailResponse:
    """Execute evaluation suite across canonical categories, computing aggregate score and calibration error."""
    service = BenchmarkEngineService()
    return await service.trigger_suite_run(request=request, user=current_user, db=db)


@router.get(
    "/runs",
    response_model=BenchmarkSuiteRunsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List historical benchmark suite runs",
)
async def list_runs(
    model_name: Optional[str] = Query(None, description="Filter runs by evaluated model"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter runs by status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteRunsListResponse:
    """List historical benchmark suite runs ordered chronologically."""
    service = BenchmarkEngineService()
    return await service.list_runs(db=db, model_name=model_name, status_filter=status_filter)


@router.get(
    "/runs/{run_id}",
    response_model=BenchmarkSuiteRunDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get benchmark suite run details and results",
)
async def get_run_detail(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteRunDetailResponse:
    """Fetch complete evaluation results for all scenarios in a suite execution run."""
    service = BenchmarkEngineService()
    return await service.get_run(run_id=run_id, db=db)


@router.post(
    "/runs/{run_id}/cancel",
    response_model=BenchmarkSuiteRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel active benchmark suite run",
)
async def cancel_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSuiteRunResponse:
    """Cancel an active or pending benchmark execution run."""
    service = BenchmarkEngineService()
    return await service.cancel_run(run_id=run_id, db=db)


@router.post(
    "/compare",
    response_model=BenchmarkRunComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare two benchmark runs and detect regressions",
)
async def compare_runs(
    request: BenchmarkRunComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRunComparisonResponse:
    """Perform side-by-side regression analysis between baseline and target suite runs."""
    service = BenchmarkEngineService()
    return await service.compare_runs(request=request, db=db)


@router.get(
    "/runs/{run_id}/report",
    response_model=BenchmarkReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate audit-ready markdown benchmark report",
)
async def get_benchmark_report(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkReportResponse:
    """Generate exportable, audit-ready markdown evaluation report for compliance and verification."""
    service = BenchmarkEngineService()
    return await service.generate_report(run_id=run_id, db=db)


@router.get(
    "/categories",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get canonical benchmark categories and weights",
)
async def get_categories(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve canonical benchmark category definitions, weighting formula, and descriptions."""
    return {
        "categories": [
            {
                "key": "bug_detection",
                "name": "Bug Detection and Resolution",
                "weight": 0.30,
                "description": "Functional correctness, defect localization, patch generation, and regression avoidance.",
            },
            {
                "key": "repo_understanding",
                "name": "Repository Understanding",
                "weight": 0.15,
                "description": "Cross-file symbol navigation, call-graph completeness, and entrypoint discovery.",
            },
            {
                "key": "arch_intelligence",
                "name": "Architecture Intelligence",
                "weight": 0.15,
                "description": "Architectural pattern inference, drift detection, layering integrity, and cyclic dependency analysis.",
            },
            {
                "key": "refactoring",
                "name": "Autonomous Refactoring",
                "weight": 0.15,
                "description": "Behavioral preservation, AST decomposition, and automated rollback verification.",
            },
            {
                "key": "security_safety",
                "name": "Security and Safety",
                "weight": 0.15,
                "description": "Vulnerability remediation, multi-tenant isolation, and immutable approval gating.",
            },
            {
                "key": "multi_agent",
                "name": "Multi-Agent Workflow Quality",
                "weight": 0.05,
                "description": "Planner-coder handoffs, reviewer fidelity, retry loops, and checkpoint resumption.",
            },
            {
                "key": "impact_analysis",
                "name": "Change Impact Analysis",
                "weight": 0.05,
                "description": "Blast radius precision, transitive dependency tracing, and test suite recommendation.",
            },
        ],
        "weighting_formula": "0.30*BugDetection + 0.15*RepoUnder + 0.15*ArchIntel + 0.15*Refactor + 0.15*Security + 0.05*MultiAgent + 0.05*Impact",
        "critical_safety_override": "Active: Any safety breach forces run status to CRITICAL_SAFETY_FAILURE and score to 0.0",
    }


@router.get(
    "/models",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get supported evaluation models",
)
async def get_evaluation_models(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List available AI models configured for benchmark evaluation."""
    return [
        {"model_id": "gemini-1.5-pro", "provider": "Google DeepMind", "context_window": 1000000, "is_default": True},
        {"model_id": "gemini-1.5-flash", "provider": "Google DeepMind", "context_window": 1000000, "is_default": False},
        {"model_id": "claude-3-5-sonnet", "provider": "Anthropic", "context_window": 200000, "is_default": False},
        {"model_id": "gpt-4o", "provider": "OpenAI", "context_window": 128000, "is_default": False},
    ]


@router.post(
    "/seed",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Seed benchmark dataset",
)
async def seed_dataset(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Ensure all canonical 31 benchmark scenarios are seeded into the database."""
    service = BenchmarkEngineService()
    total_count = await service.ensure_dataset_seeded(db)
    return {
        "status": "SEEDED",
        "total_scenarios": total_count,
        "message": f"Dataset seeded successfully with {total_count} benchmark scenarios.",
    }
