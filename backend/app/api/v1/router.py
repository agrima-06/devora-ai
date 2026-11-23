"""API V1 Router aggregator."""
from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.projects import router as projects_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.memories import router as memories_router
from app.api.v1.ml import router as ml_router
from app.api.v1.adaptive import router as adaptive_router
from app.api.v1.github import router as github_router
from app.api.v1.pull_requests import router as pull_requests_router
from app.api.v1.flaky_tests import router as flaky_tests_router
from app.api.v1.models import router as models_router
from app.api.v1.reliability import router as reliability_router
from app.api.v1.graph import router as graph_router
from app.api.v1.impact import router as impact_router
from app.api.v1.workspaces import router as workspaces_router
from app.api.v1.architecture import router as architecture_router
from app.api.v1.refactoring import router as refactoring_router
from app.api.v1.benchmarks import router as benchmarks_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(graph_router)
api_v1_router.include_router(impact_router)
api_v1_router.include_router(workspaces_router)
api_v1_router.include_router(architecture_router)
api_v1_router.include_router(refactoring_router)
api_v1_router.include_router(benchmarks_router)
api_v1_router.include_router(repositories_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(memories_router)
api_v1_router.include_router(ml_router)
api_v1_router.include_router(adaptive_router)
api_v1_router.include_router(github_router)
api_v1_router.include_router(pull_requests_router)
api_v1_router.include_router(flaky_tests_router)
api_v1_router.include_router(models_router)
api_v1_router.include_router(reliability_router)
