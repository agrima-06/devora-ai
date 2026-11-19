"""GitHub App integration service: RS256 JWT, installation access tokens, and GitHub REST API client."""
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
import jwt

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger

logger = get_logger("github_app_service")

# Regex to scrub sensitive access tokens from URLs and logs
TOKEN_SCRUB_REGEX = re.compile(r"x-access-token:[a-zA-Z0-9_\-]+@")


class GitHubAppService:
    """Service managing GitHub App authentication, short-lived tokens, and REST API calls."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
        token_fallback: Optional[str] = None,
        is_mock: bool = False,
    ):
        self.app_id = app_id or os.environ.get("GITHUB_APP_ID")
        self.private_key = private_key or os.environ.get("GITHUB_APP_PRIVATE_KEY")
        self.token_fallback = token_fallback or settings.GITHUB_TOKEN or os.environ.get("GITHUB_TOKEN")
        self.is_mock = is_mock or os.environ.get("DEVORA_MOCK_GITHUB", "").lower() in ("true", "1", "yes")

        # In-memory token cache: {installation_id: (token, expire_timestamp)}
        self._token_cache: Dict[int, tuple[str, float]] = {}

    def _generate_app_jwt(self) -> str:
        """Create an RS256-signed JWT for GitHub App authentication (valid for 9 minutes)."""
        if not self.app_id or not self.private_key:
            raise BadRequestException("GitHub App ID or Private Key is not configured.")

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 1 minute clock skew allowance
            "exp": now + (9 * 60),  # 9 minutes expiration
            "iss": self.app_id,
        }

        # Format PEM key if needed
        key_content = self.private_key
        if os.path.exists(self.private_key):
            with open(self.private_key, "r", encoding="utf-8") as f:
                key_content = f.read()

        return jwt.encode(payload, key_content, algorithm="RS256")

    async def get_installation_access_token(self, installation_id: int) -> str:
        """Acquire a 1-hour installation access token, using cache if still valid."""
        # Check cache
        if installation_id in self._token_cache:
            token, expire_time = self._token_cache[installation_id]
            if time.time() < expire_time - 300:  # 5 minutes buffer
                return token

        # If mock mode enabled or in test environment without GitHub App keys
        if self.is_mock or not (self.app_id and self.private_key):
            if self.token_fallback:
                return self.token_fallback
            # Return synthetic test token for offline tests
            mock_token = f"ghs_mock_token_{installation_id}_{int(time.time())}"
            self._token_cache[installation_id] = (mock_token, time.time() + 3600)
            return mock_token

        app_jwt = self._generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code != 201:
                logger.error("failed_to_get_installation_token", status=resp.status_code, body=resp.text)
                raise BadRequestException(f"Failed to acquire GitHub installation token: {resp.text}")

            data = resp.json()
            token = data["token"]
            # Cache token for 55 minutes
            self._token_cache[installation_id] = (token, time.time() + 3300)
            return token

    async def list_installation_repositories(self, installation_id: int) -> List[Dict[str, Any]]:
        """List repositories accessible to a specific GitHub App installation."""
        if self.is_mock or not (self.app_id and self.private_key):
            return [
                {
                    "id": 1001,
                    "name": "devora-sample-repo",
                    "full_name": "devora-org/devora-sample-repo",
                    "private": False,
                    "clone_url": "https://github.com/devora-org/devora-sample-repo.git",
                    "default_branch": "main",
                    "language": "Python",
                    "permissions": {"admin": True, "push": True, "pull": True},
                },
                {
                    "id": 1002,
                    "name": "billing-service",
                    "full_name": "devora-org/billing-service",
                    "private": True,
                    "clone_url": "https://github.com/devora-org/billing-service.git",
                    "default_branch": "main",
                    "language": "Python",
                    "permissions": {"admin": False, "push": True, "pull": True},
                },
            ]

        token = await self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.github.com/installation/repositories", headers=headers)
            if resp.status_code != 200:
                raise BadRequestException(f"Failed to list installation repositories: {resp.text}")
            data = resp.json()
            repos = data.get("repositories", [])
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "private": r.get("private", False),
                    "clone_url": r.get("clone_url", ""),
                    "default_branch": r.get("default_branch", "main"),
                    "language": r.get("language"),
                    "permissions": r.get("permissions", {}),
                }
                for r in repos
            ]

    async def get_repository_details(self, owner: str, repo: str, token: str) -> Dict[str, Any]:
        """Fetch repository metadata and permissions from GitHub."""
        if self.is_mock or token.startswith("ghs_mock_"):
            return {
                "id": 9999,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "private": False,
                "default_branch": "main",
                "language": "Python",
                "clone_url": f"https://github.com/{owner}/{repo}.git",
                "permissions": {"push": True, "pull": True, "admin": False},
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if resp.status_code == 404:
                raise NotFoundException("GitHub Repository", f"{owner}/{repo}")
            if resp.status_code != 200:
                raise BadRequestException(f"Failed to fetch repository details: {resp.text}")
            return resp.json()

    async def list_branches(self, owner: str, repo: str, token: str) -> List[Dict[str, Any]]:
        """List branches for a remote GitHub repository."""
        if self.is_mock or token.startswith("ghs_mock_"):
            return [
                {"name": "main", "commit": {"sha": "4a2b1c3d4e5f6a7b8c9d0e1f"}},
                {"name": "develop", "commit": {"sha": "1f2e3d4c5b6a7f8e9d0c1b2a"}},
            ]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}/branches", headers=headers)
            if resp.status_code != 200:
                raise BadRequestException(f"Failed to fetch branches: {resp.text}")
            return resp.json()

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        token: str,
    ) -> Dict[str, Any]:
        """Create a new Pull Request on GitHub."""
        if self.is_mock or token.startswith("ghs_mock_"):
            mock_pr_num = int(time.time()) % 1000 + 1
            return {
                "id": 8888 + mock_pr_num,
                "number": mock_pr_num,
                "title": title,
                "body": body,
                "html_url": f"https://github.com/{owner}/{repo}/pull/{mock_pr_num}",
                "head": {"ref": head, "sha": "mock_head_sha_123"},
                "base": {"ref": base, "sha": "mock_base_sha_456"},
                "state": "open",
                "merged": False,
                "merge_commit_sha": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers=headers,
                json=payload,
            )
            if resp.status_code not in (200, 201):
                logger.error("failed_to_create_pull_request", status=resp.status_code, body=resp.text)
                raise BadRequestException(f"Failed to create GitHub Pull Request: {resp.text}")
            return resp.json()

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        token: str,
    ) -> Dict[str, Any]:
        """Retrieve Pull Request details and merge status from GitHub."""
        if self.is_mock or token.startswith("ghs_mock_"):
            return {
                "number": pull_number,
                "title": "[Devora] Automated Fix",
                "state": "open",
                "merged": False,
                "merge_commit_sha": None,
                "html_url": f"https://github.com/{owner}/{repo}/pull/{pull_number}",
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}",
                headers=headers,
            )
            if resp.status_code == 404:
                raise NotFoundException(f"Pull Request #{pull_number} on {owner}/{repo}", pull_number)
            if resp.status_code != 200:
                raise BadRequestException(f"Failed to fetch Pull Request: {resp.text}")
            return resp.json()
