"""Integration tests for Phase 10 Stage 10.3: Workspace & Package Intelligence REST APIs."""

import json
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.repository import Repository
from app.models.user import User
from app.services.workspace_service import WorkspaceService


@pytest.fixture
def test_monorepo_dir(tmp_path):
    """Create a temporary multi-package repository on disk."""
    # Root package.json
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "workspace-api-repo", "workspaces": ["packages/*"]}),
        encoding="utf-8",
    )

    # 1. packages/core
    core = tmp_path / "packages" / "core"
    core.mkdir(parents=True)
    (core / "package.json").write_text(
        json.dumps({"name": "@devora/core", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (core / "index.js").write_text("console.log('core');", encoding="utf-8")

    # 2. packages/api
    api = tmp_path / "packages" / "api"
    api.mkdir(parents=True)
    (api / "package.json").write_text(
        json.dumps({"name": "@devora/api", "version": "1.0.0", "dependencies": {"@devora/core": "*"}}),
        encoding="utf-8",
    )
    (api / "server.js").write_text("console.log('api');", encoding="utf-8")

    return tmp_path


@pytest.mark.asyncio
async def test_workspace_api_lifecycle(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
    test_monorepo_dir: Path,
):
    """Test full API lifecycle: index, fetch workspaces, packages, dependencies, dependents, impact."""
    proj = Project(name="Workspace API Proj", slug=f"wsapi-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="ws-api-repo",
        full_name="local/ws-api-repo",
        clone_url="file:///tmp/repo",
    )
    db_session.add(repo)
    await db_session.commit()

    # 1. POST /repositories/{id}/workspaces/index
    index_res = await client.post(
        f"/api/v1/repositories/{repo.id}/workspaces/index",
        json={"local_path": str(test_monorepo_dir)},
        headers=auth_headers,
    )
    assert index_res.status_code == 200
    idx_data = index_res.json()
    assert idx_data["workspaces_found"] == 1
    assert idx_data["packages_indexed"] == 2
    assert idx_data["edges_created"] >= 2

    # 2. GET /repositories/{id}/workspaces
    ws_res = await client.get(
        f"/api/v1/repositories/{repo.id}/workspaces",
        headers=auth_headers,
    )
    assert ws_res.status_code == 200
    ws_data = ws_res.json()
    assert ws_data["summary"]["is_monorepo"] is True
    assert ws_data["summary"]["total_packages"] == 2
    assert len(ws_data["workspaces"]) == 1
    ws_id = ws_data["workspaces"][0]["id"]

    # 3. GET /repositories/{id}/workspaces/{workspace_id}
    detail_res = await client.get(
        f"/api/v1/repositories/{repo.id}/workspaces/{ws_id}",
        headers=auth_headers,
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["workspace_type"] in ["npm", "pnpm", "yarn", "turborepo"]

    # 4. GET /repositories/{id}/packages
    pkgs_res = await client.get(
        f"/api/v1/repositories/{repo.id}/packages",
        headers=auth_headers,
    )
    assert pkgs_res.status_code == 200
    pkgs_list = pkgs_res.json()
    assert len(pkgs_list) == 2
    pkg_names = [p["name"] for p in pkgs_list]
    assert "@devora/core" in pkg_names
    assert "@devora/api" in pkg_names

    core_pkg = next(p for p in pkgs_list if p["name"] == "@devora/core")
    api_pkg = next(p for p in pkgs_list if p["name"] == "@devora/api")

    # 5. GET /repositories/{id}/packages/{package_id}/dependencies
    api_deps_res = await client.get(
        f"/api/v1/repositories/{repo.id}/packages/{api_pkg['id']}/dependencies",
        headers=auth_headers,
    )
    assert api_deps_res.status_code == 200
    api_deps_data = api_deps_res.json()
    assert len(api_deps_data["internal_dependencies"]) == 1
    assert api_deps_data["internal_dependencies"][0]["name"] == "@devora/core"

    # 6. GET /repositories/{id}/packages/{package_id}/dependents
    core_dependents_res = await client.get(
        f"/api/v1/repositories/{repo.id}/packages/{core_pkg['id']}/dependents",
        headers=auth_headers,
    )
    assert core_dependents_res.status_code == 200
    dependents_list = core_dependents_res.json()
    assert len(dependents_list) == 1
    assert dependents_list[0]["name"] == "@devora/api"

    # 7. GET /repositories/{id}/packages/{package_id}/impact
    impact_res = await client.get(
        f"/api/v1/repositories/{repo.id}/packages/{core_pkg['id']}/impact",
        headers=auth_headers,
    )
    assert impact_res.status_code == 200
    impact_data = impact_res.json()
    assert impact_data["package_name"] == "@devora/core"
    assert impact_data["affected_packages_count"] == 1
    assert impact_data["affected_packages"][0]["package_name"] == "@devora/api"
    assert len(impact_data["recommendations"]) > 0


@pytest.mark.asyncio
async def test_workspace_api_tenant_isolation(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify unauthorized or unauthenticated requests are strictly blocked."""
    # 1. Unauthenticated request -> 401
    random_repo_id = uuid.uuid4()
    unauth_res = await client.get(f"/api/v1/repositories/{random_repo_id}/workspaces")
    assert unauth_res.status_code == 401

    # 2. Another user's repository -> 404 / access denied
    other_user = User(
        email=f"other-{uuid.uuid4().hex[:6]}@example.com",
        full_name="Other User",
        hashed_password="hash",
    )
    db_session.add(other_user)
    await db_session.flush()

    other_proj = Project(name="Other Proj", slug=f"oth-{uuid.uuid4().hex[:6]}", owner_id=other_user.id)
    db_session.add(other_proj)
    await db_session.flush()

    other_repo = Repository(
        project_id=other_proj.id,
        user_id=other_user.id,
        name="foreign-repo",
        full_name="other/foreign-repo",
        clone_url="file:///tmp/other",
    )
    db_session.add(other_repo)
    await db_session.commit()

    # Authenticated test_user queries other_user's repo -> 404
    tenant_res = await client.get(
        f"/api/v1/repositories/{other_repo.id}/workspaces",
        headers=auth_headers,
    )
    assert tenant_res.status_code == 404
