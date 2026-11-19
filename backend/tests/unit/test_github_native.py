"""Unit tests for Phase 8 GitHub-Native Autonomous Engineering: App Service, Git Manager, PR Service."""
import os
import shutil
import tempfile
import uuid
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.file_change import FileChange
from app.models.github_pull_request import GitHubPullRequest
from app.models.report import Report
from app.models.repository import Repository
from app.models.task import Task
from app.services.git_workspace_manager import GitWorkspaceManager, scrub_tokens
from app.services.github_app_service import GitHubAppService
from app.services.pull_request_service import PullRequestService


# ---------------------------------------------------------------------------
# GitHubAppService Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_app_service_token_and_mock_fallback():
    service = GitHubAppService(is_mock=True)
    token = await service.get_installation_access_token(12345)
    assert token.startswith("ghs_mock_token_12345_")

    # Cached token check
    token2 = await service.get_installation_access_token(12345)
    assert token == token2


@pytest.mark.asyncio
async def test_github_app_service_list_repositories():
    service = GitHubAppService(is_mock=True)
    repos = await service.list_installation_repositories(12345)
    assert len(repos) >= 2
    assert repos[0]["name"] == "devora-sample-repo"
    assert repos[0]["default_branch"] == "main"
    assert repos[0]["permissions"]["push"] is True


@pytest.mark.asyncio
async def test_github_app_service_create_and_get_pull_request():
    service = GitHubAppService(is_mock=True)
    pr = await service.create_pull_request(
        owner="devora-org",
        repo="sample-repo",
        title="[Devora] Fix memory leak",
        body="Detailed resolution report",
        head="devora/fix-4a2b1c3d",
        base="main",
        token="ghs_mock_token_12345",
    )
    assert pr["number"] >= 1
    assert pr["state"] == "open"
    assert pr["title"] == "[Devora] Fix memory leak"
    assert "https://github.com/devora-org/sample-repo/pull/" in pr["html_url"]

    fetched = await service.get_pull_request(
        owner="devora-org",
        repo="sample-repo",
        pull_number=pr["number"],
        token="ghs_mock_token_12345",
    )
    assert fetched["number"] == pr["number"]
    assert fetched["state"] == "open"


def test_token_scrubbing_utility():
    dirty_log = "Error pushing to https://x-access-token:ghs_secret_token_12345@github.com/org/repo.git"
    clean_log = scrub_tokens(dirty_log)
    assert "ghs_secret_token_12345" not in clean_log
    assert "x-access-token:[REDACTED]@" in clean_log


# ---------------------------------------------------------------------------
# GitWorkspaceManager Tests
# ---------------------------------------------------------------------------


def test_git_workspace_manager_branch_naming():
    branch = GitWorkspaceManager.generate_branch_name("bug_fix", "4a2b1c3d-0000-0000-0000-000000000000")
    assert branch == "devora/bugfix-4a2b1c3d"

    sanitized = GitWorkspaceManager.sanitize_branch_name("feature/test;rm -rf /")
    assert ";" not in sanitized
    assert " " not in sanitized


def test_git_workspace_manager_lifecycle():
    temp_dir = Path(tempfile.mkdtemp(prefix="devora_test_tasks_"))
    try:
        manager = GitWorkspaceManager(base_tasks_dir=temp_dir)
        task_id = "test-task-1234"

        # 1. Prepare workspace
        ws = manager.prepare_task_workspace(
            task_id=task_id,
            repo_clone_url="https://github.com/devora-org/sample.git",
            base_branch="main",
            task_branch="devora/test-branch",
        )
        assert ws.exists()
        assert (ws / ".git").exists()

        # 2. Check clean status
        status = manager.get_status(ws)
        assert status["is_clean"] is True

        # 3. Modify a file
        test_file = ws / "calculator.py"
        test_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        status_after = manager.get_status(ws)
        assert status_after["is_clean"] is False
        assert len(status_after["untracked"]) == 1

        # 4. Commit changes
        sha = manager.commit_changes(ws, "feat: add calculator function")
        assert len(sha) == 40  # Valid 40-character hex commit SHA

        status_committed = manager.get_status(ws)
        assert status_committed["is_clean"] is True

        # 5. Push branch (mock mode test)
        pushed = manager.push_branch(
            workspace_path=ws,
            branch_name="devora/test-branch",
            remote_url="https://github.com/devora-org/sample.git",
            token="ghs_mock_token_12345",
        )
        assert pushed is True

        # 6. Cleanup
        manager.cleanup_task_workspace(task_id)
        assert not ws.exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# PullRequestService Tests
# ---------------------------------------------------------------------------


def test_pull_request_service_content_synthesis():
    task = Task(
        id=uuid.uuid4(),
        title="ZeroDivisionError when dividing by zero in calculator",
        task_type="bug_fix",
        target_branch="main",
        task_branch="devora/bugfix-a1b2c3d4",
    )
    report = Report(
        title="ZeroDivisionError Resolution",
        summary="Handled zero division by raising ValueError.",
        root_cause_analysis="Denominator was passed to div operator without zero checking.",
        test_summary={"passed": 3, "failed": 0, "duration_seconds": 0.42},
        markdown_content="# Report\n\nAll tests passed.",
    )
    file_changes = [
        FileChange(
            file_path="src/calc.py",
            change_type="modified",
            diff="--- a/src/calc.py\n+++ b/src/calc.py",
        )
    ]

    title, body = PullRequestService.generate_pr_content(
        task=task,
        report=report,
        file_changes=file_changes,
        quality_score=95,
    )

    assert title == "[Devora] ZeroDivisionError when dividing by zero in calculator"
    assert "## Summary of Changes" in body
    assert "Identified Root Cause" in body
    assert "Denominator was passed to div operator" in body
    assert "`src/calc.py` (MODIFIED)" in body
    assert "3 passed, 0 failed in isolated sandbox (0.42s)" in body
    assert "95/100 (Approved)" in body
    assert "Docker isolated (`--network none`, cpus 2.0, memory 1500m)" in body
    assert "Pre-Merge Checklist" in body
    assert str(task.id) in body
