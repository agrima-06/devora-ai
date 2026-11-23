"""Integration tests for Phase 10 Stage 10.2: Blast Radius and Change Impact Analysis Engine."""
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.repository import Repository
from app.models.user import User
from app.agents.specialists.planner import planner_node
from app.agents.specialists.code_reviewer import code_reviewer_node
from app.agents.specialists.reporter import reporter_node
from app.agents.state import DevoraWorkflowState, TaskPlanOutput, CodeReviewOutput, FinalReportOutput


@pytest.fixture
def multi_file_git_repo():
    """Create a temporary real git repository with cross-file dependencies and test suites."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)

        # 1. src/formatter.py (leaf dependency)
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "formatter.py").write_text('''"""Result formatter."""
import math

def format_result(val: float) -> str:
    """Format numeric result."""
    return f"Value: {round(val, 2)}"
''')

        # 2. src/calculator.py (depends on formatter.py)
        (src_dir / "calculator.py").write_text('''"""Calculator engine."""
from src.formatter import format_result

class BaseEngine:
    """Base mathematical engine."""
    pass

class MathEngine(BaseEngine):
    """Core calculator."""

    def __init__(self, precision: int = 2):
        self.precision = precision

    def compute_sum(self, a: float, b: float) -> str:
        """Add two numbers and format output."""
        total = a + b
        return format_result(total)

def calculate_average(numbers: list) -> float:
    """Calculate mean of numbers."""
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
''')

        # 3. src/main.py (depends on calculator.py and external fastapi)
        (src_dir / "main.py").write_text('''"""Application entry point."""
from src.calculator import MathEngine
import fastapi

app = fastapi.FastAPI()
engine = MathEngine()

@app.get("/add")
def add_numbers(a: float, b: float):
    return {"result": engine.compute_sum(a, b)}
''')

        # 4. tests/test_calculator.py (test file importing calculator.py)
        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calculator.py").write_text('''"""Tests for calculator."""
import pytest
from src.calculator import MathEngine, calculate_average

def test_compute_sum():
    engine = MathEngine()
    res = engine.compute_sum(2.0, 3.0)
    assert "Value: 5" in res

def test_calculate_average():
    assert calculate_average([1, 2, 3]) == 2.0
''')

        # Initialize Git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@devora.ai"], cwd=repo_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

        yield str(repo_dir)


@pytest.mark.asyncio
async def test_impact_analysis_for_leaf_file(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test blast radius when modifying src/formatter.py (should impact calculator, main, and tests)."""
    proj = Project(name="Impact Project", slug=f"impact-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="impact-repo",
        full_name="local/impact-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    # 1. Index the graph first
    index_res = await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )
    assert index_res.status_code == 200

    # 2. Run Impact Analysis for src/formatter.py
    impact_res = await client.post(
        f"/api/v1/repositories/{repo.id}/impact-analysis",
        json={
            "file_paths": ["src/formatter.py"],
            "max_depth": 3,
            "include_tests": True,
        },
        headers=auth_headers,
    )
    assert impact_res.status_code == 200
    data = impact_res.json()

    assert data["repository_id"] == str(repo.id)
    assert data["impact_score"] > 0
    assert data["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert data["confidence"] > 0.0

    # src/formatter.py is used by src/calculator.py (direct) and src/main.py (transitive)
    affected_files = data["affected_files"]
    assert "src/formatter.py" in affected_files
    assert any("calculator.py" in f for f in affected_files)

    # Dependency paths should explain why calculator or main is affected
    paths = data["dependency_paths"]
    assert len(paths) > 0
    first_path = paths[0]
    assert "explanation" in first_path
    assert first_path["depth"] >= 1

    # Recommended tests should recommend tests/test_calculator.py
    rec_tests = data["recommended_tests"]
    assert len(rec_tests) > 0
    assert any("test_calculator.py" in t["test_file_path"] for t in rec_tests)


@pytest.mark.asyncio
async def test_impact_analysis_for_symbol_target(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test blast radius when targeting a specific symbol (MathEngine class)."""
    proj = Project(name="Symbol Impact Project", slug=f"sym-impact-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="sym-impact-repo",
        full_name="local/sym-impact-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    # Index graph
    await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )

    # Run analysis for MathEngine
    res = await client.post(
        f"/api/v1/repositories/{repo.id}/impact-analysis",
        json={
            "qualified_names": ["src/calculator.py:MathEngine"],
            "max_depth": 2,
            "include_tests": True,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["summary"]["total_affected_files"] >= 1
    assert data["score_breakdown"]["files_score"] > 0
    assert data["score_breakdown"]["symbols_score"] > 0


@pytest.mark.asyncio
async def test_impact_analysis_unresolved_or_empty_target(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test graceful handling when target file or symbol does not exist in graph."""
    proj = Project(name="Empty Target Project", slug=f"empty-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="empty-target-repo",
        full_name="local/empty-target-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    res = await client.post(
        f"/api/v1/repositories/{repo.id}/impact-analysis",
        json={"file_paths": ["nonexistent/fake_module.py"]},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["impact_score"] == 0
    assert data["severity"] == "UNKNOWN"
    assert data["summary"]["total_affected_files"] == 0


@pytest.mark.asyncio
async def test_repository_isolation_and_unauthorized_access(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test that unauthorized user cannot access another user's repository impact analysis."""
    random_repo_id = uuid.uuid4()
    res = await client.post(
        f"/api/v1/repositories/{random_repo_id}/impact-analysis",
        json={"file_paths": ["src/main.py"]},
        headers=auth_headers,
    )
    assert res.status_code == 404

    # Unauthorized without auth headers
    res_no_auth = await client.post(
        f"/api/v1/repositories/{random_repo_id}/impact-analysis",
        json={"file_paths": ["src/main.py"]},
    )
    assert res_no_auth.status_code == 401


@pytest.mark.asyncio
async def test_agent_workflow_integration_smoke():
    """Verify that specialist agent nodes cleanly ingest impact_analysis from workflow state."""
    mock_plan = TaskPlanOutput(
        objective="Fix calculation bug",
        implementation_strategy="Update precision",
        strategy_rationale="Empirical safety",
        risks_and_assumptions=[],
        steps=[],
        test_criteria=["Run test_calculator.py"],
        risk_level="MEDIUM",
    )
    mock_review = CodeReviewOutput(
        approved=True,
        quality_score=92,
        comments=["Good clean implementation", "Downstream consumers respected"],
        suggested_refactorings=[],
    )
    mock_report = FinalReportOutput(
        title="Calculation Fix Report",
        summary="Successfully repaired arithmetic rounding",
        root_cause_analysis="Floating point precision mismatch",
        changes_made=["src/calculator.py"],
        verification_evidence="All 2 tests passed",
        limitations=None,
        markdown_report="# Executive Report\n\nVerified bug fix.",
    )

    state: DevoraWorkflowState = {
        "task_id": "test-task-1",
        "user_id": "user-1",
        "repository_id": "repo-1",
        "task_description": "Fix arithmetic precision",
        "task_type": "bug_fix",
        "git_diff": "diff --git a/calc.py b/calc.py",
        "applied_file_changes": [{"file_path": "src/calculator.py"}],
        "test_results": {"passed": True, "passed_tests": 2, "failed_tests": 0, "exit_code": 0},
        "impact_analysis": {
            "severity": "HIGH",
            "impact_score": 65,
            "confidence": 0.95,
            "affected_files": ["src/calculator.py", "src/main.py"],
            "recommended_tests": [{"test_file_path": "tests/test_calculator.py"}],
        },
    }

    with patch("app.agents.gateway.gateway.ModelGateway.get_instance") as mock_get_gw:
        mock_gw = MagicMock()
        mock_gw.generate_structured = AsyncMock()
        mock_get_gw.return_value = mock_gw

        # 1. Test Planner node
        mock_gw.generate_structured.return_value = mock_plan
        plan_res = await planner_node(state)
        assert plan_res["current_agent"] == "planner"
        assert "implementation_plan" in plan_res

        # 2. Test Code Reviewer node
        mock_gw.generate_structured.return_value = mock_review
        review_res = await code_reviewer_node(state)
        assert review_res["current_agent"] == "code_reviewer"
        assert review_res["review_results"]["approved"] is True

        # 3. Test Reporter node
        mock_gw.generate_structured.return_value = mock_report
        report_res = await reporter_node(state)
        assert report_res["current_agent"] == "reporter"
        assert "final_report" in report_res
