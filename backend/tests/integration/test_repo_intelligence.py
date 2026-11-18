"""Integration tests for Repository Intelligence (indexing, architecture, files, symbols, search)."""
import os
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
def local_git_repo():
    """Create a temporary real git repository with sample code files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)

        # 1. Python source file
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "calculator.py").write_text('''"""Calculator module."""

class MathEngine:
    """Core mathematical operations engine."""

    def __init__(self, precision: int = 2):
        self.precision = precision

    def compute_sum(self, a: float, b: float) -> float:
        """Add two numbers."""
        return round(a + b, self.precision)

def calculate_average(numbers: list) -> float:
    """Calculate arithmetic average of a list."""
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
''')

        # 2. TypeScript utility file
        (src_dir / "formatter.ts").write_text('''export function formatResult(value: number): string {
    return `Output: ${value}`;
}
''')

        # 3. Test file
        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calc.py").write_text('''def test_dummy():
    assert True
''')

        # 4. Manifest and config
        (repo_dir / "requirements.txt").write_text("fastapi==0.110.0\npytest==8.0.0\n")
        (repo_dir / "README.md").write_text("# Sample Project\n")
        (repo_dir / ".gitignore").write_text("*.tmp\n")

        # Initialize git repo and commit files
        subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Devora Tester"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "config", "user.email", "tester@devora.ai"], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
        subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)

        yield str(repo_dir)


@pytest.mark.asyncio
async def test_full_repository_intelligence_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    local_git_repo: str,
):
    # 1. Create Project
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Intelligence Test Project", "slug": "intelligence-test-project", "description": "Testing Phase 3 engine"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Connect Repository pointing to the local git repo
    repo_resp = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": project_id,
            "name": "sample-repo",
            "full_name": "local/sample-repo",
            "clone_url": f"file://{local_git_repo}",
            "default_branch": "main",
        },
        headers=auth_headers,
    )
    assert repo_resp.status_code == 201
    repo_data = repo_resp.json()
    repo_id = repo_data["id"]
    assert repo_data["indexing_status"] == "NOT_INDEXED"

    # 3. Trigger Repository Indexing
    index_resp = await client.post(
        f"/api/v1/repositories/{repo_id}/index",
        json={"branch": "main", "force_reindex": True},
        headers=auth_headers,
    )
    assert index_resp.status_code == 202
    job_data = index_resp.json()
    assert job_data["status"] == "COMPLETED"
    assert job_data["files_count"] >= 4
    assert job_data["symbols_count"] >= 3
    assert job_data["commit_sha"] is not None

    # 4. Check Indexing Status
    status_resp = await client.get(f"/api/v1/repositories/{repo_id}/index/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "COMPLETED"

    # 5. Check Architecture & Conventions Retrieval
    arch_resp = await client.get(f"/api/v1/repositories/{repo_id}/architecture", headers=auth_headers)
    assert arch_resp.status_code == 200
    arch_data = arch_resp.json()
    assert arch_data["primary_language"] == "Python"
    assert "FastAPI" in arch_data["frameworks"]
    assert "Pytest" in arch_data["frameworks"]
    assert arch_data["total_files"] >= 4
    assert "Repository Architecture Summary" in arch_data["architecture_summary"]
    assert "Project Conventions & Practices" in arch_data["coding_conventions"]

    # 6. List Indexed Files
    files_resp = await client.get(f"/api/v1/repositories/{repo_id}/files", headers=auth_headers)
    assert files_resp.status_code == 200
    files_data = files_resp.json()
    file_paths = [f["file_path"] for f in files_data]
    assert "src/calculator.py" in file_paths
    assert "requirements.txt" in file_paths

    # 7. List Extracted Symbols
    symbols_resp = await client.get(f"/api/v1/repositories/{repo_id}/symbols", headers=auth_headers)
    assert symbols_resp.status_code == 200
    symbols_data = symbols_resp.json()
    symbol_names = [s["name"] for s in symbols_data]
    assert "MathEngine" in symbol_names
    assert any("compute_sum" in s for s in symbol_names)
    assert "calculate_average" in symbol_names

    # 8. Code Search - Symbol Search
    sym_search_resp = await client.get(
        f"/api/v1/repositories/{repo_id}/search",
        params={"q": "MathEngine", "search_type": "symbol"},
        headers=auth_headers,
    )
    assert sym_search_resp.status_code == 200
    sym_search = sym_search_resp.json()
    assert sym_search["total_matches"] >= 1
    assert any(r["symbol_name"] == "MathEngine" for r in sym_search["results"])

    # 9. Code Search - Keyword Search
    kw_search_resp = await client.get(
        f"/api/v1/repositories/{repo_id}/search",
        params={"q": "compute_sum", "search_type": "keyword"},
        headers=auth_headers,
    )
    assert kw_search_resp.status_code == 200
    kw_search = kw_search_resp.json()
    assert kw_search["total_matches"] >= 1
    assert any("compute_sum" in r["snippet"] for r in kw_search["results"])

    # 10. Code Search - Semantic Search
    sem_search_resp = await client.get(
        f"/api/v1/repositories/{repo_id}/search",
        params={"q": "mathematical calculation", "search_type": "semantic"},
        headers=auth_headers,
    )
    assert sem_search_resp.status_code == 200
    sem_search = sem_search_resp.json()
    assert len(sem_search["results"]) > 0

    # 11. Incremental Re-indexing (no new commit, force_reindex=False)
    reindex_resp = await client.post(
        f"/api/v1/repositories/{repo_id}/index",
        json={"branch": "main", "force_reindex": False},
        headers=auth_headers,
    )
    assert reindex_resp.status_code == 202
    assert reindex_resp.json()["id"] == job_data["id"]  # Returns existing completed job


@pytest.mark.asyncio
async def test_repository_intelligence_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    # Create another user
    other_user = User(
        email="other@devora.ai",
        full_name="Other User",
        hashed_password=get_password_hash("OtherPass123!"),
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.flush()

    other_token = create_access_token(subject=str(other_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # User A creates project and repo
    proj = Project(name="Project A", slug="project-a", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="private-repo",
        full_name="test/private-repo",
        clone_url="https://github.com/test/private-repo",
    )
    db_session.add(repo)
    await db_session.flush()

    # User B cannot access architecture or search
    arch_resp = await client.get(f"/api/v1/repositories/{repo.id}/architecture", headers=other_headers)
    assert arch_resp.status_code == 404

    search_resp = await client.get(
        f"/api/v1/repositories/{repo.id}/search",
        params={"q": "test"},
        headers=other_headers,
    )
    assert search_resp.status_code == 404

    index_resp = await client.post(f"/api/v1/repositories/{repo.id}/index", headers=other_headers)
    assert index_resp.status_code == 404
