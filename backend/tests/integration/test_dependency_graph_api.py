"""Integration tests for Phase 10 Stage 10.1: Repository Dependency Graph API."""
import subprocess
import tempfile
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.project import Project
from app.models.repository import Repository
from app.models.user import User


@pytest.fixture
def multi_file_git_repo():
    """Create a temporary real git repository with cross-file dependencies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)

        # 1. src/formatter.py
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "formatter.py").write_text('''"""Result formatter."""
import math

def format_result(val: float) -> str:
    """Format numeric result."""
    return f"Value: {round(val, 2)}"
''')

        # 2. src/calculator.py
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

        # 3. src/main.py (imports local calculator and external fastapi)
        (src_dir / "main.py").write_text('''"""Application entry point."""
from src.calculator import MathEngine
import fastapi

app = fastapi.FastAPI()
engine = MathEngine()

@app.get("/add")
def add_numbers(a: float, b: float):
    return {"result": engine.compute_sum(a, b)}
''')

        # 4. tests/test_calculator.py
        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calculator.py").write_text('''"""Unit tests."""
from src.calculator import MathEngine
import pytest

def test_addition():
    calc = MathEngine()
    assert "Value: 5" in calc.compute_sum(2, 3)
''')

        (repo_dir / "requirements.txt").write_text("fastapi==0.110.0\npytest==8.0.0\n")
        (repo_dir / "README.md").write_text("# Graph Test Repo\n")

        subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "config", "user.email", "tester@devora.ai"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

        yield str(repo_dir)


@pytest.mark.asyncio
async def test_full_repository_graph_indexing(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test full repository dependency graph indexing, summary statistics, and cross-file relationships."""
    # 1. Setup project and repository
    proj = Project(name="Graph Project", slug=f"graph-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="graph-repo",
        full_name="local/graph-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    # 2. Trigger graph indexing via POST /repositories/{id}/graph/index
    res = await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )
    assert res.status_code == 200
    index_data = res.json()
    assert index_data["status"] == "INDEXED"
    assert index_data["total_files"] >= 4
    assert index_data["files_indexed"] >= 4
    assert index_data["nodes_created"] > 0
    assert index_data["edges_created"] > 0

    # 3. Fetch summary via GET /repositories/{id}/graph
    summary_res = await client.get(
        f"/api/v1/repositories/{repo.id}/graph",
        headers=auth_headers,
    )
    assert summary_res.status_code == 200
    summary = summary_res.json()

    assert summary["total_nodes"] > 0
    assert summary["total_edges"] > 0
    assert "CLASS" in summary["node_types_breakdown"]
    assert "FUNCTION" in summary["node_types_breakdown"]
    assert "FILE" in summary["node_types_breakdown"]
    assert "IMPORTS" in summary["edge_types_breakdown"]
    assert "DEFINES" in summary["edge_types_breakdown"]
    assert "CONTAINS" in summary["edge_types_breakdown"]
    assert summary["external_count"] >= 2  # math, fastapi, pytest


@pytest.mark.asyncio
async def test_incremental_indexing_idempotency(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test that repeat indexing with unchanged files skips reparsing and prevents duplicate nodes."""
    proj = Project(name="Idempotency Project", slug=f"idemp-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="idemp-repo",
        full_name="local/idemp-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    # Pass 1: Initial full index
    res1 = await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )
    assert res1.status_code == 200
    data1 = res1.json()

    # Pass 2: Incremental index with no file modifications
    res2 = await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": False},
        headers=auth_headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()

    # Files should be skipped
    assert data2["files_skipped"] >= 4
    assert data2["files_indexed"] == 0

    # Total node count in database should remain stable
    summary_res = await client.get(f"/api/v1/repositories/{repo.id}/graph", headers=auth_headers)
    summary = summary_res.json()
    assert summary["total_nodes"] == data1["nodes_created"]


@pytest.mark.asyncio
async def test_file_modification_and_incremental_reindexing(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test that modifying a single file reindexes only that file and adds the new symbol."""
    proj = Project(name="Mod Project", slug=f"mod-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="mod-repo",
        full_name="local/mod-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    # 1. Initial index
    await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )

    # 2. Modify src/calculator.py to add multiply method
    calc_path = Path(multi_file_git_repo) / "src" / "calculator.py"
    calc_content = calc_path.read_text()
    calc_content += '''
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b
'''
    calc_path.write_text(calc_content)
    subprocess.run(["git", "add", "."], cwd=multi_file_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add multiply method"], cwd=multi_file_git_repo, check=True, stdout=subprocess.DEVNULL)

    # 3. Incremental index
    res_mod = await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": False},
        headers=auth_headers,
    )
    assert res_mod.status_code == 200
    mod_data = res_mod.json()
    assert mod_data["files_indexed"] == 1  # only calculator.py was changed
    assert mod_data["files_skipped"] >= 3

    # 4. Verify multiply symbol exists in nodes
    nodes_res = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/nodes?q=multiply",
        headers=auth_headers,
    )
    assert nodes_res.status_code == 200
    nodes_data = nodes_res.json()
    assert nodes_data["total"] >= 1
    mult_node = nodes_data["nodes"][0]
    assert mult_node["name"] == "multiply"
    assert mult_node["node_type"] == "METHOD"


@pytest.mark.asyncio
async def test_query_nodes_and_filtering(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test filtering nodes by type, file path, and search query."""
    proj = Project(name="Filter Project", slug=f"filt-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="filt-repo",
        full_name="local/filt-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )

    # 1. Filter by node_type=CLASS
    res_class = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/nodes?node_type=CLASS",
        headers=auth_headers,
    )
    assert res_class.status_code == 200
    class_data = res_class.json()
    assert class_data["total"] >= 2
    assert all(n["node_type"] == "CLASS" for n in class_data["nodes"])

    # 2. Filter by file_path=src/formatter.py
    res_file = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/nodes?file_path=src/formatter.py",
        headers=auth_headers,
    )
    assert res_file.status_code == 200
    file_data = res_file.json()
    assert file_data["total"] >= 2  # FILE node + format_result function

    # 3. Filter by search query q=format_result
    res_search = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/nodes?q=format_result",
        headers=auth_headers,
    )
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["total"] >= 1
    assert search_data["nodes"][0]["name"] == "format_result"


@pytest.mark.asyncio
async def test_node_detail_and_bounded_dependencies(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test node detail endpoint and bounded BFS dependency traversal."""
    proj = Project(name="Dep Project", slug=f"dep-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="dep-repo",
        full_name="local/dep-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()

    await client.post(
        f"/api/v1/repositories/{repo.id}/graph/index",
        json={"force_reindex": True},
        headers=auth_headers,
    )

    # 1. Locate MathEngine node
    nodes_res = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/nodes?q=MathEngine",
        headers=auth_headers,
    )
    math_node = next(n for n in nodes_res.json()["nodes"] if n["node_type"] == "CLASS")
    math_id = math_node["id"]

    # 2. Fetch node detail
    detail_res = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/nodes/{math_id}",
        headers=auth_headers,
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["node"]["name"] == "MathEngine"
    assert "incoming_edges" in detail
    assert "outgoing_edges" in detail

    # 3. Fetch dependencies with depth 2
    deps_res = await client.get(
        f"/api/v1/repositories/{repo.id}/graph/dependencies?node_id={math_id}&direction=both&max_depth=2",
        headers=auth_headers,
    )
    assert deps_res.status_code == 200
    deps = deps_res.json()
    assert deps["root_node_id"] == math_id
    assert deps["max_depth"] == 2
    assert len(deps["nodes"]) >= 1


@pytest.mark.asyncio
async def test_cross_repository_isolation(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    multi_file_git_repo: str,
):
    """Test that a user cannot access another user's graph data."""
    # User 1 repo
    proj1 = Project(name="User 1 Proj", slug=f"u1-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj1)
    await db_session.flush()

    repo1 = Repository(
        project_id=proj1.id,
        user_id=test_user.id,
        name="u1-repo",
        full_name="local/u1-repo",
        clone_url=f"file://{multi_file_git_repo}",
        default_branch="main",
    )
    db_session.add(repo1)

    # User 2
    user2 = User(
        email=f"user2_{uuid.uuid4().hex[:6]}@devora.ai",
        full_name="User Two",
        hashed_password=get_password_hash("Password123!"),
        is_active=True,
    )
    db_session.add(user2)
    await db_session.commit()

    token2 = create_access_token(subject=str(user2.id))
    auth_headers_user2 = {"Authorization": f"Bearer {token2}"}

    # User 2 tries to access User 1's graph
    res = await client.get(
        f"/api/v1/repositories/{repo1.id}/graph",
        headers=auth_headers_user2,
    )
    assert res.status_code == 404
