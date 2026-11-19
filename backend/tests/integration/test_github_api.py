"""Integration tests for Phase 8 GitHub and Pull Request API endpoints."""
import uuid
import pytest
from httpx import AsyncClient


@pytest.fixture
async def sample_project_and_repo(client: AsyncClient, auth_headers: dict) -> tuple[str, str]:
    # 1. Create project
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "GitHub Native Project", "slug": f"gh-native-{uuid.uuid4().hex[:6]}"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 2. Create repo
    repo_resp = await client.post(
        "/api/v1/repositories",
        json={
            "project_id": proj_id,
            "name": "devora-demo",
            "full_name": "devora-org/devora-demo",
            "clone_url": "https://github.com/devora-org/devora-demo.git",
            "default_branch": "main",
            "language": "python",
        },
        headers=auth_headers,
    )
    assert repo_resp.status_code == 201
    repo_id = repo_resp.json()["id"]
    return proj_id, repo_id


@pytest.fixture
async def sample_task_id(client: AsyncClient, auth_headers: dict, sample_project_and_repo: tuple[str, str]) -> str:
    proj_id, repo_id = sample_project_and_repo
    task_resp = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "repository_id": repo_id,
            "title": "Fix division by zero in demo calculation",
            "prompt": "Investigate and patch zero denominator handling",
            "task_type": "bug_fix",
            "target_branch": "main",
        },
        headers=auth_headers,
    )
    assert task_resp.status_code == 201
    return task_resp.json()["id"]


@pytest.mark.asyncio
async def test_get_github_status(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/github/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "app_configured" in data
    assert "is_mock" in data


@pytest.mark.asyncio
async def test_connect_and_list_github_installations(client: AsyncClient, auth_headers: dict):
    # Connect installation
    payload = {
        "installation_id": 998877,
        "account_login": "devora-org",
        "account_type": "Organization",
        "repository_selection": "selected",
        "permissions": {"pull_requests": "write", "contents": "write"},
    }
    connect_resp = await client.post(
        "/api/v1/github/installations/connect",
        json=payload,
        headers=auth_headers,
    )
    assert connect_resp.status_code == 201
    inst_data = connect_resp.json()
    assert inst_data["installation_id"] == 998877
    assert inst_data["account_login"] == "devora-org"

    # List installations
    list_resp = await client.get("/api/v1/github/installations", headers=auth_headers)
    assert list_resp.status_code == 200
    installations = list_resp.json()
    assert any(i["installation_id"] == 998877 for i in installations)


@pytest.mark.asyncio
async def test_list_installation_repositories(client: AsyncClient, auth_headers: dict):
    # Connect installation first
    await client.post(
        "/api/v1/github/installations/connect",
        json={"installation_id": 998877, "account_login": "devora-org"},
        headers=auth_headers,
    )
    # List repositories for connected installation
    resp = await client.get("/api/v1/github/installations/998877/repositories", headers=auth_headers)
    assert resp.status_code == 200
    repos = resp.json()
    assert isinstance(repos, list)
    assert len(repos) >= 1
    assert "clone_url" in repos[0]
    assert "default_branch" in repos[0]


@pytest.mark.asyncio
async def test_repository_branches_endpoint(client: AsyncClient, auth_headers: dict, sample_project_and_repo: tuple[str, str]):
    _, repo_id = sample_project_and_repo
    resp = await client.get(f"/api/v1/repositories/{repo_id}/branches", headers=auth_headers)
    assert resp.status_code == 200
    branches = resp.json()
    assert isinstance(branches, list)
    assert any(b["name"] == "main" for b in branches)


@pytest.mark.asyncio
async def test_create_and_sync_pull_request_flow(client: AsyncClient, auth_headers: dict, sample_task_id: str):
    # 1. Create Pull Request for the task
    pr_resp = await client.post(f"/api/v1/pull-requests/tasks/{sample_task_id}", headers=auth_headers)
    assert pr_resp.status_code == 201
    pr_data = pr_resp.json()
    assert pr_data["pr_number"] >= 1
    assert pr_data["state"] == "open"
    assert "https://github.com/" in pr_data["html_url"]
    pr_id = pr_data["id"]

    # 2. Get PR by ID
    get_resp = await client.get(f"/api/v1/pull-requests/{pr_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == pr_id

    # 3. List PRs
    list_resp = await client.get("/api/v1/pull-requests", headers=auth_headers)
    assert list_resp.status_code == 200
    all_prs = list_resp.json()
    assert any(p["id"] == pr_id for p in all_prs)

    # 4. Synchronize PR state from GitHub
    sync_resp = await client.post(f"/api/v1/pull-requests/{pr_id}/sync", headers=auth_headers)
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert sync_data["pull_request"]["id"] == pr_id


@pytest.mark.asyncio
async def test_disconnect_github_installation(client: AsyncClient, auth_headers: dict):
    # Connect installation first
    await client.post(
        "/api/v1/github/installations/connect",
        json={"installation_id": 998877, "account_login": "devora-org"},
        headers=auth_headers,
    )
    del_resp = await client.delete("/api/v1/github/installations/998877", headers=auth_headers)
    assert del_resp.status_code == 204

    # Verify no longer returned in active list
    list_resp = await client.get("/api/v1/github/installations", headers=auth_headers)
    assert list_resp.status_code == 200
    installations = list_resp.json()
    assert not any(i["installation_id"] == 998877 for i in installations)
