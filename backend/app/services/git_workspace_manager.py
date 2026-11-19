"""Git workspace and branch management service for isolated autonomous development."""
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.exceptions import BadRequestException, DevoraException
from app.core.logging import get_logger

logger = get_logger("git_workspace_manager")

# Scrub token from any git command output or logs
TOKEN_SCRUB_REGEX = re.compile(r"x-access-token:[a-zA-Z0-9_\-]+@")


def scrub_tokens(text: str) -> str:
    """Mask any GitHub access tokens from log strings or command outputs."""
    if not text:
        return ""
    return TOKEN_SCRUB_REGEX.sub("x-access-token:[REDACTED]@", text)


class GitWorkspaceManager:
    """Manages isolated local task workspaces, git branches, commits, and pushes."""

    def __init__(self, base_tasks_dir: Optional[Path] = None):
        self.base_tasks_dir = base_tasks_dir or Path(os.environ.get("DEVORA_TASKS_DIR", "/tmp/devora/tasks"))
        self.base_tasks_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_branch_name(task_type: str, task_id: str) -> str:
        """Generate deterministic, collision-free branch name: devora/{type}-{id[:8]}."""
        safe_type = re.sub(r"[^a-zA-Z0-9]", "", task_type or "fix").lower()
        clean_id = re.sub(r"[^a-zA-Z0-9]", "", str(task_id))[:8]
        return f"devora/{safe_type}-{clean_id}"

    @staticmethod
    def sanitize_branch_name(branch_name: str) -> str:
        """Strip illegal characters for git branch names."""
        return re.sub(r"[^a-zA-Z0-9_\-\./]", "", branch_name)

    def get_task_workspace_path(self, task_id: str) -> Path:
        """Resolve isolated task workspace path and prevent directory traversal."""
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", str(task_id))
        workspace = (self.base_tasks_dir / safe_id / "workspace").resolve()
        if not str(workspace).startswith(str(self.base_tasks_dir.resolve())):
            raise BadRequestException("Path traversal attempt detected in task identifier.")
        return workspace

    def _run_git_cmd(
        self,
        args: List[str],
        cwd: Path,
        timeout: int = 90,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        """Execute a git command safely using an argument array without shell=True."""
        cmd_env = os.environ.copy()
        cmd_env.update({
            "GIT_AUTHOR_NAME": "Devora AI Engine",
            "GIT_AUTHOR_EMAIL": "engine@devora.ai",
            "GIT_COMMITTER_NAME": "Devora AI Engine",
            "GIT_COMMITTER_EMAIL": "engine@devora.ai",
        })
        if env:
            cmd_env.update(env)

        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=cmd_env,
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error("git_command_timeout", args=args, cwd=str(cwd))
            raise BadRequestException(f"Git operation timed out after {timeout} seconds.")
        except Exception as exc:
            logger.error("git_command_error", error=str(exc), args=args)
            raise BadRequestException(f"Git command failed: {scrub_tokens(str(exc))}")

    def prepare_task_workspace(
        self,
        task_id: str,
        repo_clone_url: str,
        base_branch: str = "main",
        task_branch: Optional[str] = None,
        token: Optional[str] = None,
        source_repo_dir: Optional[Path] = None,
        preserve_existing: bool = False,
    ) -> Path:
        """Initialize task workspace, ensure git repository, checkout base, and create task branch."""
        workspace = self.get_task_workspace_path(task_id)
        task_dir = workspace.parent
        task_dir.mkdir(parents=True, exist_ok=True)

        # In recovery scenarios, preserve existing modified files and git working tree if intact
        if preserve_existing and workspace.exists() and (workspace / ".git").exists():
            logger.info(
                "workspace_preserved_for_recovery",
                task_id=task_id,
                workspace=str(workspace),
            )
            clean_url = repo_clone_url.strip() if repo_clone_url else ""
            if clean_url:
                self._run_git_cmd(["remote", "remove", "origin"], cwd=workspace)
                self._run_git_cmd(["remote", "add", "origin", clean_url], cwd=workspace)

            active_branch = task_branch or self.generate_branch_name("fix", task_id)
            safe_branch = self.sanitize_branch_name(active_branch)
            # Ensure we are on the task branch without discarding uncommitted working changes
            self._run_git_cmd(["checkout", safe_branch], cwd=workspace)
            return workspace

        # Clean existing workspace if needed
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=True)

        # 1. Populate workspace from source directory if available
        if source_repo_dir and Path(source_repo_dir).exists() and Path(source_repo_dir).is_dir():
            shutil.copytree(source_repo_dir, workspace, dirs_exist_ok=True)
            logger.info("workspace_copied_from_source", source=str(source_repo_dir), dest=str(workspace))

        # 2. Ensure git repository is initialized
        git_dir = workspace / ".git"
        if not git_dir.exists():
            init_res = self._run_git_cmd(["init", "-b", base_branch], cwd=workspace)
            if init_res.returncode != 0:
                raise BadRequestException(f"Failed to initialize git repository: {init_res.stderr}")

            # Configure identity locally
            self._run_git_cmd(["config", "user.name", "Devora AI Engine"], cwd=workspace)
            self._run_git_cmd(["config", "user.email", "engine@devora.ai"], cwd=workspace)

            # Check if any commits exist; if empty, create initial baseline commit
            log_res = self._run_git_cmd(["log", "-1"], cwd=workspace)
            if log_res.returncode != 0:
                self._run_git_cmd(["add", "."], cwd=workspace)
                self._run_git_cmd(["commit", "-m", "chore: initialize task baseline", "--allow-empty"], cwd=workspace)

        # 3. Configure remote origin if valid clone url provided
        clean_url = repo_clone_url.strip() if repo_clone_url else ""
        if clean_url:
            self._run_git_cmd(["remote", "remove", "origin"], cwd=workspace)
            self._run_git_cmd(["remote", "add", "origin", clean_url], cwd=workspace)

        # 4. Check out or create task branch
        active_branch = task_branch or self.generate_branch_name("fix", task_id)
        safe_branch = self.sanitize_branch_name(active_branch)

        # Create branch from current base
        checkout_res = self._run_git_cmd(["checkout", "-B", safe_branch], cwd=workspace)
        if checkout_res.returncode != 0:
            raise BadRequestException(f"Failed to checkout task branch '{safe_branch}': {checkout_res.stderr}")

        logger.info(
            "task_workspace_prepared",
            task_id=task_id,
            workspace=str(workspace),
            branch=safe_branch,
            base_branch=base_branch,
        )
        return workspace

    def get_status(self, workspace_path: Path) -> Dict[str, Any]:
        """Fetch porcelain status of git workspace."""
        if not (workspace_path / ".git").exists():
            return {"is_clean": True, "files": [], "modified": [], "untracked": []}

        res = self._run_git_cmd(["status", "--porcelain"], cwd=workspace_path)
        if res.returncode != 0:
            raise BadRequestException(f"Failed to inspect git status: {res.stderr}")

        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        modified: List[str] = []
        untracked: List[str] = []

        for line in lines:
            status_code = line[:2]
            filename = line[3:].strip()
            if "??" in status_code:
                untracked.append(filename)
            else:
                modified.append(filename)

        return {
            "is_clean": len(lines) == 0,
            "total_changes": len(lines),
            "modified": modified,
            "untracked": untracked,
            "raw_porcelain": res.stdout,
        }

    def get_diff(self, workspace_path: Path, base_branch: Optional[str] = None) -> str:
        """Generate git diff against base branch or current working tree."""
        if not (workspace_path / ".git").exists():
            return ""

        if base_branch:
            # Diff against base branch if available
            res = self._run_git_cmd(["diff", base_branch], cwd=workspace_path)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout

        # Fallback to unstaged / staged changes in working tree
        res = self._run_git_cmd(["diff", "HEAD"], cwd=workspace_path)
        if res.returncode == 0:
            return res.stdout

        # Simple working tree diff
        res = self._run_git_cmd(["diff"], cwd=workspace_path)
        return res.stdout if res.returncode == 0 else ""

    def commit_changes(
        self,
        workspace_path: Path,
        message: str,
        files: Optional[List[str]] = None,
    ) -> str:
        """Stage modified files, commit with structured message, and return commit SHA."""
        if not (workspace_path / ".git").exists():
            raise BadRequestException(f"Workspace '{workspace_path}' is not a valid git repository.")

        # Stage files
        if files:
            for f in files:
                self._run_git_cmd(["add", f], cwd=workspace_path)
        else:
            self._run_git_cmd(["add", "."], cwd=workspace_path)

        # Check if there are staged changes
        staged_check = self._run_git_cmd(["diff", "--cached", "--quiet"], cwd=workspace_path)
        if staged_check.returncode == 0:
            # Nothing staged to commit, return current HEAD commit
            head_res = self._run_git_cmd(["rev-parse", "HEAD"], cwd=workspace_path)
            if head_res.returncode == 0:
                return head_res.stdout.strip()
            return ""

        # Perform commit
        clean_msg = message.strip() or "fix: autonomous engineering modifications"
        commit_res = self._run_git_cmd(["commit", "-m", clean_msg], cwd=workspace_path)
        if commit_res.returncode != 0:
            raise BadRequestException(f"Failed to commit git modifications: {commit_res.stderr}")

        # Retrieve commit SHA
        sha_res = self._run_git_cmd(["rev-parse", "HEAD"], cwd=workspace_path)
        if sha_res.returncode != 0:
            raise BadRequestException("Failed to retrieve git commit SHA.")

        sha = sha_res.stdout.strip()
        logger.info("git_changes_committed", workspace=str(workspace_path), sha=sha)
        return sha

    def push_branch(
        self,
        workspace_path: Path,
        branch_name: str,
        remote_url: str,
        token: Optional[str] = None,
    ) -> bool:
        """Push task branch to remote repository using installation token, scrubbing credentials."""
        safe_branch = self.sanitize_branch_name(branch_name)

        # Check mock mode or offline mode
        is_mock = (
            os.environ.get("DEVORA_MOCK_GITHUB", "").lower() in ("true", "1", "yes")
            or not token
            or token.startswith("ghs_mock_")
            or remote_url.startswith("file://")
            or not remote_url.startswith("http")
        )

        if is_mock:
            logger.info(
                "mock_push_branch_simulated",
                branch=safe_branch,
                remote=scrub_tokens(remote_url),
            )
            return True

        # Build authenticated remote push URL: https://x-access-token:{token}@github.com/...
        clean_url = remote_url.strip()
        if clean_url.startswith("https://"):
            auth_url = f"https://x-access-token:{token}@{clean_url[8:]}"
        else:
            auth_url = clean_url

        try:
            # Execute push directly using authenticated URL
            push_res = self._run_git_cmd(
                ["push", auth_url, f"{safe_branch}:{safe_branch}", "--force"],
                cwd=workspace_path,
                timeout=60,
            )
            if push_res.returncode != 0:
                err_msg = scrub_tokens(push_res.stderr or push_res.stdout)
                logger.error("git_push_failed", error=err_msg, branch=safe_branch)
                raise BadRequestException(f"Failed to push git branch: {err_msg}")

            logger.info("git_branch_pushed", branch=safe_branch, remote=scrub_tokens(clean_url))
            return True
        finally:
            # Ensure local git remote config never stores the access token
            self._run_git_cmd(["remote", "set-url", "origin", clean_url], cwd=workspace_path)

    def cleanup_task_workspace(self, task_id: str) -> None:
        """Remove task workspace directory when task is completed or archived."""
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", str(task_id))
        task_dir = self.base_tasks_dir / safe_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
            logger.info("task_workspace_cleaned", task_id=task_id)
