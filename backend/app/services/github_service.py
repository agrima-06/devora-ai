"""GitHub repository integration service: URL validation, secure cloning, and metadata extraction."""
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger

logger = get_logger("github_service")

# Regex pattern for validating GitHub repository URLs
GITHUB_HTTPS_REGEX = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?/?$"
)
GITHUB_SSH_REGEX = re.compile(
    r"^git@github\.com:([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?$"
)


class GitHubService:
    """Service handling repository validation, cloning, and branch metadata."""

    def __init__(self, base_workspace_dir: Optional[str] = None):
        self.base_workspace_dir = Path(
            base_workspace_dir or os.environ.get("DEVORA_WORKSPACE_DIR", "/tmp/devora/repos")
        )
        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def parse_github_url(url: str) -> Tuple[str, str]:
        """Validate and parse a GitHub URL into (owner, repo_name).
        Also supports local test paths starting with file:// or existing directories for testing.
        """
        if not url or not isinstance(url, str):
            raise BadRequestException("Repository clone URL cannot be empty.")

        url = url.strip()

        # Check standard HTTPS
        match = GITHUB_HTTPS_REGEX.match(url)
        if match:
            return match.group(1), match.group(2)

        # Check SSH
        match = GITHUB_SSH_REGEX.match(url)
        if match:
            return match.group(1), match.group(2)

        # Check local test directory or file URI
        if url.startswith("file://") or os.path.isdir(url):
            clean_path = url.replace("file://", "")
            if os.path.exists(clean_path):
                name = os.path.basename(clean_path.rstrip("/")) or "test-repo"
                return "local", name

        raise BadRequestException(
            f"Invalid repository URL '{url}'. Expected format: https://github.com/owner/repository"
        )

    def get_repo_dir(self, repository_id: str) -> Path:
        """Resolve isolated local workspace path for a repository."""
        # Sanitize path to prevent directory traversal
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", str(repository_id))
        repo_path = (self.base_workspace_dir / safe_id).resolve()
        if not str(repo_path).startswith(str(self.base_workspace_dir.resolve())):
            raise BadRequestException("Path traversal attempt detected in repository identifier.")
        return repo_path

    def clone_or_update(
        self,
        repository_id: str,
        clone_url: str,
        branch: str = "main",
        token: Optional[str] = None,
    ) -> Dict[str, str]:
        """Clone repository into isolated workspace, or update and checkout target branch."""
        owner, repo_name = self.parse_github_url(clone_url)
        repo_dir = self.get_repo_dir(repository_id)

        # Build authenticated URL if token provided
        auth_url = clone_url
        if token and clone_url.startswith("https://github.com/"):
            auth_url = clone_url.replace(
                "https://github.com/",
                f"https://x-access-token:{token}@github.com/",
            )

        try:
            if not repo_dir.exists() or not (repo_dir / ".git").exists():
                # Clean any partial directory
                if repo_dir.exists():
                    shutil.rmtree(repo_dir)

                logger.info("cloning_repository", repo_id=str(repository_id), branch=branch)
                # Clone repository
                clone_cmd = [
                    "git",
                    "clone",
                    "--depth",
                    "50",
                    "--branch",
                    branch,
                    auth_url,
                    str(repo_dir),
                ]
                self._run_git_cmd(clone_cmd, cwd=None, token=token)
            else:
                logger.info("updating_repository", repo_id=str(repository_id), branch=branch)
                # Fetch and checkout branch
                fetch_cmd = ["git", "fetch", "--depth", "50", "origin", branch]
                self._run_git_cmd(fetch_cmd, cwd=repo_dir, token=token)

                checkout_cmd = ["git", "checkout", branch]
                self._run_git_cmd(checkout_cmd, cwd=repo_dir, token=token)

                pull_cmd = ["git", "reset", "--hard", f"origin/{branch}"]
                self._run_git_cmd(pull_cmd, cwd=repo_dir, token=token)

            # Extract HEAD metadata
            commit_sha = self._run_git_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir).strip()
            commit_msg = self._run_git_cmd(
                ["git", "log", "-1", "--pretty=%B"], cwd=repo_dir
            ).strip()
            commit_author = self._run_git_cmd(
                ["git", "log", "-1", "--pretty=%an <%ae>"], cwd=repo_dir
            ).strip()

            return {
                "workspace_path": str(repo_dir),
                "commit_sha": commit_sha,
                "commit_message": commit_msg,
                "commit_author": commit_author,
                "branch": branch,
            }

        except Exception as exc:
            # Clean sensitive token from error message
            err_msg = str(exc)
            if token:
                err_msg = err_msg.replace(token, "[REDACTED_TOKEN]")
            logger.error("git_operation_failed", error=err_msg, repo_id=str(repository_id))
            raise BadRequestException(f"Failed to access or clone repository: {err_msg}")

    def _run_git_cmd(
        self, cmd: list, cwd: Optional[Path] = None, token: Optional[str] = None
    ) -> str:
        """Run git command with strict timeout and output sanitization."""
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or exc.stdout or "Git command failed"
            if token:
                stderr = stderr.replace(token, "[REDACTED_TOKEN]")
            raise BadRequestException(stderr.strip())
        except subprocess.TimeoutExpired:
            raise BadRequestException("Git command timed out after 90 seconds.")
