"""Isolated execution sandbox service for running tests, static analysis, and code patch application."""
import difflib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import time
import uuid
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


def parse_memory_to_bytes(mem_str: Optional[str]) -> Optional[int]:
    """Parse memory string like '1500m', '1g', '512k' to bytes."""
    if not mem_str:
        return None
    mem_str = str(mem_str).strip().lower()
    match = re.match(r"^(\d+)([kmg]?)$", mem_str)
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    multipliers = {"": 1, "k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}
    return val * multipliers.get(unit, 1)


def sanitize_output(text: str) -> str:
    """Strip sensitive credentials from command output."""
    if not text:
        return ""
    text = re.sub(r"ghp_[a-zA-Z0-9]{36,40}", "[REDACTED_GITHUB_TOKEN]", text)
    text = re.sub(r"AIza[0-9A-Za-z-_]{30,45}", "[REDACTED_API_KEY]", text)
    return text


class SandboxExitClassifier:
    """Centralized classifier for sandbox container and process exit conditions."""

    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    COMMAND_NOT_EXECUTABLE = "COMMAND_NOT_EXECUTABLE"
    COMMAND_NOT_FOUND = "COMMAND_NOT_FOUND"
    OOM_KILLED = "OOM_KILLED"
    PROCESS_KILLED = "PROCESS_KILLED"
    SANDBOX_STARTUP_FAILURE = "SANDBOX_STARTUP_FAILURE"
    RUNNER_UNAVAILABLE = "RUNNER_UNAVAILABLE"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"

    @classmethod
    def classify(
        cls,
        exit_code: int,
        timed_out: bool = False,
        oom_killed: bool = False,
        is_daemon_unavailable: bool = False,
        is_startup_failure: bool = False,
    ) -> str:
        """Classify sandbox execution status based on deterministic exit evidence.

        Exit code 137 is only classified as OOM_KILLED when oom_killed
        is independently verified through container/cgroup telemetry; otherwise
        it is classified as PROCESS_KILLED.
        """
        if is_daemon_unavailable:
            return cls.RUNNER_UNAVAILABLE

        if is_startup_failure:
            return cls.SANDBOX_STARTUP_FAILURE

        if timed_out or exit_code in (124, -1):
            return cls.TIMEOUT

        if exit_code == 0:
            return cls.SUCCESS

        if exit_code == 126:
            return cls.COMMAND_NOT_EXECUTABLE

        if exit_code == 127:
            return cls.COMMAND_NOT_FOUND

        if exit_code in (137, -9):
            if oom_killed:
                return cls.OOM_KILLED
            return cls.PROCESS_KILLED

        return cls.EXECUTION_FAILURE

    @classmethod
    def is_environment_or_resource_failure(cls, classification: str) -> bool:
        """Return True if classification represents an environmental or resource constraint
        that must not trigger automated LLM code rewrites or lower flaky stability scores.
        """
        return classification in {
            cls.TIMEOUT,
            cls.COMMAND_NOT_EXECUTABLE,
            cls.COMMAND_NOT_FOUND,
            cls.OOM_KILLED,
            cls.PROCESS_KILLED,
            cls.SANDBOX_STARTUP_FAILURE,
            cls.RUNNER_UNAVAILABLE,
            "RESOURCE_EXHAUSTED",
            "EXECUTION_TIMEOUT",
        }


@dataclass
class ExecutionResult:
    """Result of sandbox process execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    # Extended Resource Telemetry (Phase 9 Stage 9.3)
    peak_memory_rss_bytes: Optional[int] = None
    peak_memory_rss_mb: Optional[float] = None
    cpu_time_seconds: Optional[float] = None
    wall_time_seconds: Optional[float] = None
    memory_limit_bytes: Optional[int] = None
    memory_limit_mb: Optional[float] = None
    cpu_limit: Optional[float] = None
    oom_killed: bool = False
    termination_reason: Optional[str] = None
    exit_classification: str = "EXECUTION_FAILURE"
    resource_telemetry_available: bool = False


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
        """Execute command in isolated Docker container with resource accounting and cleanup."""
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

        container_name = f"devora-sandbox-{uuid.uuid4().hex[:12]}"

        # Parse memory limit
        mem_limit_str = settings.SANDBOX_CONTAINER_MEMORY_LIMIT
        mem_limit_bytes = parse_memory_to_bytes(mem_limit_str)
        mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 2) if mem_limit_bytes else 1500.0

        try:
            cpu_limit = float(settings.SANDBOX_CONTAINER_CPU_LIMIT)
        except (ValueError, TypeError):
            cpu_limit = 2.0

        container_cmd = [
            "docker", "run",
            "--name", container_name,
            "--network", "none",
            "--memory", mem_limit_str,
            "--cpus", str(cpu_limit),
            "--pids-limit", str(settings.SANDBOX_CONTAINER_PIDS_LIMIT),
            "--security-opt=no-new-privileges:true",
            "--cap-drop=ALL",
            "-v", f"{resolved_ws}:/workspace:rw",
            "-w", "/workspace",
            self.image_name,
            "/bin/sh", "-c", command,
        ]

        start_time = time.perf_counter()
        timed_out = False
        oom_killed = False
        raw_stdout = ""
        raw_stderr = ""
        exit_code = 1
        peak_memory_rss_bytes = None
        peak_memory_rss_mb = None
        cpu_time_seconds = None
        telemetry_available = False
        termination_reason = None
        startup_failure = False

        try:
            try:
                proc = subprocess.run(
                    container_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                wall_duration = time.perf_counter() - start_time
                exit_code = proc.returncode
                raw_stdout = proc.stdout
                raw_stderr = proc.stderr
            except subprocess.TimeoutExpired:
                wall_duration = time.perf_counter() - start_time
                timed_out = True
                exit_code = 124
                raw_stderr = f"Execution timed out after {timeout_seconds} seconds."
                termination_reason = f"Execution timed out after {timeout_seconds} seconds"

            # Query Docker inspect before container cleanup
            try:
                insp = subprocess.run(
                    ["docker", "inspect", container_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if insp.returncode == 0:
                    inspect_data = json.loads(insp.stdout)
                    if inspect_data and isinstance(inspect_data, list):
                        c_info = inspect_data[0]
                        c_state = c_info.get("State", {})
                        oom_killed = bool(c_state.get("OOMKilled", False))
                        if oom_killed:
                            termination_reason = "Container exceeded memory limit (OOMKilled by Linux kernel)"
                        elif c_state.get("Status") == "dead" or (c_state.get("Error") and exit_code != 0 and not timed_out):
                            startup_failure = True
                            termination_reason = f"Container failure: {c_state.get('Error')}"

                        h_cfg = c_info.get("HostConfig", {})
                        if h_cfg.get("Memory"):
                            mem_limit_bytes = int(h_cfg.get("Memory"))
                            mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 2)
                        if h_cfg.get("NanoCpus"):
                            cpu_limit = round(float(h_cfg.get("NanoCpus")) / 1e9, 2)

                        telemetry_available = True
            except Exception as e:
                logger.debug("docker_inspect_telemetry_failed", error=str(e))

        except Exception as exc:
            wall_duration = time.perf_counter() - start_time
            startup_failure = True
            exit_code = 1
            raw_stderr = f"Sandbox execution error: {str(exc)}"
            termination_reason = f"Sandbox error: {str(exc)}"
        finally:
            # Deterministic container cleanup: guarantees zero orphaned containers
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except Exception:
                pass

        exit_class = SandboxExitClassifier.classify(
            exit_code=exit_code,
            timed_out=timed_out,
            oom_killed=oom_killed,
            is_startup_failure=startup_failure,
        )

        return ExecutionResult(
            exit_code=exit_code,
            stdout=sanitize_output(raw_stdout),
            stderr=sanitize_output(raw_stderr),
            duration_seconds=round(wall_duration, 3),
            timed_out=timed_out,
            peak_memory_rss_bytes=peak_memory_rss_bytes,
            peak_memory_rss_mb=peak_memory_rss_mb,
            cpu_time_seconds=cpu_time_seconds,
            wall_time_seconds=round(wall_duration, 3),
            memory_limit_bytes=mem_limit_bytes,
            memory_limit_mb=mem_limit_mb,
            cpu_limit=cpu_limit,
            oom_killed=oom_killed,
            termination_reason=termination_reason,
            exit_classification=exit_class,
            resource_telemetry_available=telemetry_available,
        )

    def _sanitize_output(self, text: str) -> str:
        """Strip sensitive credentials from command output."""
        return sanitize_output(text)


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
        "npm test",
        "npm run",
        "npm",
        "npx jest",
        "npx vitest",
        "npx",
        "yarn test",
        "yarn",
        "pnpm test",
        "pnpm",
        "go test",
        "go",
        "cargo test",
        "cargo",
        "mvn test",
        "mvn",
    )

    def run_command(
        self,
        command: str,
        workspace_path: Path,
        timeout_seconds: int = 30,
    ) -> ExecutionResult:
        """Run command with stripped environment variables, confined working directory, and resource tracking."""
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

        start_time = time.perf_counter()
        usage_start = resource.getrusage(resource.RUSAGE_CHILDREN)
        timed_out = False
        exit_code = 1
        raw_stdout = ""
        raw_stderr = ""
        termination_reason = None

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
            wall_duration = time.perf_counter() - start_time
            exit_code = proc.returncode
            raw_stdout = proc.stdout
            raw_stderr = proc.stderr
        except subprocess.TimeoutExpired:
            wall_duration = time.perf_counter() - start_time
            timed_out = True
            exit_code = 124
            raw_stderr = f"Process timed out after {timeout_seconds} seconds."
            termination_reason = f"Process timed out after {timeout_seconds} seconds"
        except Exception as exc:
            wall_duration = time.perf_counter() - start_time
            exit_code = 1
            raw_stderr = f"Process error: {str(exc)}"
            termination_reason = f"Process error: {str(exc)}"

        usage_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_time = round(
            max(0.0, (usage_end.ru_utime + usage_end.ru_stime) - (usage_start.ru_utime + usage_start.ru_stime)),
            3,
        )

        is_darwin = sys.platform == "darwin"
        raw_rss = usage_end.ru_maxrss
        peak_bytes = raw_rss if is_darwin else (raw_rss * 1024)
        peak_mb = round(peak_bytes / (1024 * 1024), 2) if peak_bytes > 0 else None

        oom_killed = False
        if exit_code in (137, -9) and not termination_reason:
            termination_reason = "Process killed by external signal (SIGKILL)"

        exit_class = SandboxExitClassifier.classify(
            exit_code=exit_code,
            timed_out=timed_out,
            oom_killed=oom_killed,
        )

        telemetry_available = (peak_mb is not None and peak_mb > 0)

        return ExecutionResult(
            exit_code=exit_code,
            stdout=sanitize_output(raw_stdout),
            stderr=sanitize_output(raw_stderr),
            duration_seconds=round(wall_duration, 3),
            timed_out=timed_out,
            peak_memory_rss_bytes=peak_bytes if peak_bytes > 0 else None,
            peak_memory_rss_mb=peak_mb,
            cpu_time_seconds=cpu_time,
            wall_time_seconds=round(wall_duration, 3),
            memory_limit_bytes=None,
            memory_limit_mb=None,
            cpu_limit=None,
            oom_killed=oom_killed,
            termination_reason=termination_reason,
            exit_classification=exit_class,
            resource_telemetry_available=telemetry_available,
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
