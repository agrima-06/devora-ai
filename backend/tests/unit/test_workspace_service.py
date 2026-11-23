"""Unit tests for WorkspaceService graph persistence and package impact analysis."""

import json
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.repository import Repository
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.models.user import User
from app.services.workspace_service import WorkspaceService


@pytest.fixture
def mock_monorepo(tmp_path):
    """Create a temporary multi-package repository."""
    # Root package.json
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "devora-root", "workspaces": ["packages/*"]}),
        encoding="utf-8",
    )

    # 1. packages/core
    core_dir = tmp_path / "packages" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "package.json").write_text(
        json.dumps({"name": "@devora/core", "version": "1.0.0", "dependencies": {"lodash": "^4.17.21"}}),
        encoding="utf-8",
    )
    (core_dir / "index.js").write_text("module.exports = { core: true };", encoding="utf-8")

    # 2. packages/api (depends on @devora/core)
    api_dir = tmp_path / "packages" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "package.json").write_text(
        json.dumps({"name": "@devora/api", "version": "1.0.0", "dependencies": {"@devora/core": "*"}}),
        encoding="utf-8",
    )
    (api_dir / "server.js").write_text("const core = require('@devora/core');", encoding="utf-8")

    # 3. packages/client (depends on @devora/api)
    client_dir = tmp_path / "packages" / "client"
    client_dir.mkdir(parents=True)
    (client_dir / "package.json").write_text(
        json.dumps({"name": "@devora/client", "version": "1.0.0", "dependencies": {"@devora/api": "*"}}),
        encoding="utf-8",
    )
    (client_dir / "app.js").write_text("const api = require('@devora/api');", encoding="utf-8")

    return tmp_path


@pytest.mark.asyncio
async def test_workspace_indexing_and_graph_persistence(
    db_session: AsyncSession,
    test_user: User,
    mock_monorepo: Path,
):
    """Verify that index_workspaces persists WORKSPACE and PACKAGE nodes and relational edges."""
    proj = Project(name="Workspace Proj", slug=f"ws-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="monorepo",
        full_name="local/monorepo",
        clone_url="file:///tmp/repo",
    )
    db_session.add(repo)
    await db_session.commit()

    service = WorkspaceService()
    index_res = await service.index_workspaces(
        repository_id=repo.id,
        repo_path=mock_monorepo,
        db=db_session,
    )

    assert index_res.status_code if hasattr(index_res, "status_code") else True
    assert index_res.workspaces_found == 1
    assert index_res.packages_indexed == 3
    assert index_res.edges_created >= 3

    # Verify nodes in database
    nodes = (
        await db_session.execute(
            select(RepositoryGraphNode).where(RepositoryGraphNode.repository_id == repo.id)
        )
    ).scalars().all()

    node_types = {n.node_type for n in nodes}
    assert "WORKSPACE" in node_types
    assert "PACKAGE" in node_types

    pkg_names = {n.name for n in nodes if n.node_type == "PACKAGE"}
    assert "@devora/core" in pkg_names
    assert "@devora/api" in pkg_names
    assert "@devora/client" in pkg_names

    # Verify edges in database
    edges = (
        await db_session.execute(
            select(RepositoryGraphEdge).where(RepositoryGraphEdge.repository_id == repo.id)
        )
    ).scalars().all()

    edge_types = {e.edge_type for e in edges}
    assert "WORKSPACE_CONTAINS" in edge_types
    assert "PACKAGE_DEPENDS_ON" in edge_types


@pytest.mark.asyncio
async def test_get_workspace_graph_and_dependencies(
    db_session: AsyncSession,
    test_user: User,
    mock_monorepo: Path,
):
    """Verify get_workspace_graph and get_package_dependencies queries."""
    proj = Project(name="WS Query Proj", slug=f"wsq-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="ws-query-repo",
        full_name="local/ws-query",
        clone_url="file:///tmp/repo",
    )
    db_session.add(repo)
    await db_session.commit()

    service = WorkspaceService()
    await service.index_workspaces(repo.id, mock_monorepo, db_session)

    # 1. Workspace graph topology
    graph_resp = await service.get_workspace_graph(repo.id, db_session)
    assert graph_resp.summary.is_monorepo is True
    assert graph_resp.summary.total_workspaces == 1
    assert graph_resp.summary.total_packages == 3
    assert len(graph_resp.cross_package_edges) == 2  # api -> core, client -> api

    # 2. Package dependencies for @devora/api
    deps_resp = await service.get_package_dependencies(repo.id, "@devora/api", db_session)
    assert deps_resp.package_name == "@devora/api"
    assert len(deps_resp.internal_dependencies) == 1
    assert deps_resp.internal_dependencies[0].name == "@devora/core"
    assert len(deps_resp.dependents) == 1
    assert deps_resp.dependents[0].name == "@devora/client"


@pytest.mark.asyncio
async def test_get_package_impact_blast_radius(
    db_session: AsyncSession,
    test_user: User,
    mock_monorepo: Path,
):
    """Verify package-level blast radius traversal."""
    proj = Project(name="Impact Proj", slug=f"wsi-{uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(proj)
    await db_session.flush()

    repo = Repository(
        project_id=proj.id,
        user_id=test_user.id,
        name="ws-impact-repo",
        full_name="local/ws-impact",
        clone_url="file:///tmp/repo",
    )
    db_session.add(repo)
    await db_session.commit()

    service = WorkspaceService()
    await service.index_workspaces(repo.id, mock_monorepo, db_session)

    # Impact when @devora/core is changed: should impact @devora/api (depth 1) and @devora/client (depth 2)
    impact_resp = await service.get_package_impact(repo.id, "@devora/core", db_session)
    assert impact_resp.package_name == "@devora/core"
    assert impact_resp.affected_packages_count == 2
    assert impact_resp.severity in ["MEDIUM", "HIGH"]

    affected_names = [a.package_name for a in impact_resp.affected_packages]
    assert "@devora/api" in affected_names
    assert "@devora/client" in affected_names

    # Check dependency path for transitive consumer
    client_item = next(a for a in impact_resp.affected_packages if a.package_name == "@devora/client")
    assert client_item.depth == 2
    assert client_item.dependency_path == ["@devora/core", "@devora/api", "@devora/client"]
