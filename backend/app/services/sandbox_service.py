"""Isolated execution sandbox service for running tests, static analysis, and code patch application."""
import difflib
import os
import re
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.agents.state import FileEdit
from app.config import settings
from app.core.exceptions import BadRequestException, DevoraException
from app.core.logging import get_logger

logger = get_logger("sandbox_service")


class SandboxUnavailableException(DevoraException):
    """Raised when the secure sandbox execution environment is unavailable."""
    pass


@dataclass
class ExecutionResult:
    """Result of sandbox process execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


class SandboxRunner(ABC):
    """Abstract interface for sandbox command runners."""

    @abstractmethod
    def run_command(
        self,
        command: str,
        workspace_path: Path,
        timeout_seconds: int = 60,
    ) -> ExecutionResult:
        """Run command within isolated execution environment."""
        pass


class DockerSandboxRunner(SandboxRunner):
    """Production Docker-based isolated runner enforcing memory, CPU, PID limits, and network isolation."""

    def __init__(self, image_name: str = "python:3.11-slim-bookworm"):
        self.image_name = image_name

    def is_docker_available(self) -> bool:
        """Check if Docker CLI and daemon are operational."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def run_command(
        self,
        command: str,
        workspace_path: Path,
        timeout_seconds: int = 60,
    ) -> ExecutionResult:
        """Execute command in isolated Docker container."""
        if not self.is_docker_available():
            logger.error("docker_daemon_unavailable")
            raise SandboxUnavailableException(
                "Docker daemon is not accessible or not running. Untrusted code execution is disabled."
            )

        resolved_ws = workspace_path.resolve()
        resolved_str = str(resolved_ws)
        forbidden_roots = {
            "/", "/etc", "/private/etc", "/var", "/private/var", "/usr", "/Library",
            "/System", "/Users", str(Path.home()), "/tmp", "/private/tmp",
        }
        if resolved_str in forbidden_roots or resolved_ws == Path.home():
            raise BadRequestException(f"Mounting sensitive path '{workspace_path}' is strictly forbidden.")

        start_time = time.time()
        container_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "1500m",
            "--cpus", "2.0",
            "--pids-limit", "100",
            "--security-opt=no-new-privileges:true",
            "--cap-drop=ALL",
            "-v", f"{resolved_ws}:/workspace:rw",
            "-w", "/workspace",
            self.image_name,
            "/bin/sh", "-c", command,
        ]

        try:
            proc = subprocess.run(
                container_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration = time.time() - start_time
            return ExecutionResult(
                exit_code=proc.returncode,
                stdout=self._sanitize_output(proc.stdout),
                stderr=self._sanitize_output(proc.stderr),
                duration_seconds=round(duration, 3),
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {timeout_seconds} seconds.",
                duration_seconds=round(duration, 3),
                timed_out=True,
            )
        except Exception as exc:
            duration = time.time() - start_time
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=f"Sandbox execution error: {str(exc)}",
                duration_seconds=round(duration, 3),
                timed_out=False,
            )

    def _sanitize_output(self, text: str) -> str:
        """Strip sensitive credentials from command output."""
        if not text:
            return ""
        # Redact GitHub tokens and Gemini keys
        text = re.sub(r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]", text)
        text = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", text)
        return text


class LocalIsolatedRunner(SandboxRunner):
    """Isolated local runner for unit/integration testing with stripped environment and path confinement."""

    ALLOWED_PREFIXES = (
        "pytest",
        "python -m unittest",
        "python -m pytest",
        "python",
        "ruff",
        "mypy",
        "echo",
    )

    def run_command(
        self,
        command: str,
        workspace_path: Path,
        timeout_seconds: int = 30,
    ) -> ExecutionResult:
        """Run command with stripped environment variables and confined working directory."""
        clean_cmd = command.strip()
        if not any(clean_cmd.startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
            raise BadRequestException(f"Command '{command}' is not in the allowed sandbox execution whitelist.")

        # Prevent shell chaining / command injection attacks
        forbidden_tokens = ["&&", "||", "|", "`", "$(", "${", "\n"]
        for token in forbidden_tokens:
            if token in clean_cmd:
                raise BadRequestException(f"Command injection detected: forbidden operator '{token}'.")

        # Semicolon chaining is forbidden (unless inside a python -c argument)
        if ";" in clean_cmd and not clean_cmd.startswith("python"):
            raise BadRequestException("Command injection detected: forbidden operator ';'.")

        # Sanitize environment: strip backend secrets and prepend current python bin directory
        py_bin_dir = str(Path(sys.executable).parent)
        safe_env = {
            "PATH": f"{py_bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": str(workspace_path),
            "LANG": "en_US.UTF-8",
            "PYTHONPATH": str(workspace_path),
        }

        start_time = time.time()
        try:
            proc = subprocess.run(
                clean_cmd,
                shell=True,
                cwd=str(workspace_path),
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration = time.time() - start_time
            return ExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_seconds=round(duration, 3),
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Process timed out after {timeout_seconds} seconds.",
                duration_seconds=round(duration, 3),
                timed_out=True,
            )
        except Exception as exc:
            duration = time.time() - start_time
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=f"Process error: {str(exc)}",
                duration_seconds=round(duration, 3),
                timed_out=False,
            )


class SandboxService:
    """Manages ephemeral task workspaces, safe code modifications, and sandboxed test runs."""

    def __init__(
        self,
        runner: Optional[SandboxRunner] = None,
        base_tasks_dir: Optional[Path] = None,
    ):
        self.base_tasks_dir = base_tasks_dir or Path(os.environ.get("DEVORA_TASKS_DIR", "/tmp/devora/tasks"))
        self.base_tasks_dir.mkdir(parents=True, exist_ok=True)

        # Select runner
        forced_runner = os.environ.get("DEVORA_SANDBOX_RUNNER", "").lower()
        if runner:
            self.runner = runner
        elif forced_runner in ("local", "isolated_process", "mock", "test", "local_test"):
            self.runner = LocalIsolatedRunner()
        else:
            # Default to production DockerSandboxRunner. Never fall back to uncontained subprocess execution.
            self.runner = DockerSandboxRunner()

    def prepare_workspace(self, task_id: str, repo_workspace_path: Path) -> Path:
        """Create an isolated workspace for the task by copying the repository snapshot."""
        task_workspace = (self.base_tasks_dir / task_id / "workspace").resolve()
        if task_workspace.exists():
            shutil.rmtree(task_workspace)
        task_workspace.mkdir(parents=True, exist_ok=True)

        if repo_workspace_path.exists() and repo_workspace_path.is_dir():
            shutil.copytree(repo_workspace_path, task_workspace, dirs_exist_ok=True)

        return task_workspace

    def apply_edits(self, workspace_path: Path, edits: List[FileEdit]) -> Dict[str, Any]:
        """Safely apply structured file modifications to the task workspace.
        Enforces path containment and generates a unified git diff.
        """
        modified_records: List[Dict[str, Any]] = []
        all_diffs: List[str] = []

        for edit in edits:
            rel_path = edit.file_path.strip().lstrip("/")
            target_file = (workspace_path / rel_path).resolve()

            # Prevent directory traversal attacks
            if not str(target_file).startswith(str(workspace_path.resolve())):
                raise BadRequestException(f"Path traversal blocked for file '{edit.file_path}'.")

            original_content = ""
            if target_file.exists() and target_file.is_file():
                original_content = target_file.read_text(encoding="utf-8", errors="replace")

            # Apply modification or replacement
            if edit.original_snippet and edit.original_snippet in original_content:
                new_content = original_content.replace(edit.original_snippet, edit.new_snippet, 1)
            elif edit.change_type == "added" or not target_file.exists():
                new_content = edit.new_snippet
            else:
                # Fallback: append or replace whole content if small
                new_content = edit.new_snippet

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(new_content, encoding="utf-8")

            # Generate unified diff
            orig_lines = original_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            file_diff = "".join(
                difflib.unified_diff(
                    orig_lines,
                    new_lines,
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
            )
            all_diffs.append(file_diff)

            modified_records.append({
                "file_path": rel_path,
                "change_type": edit.change_type,
                "original_content": original_content,
                "new_content": new_content,
                "diff": file_diff,
                "explanation": edit.explanation,
            })

        unified_diff_str = "\n".join(all_diffs)
        return {
            "modified_files": modified_records,
            "git_diff": unified_diff_str,
        }

    def execute_command(
        self,
        workspace_path: Path,
        command: str,
        timeout_seconds: int = 60,
    ) -> ExecutionResult:
        """Run command within the configured sandbox runner."""
        return self.runner.run_command(
            command=command,
            workspace_path=workspace_path,
            timeout_seconds=timeout_seconds,
        )
