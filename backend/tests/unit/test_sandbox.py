"""Unit tests for SandboxService: path containment, diff generation, and process execution."""
import tempfile
from pathlib import Path
import pytest

from app.agents.state import FileEdit
from app.core.exceptions import BadRequestException
from app.services.sandbox_service import LocalIsolatedRunner, SandboxService


def test_sandbox_path_traversal_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        service = SandboxService(runner=LocalIsolatedRunner())

        malicious_edit = FileEdit(
            file_path="../../etc/passwd",
            original_snippet="",
            new_snippet="malicious",
            explanation="exploit",
        )

        with pytest.raises(BadRequestException) as exc_info:
            service.apply_edits(ws, [malicious_edit])
        assert "Path traversal blocked" in str(exc_info.value)


def test_sandbox_apply_edits_and_diff():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "main.py").write_text("def hello():\n    return 'old'\n")

        service = SandboxService(runner=LocalIsolatedRunner())

        edit = FileEdit(
            file_path="main.py",
            original_snippet="    return 'old'",
            new_snippet="    return 'new'",
            explanation="update return value",
        )

        res = service.apply_edits(ws, [edit])
        assert len(res["modified_files"]) == 1
        assert "main.py" in res["git_diff"]
        assert "-    return 'old'" in res["git_diff"]
        assert "+    return 'new'" in res["git_diff"]

        content = (ws / "main.py").read_text()
        assert "return 'new'" in content


def test_sandbox_runner_disallows_unsafe_commands():
    runner = LocalIsolatedRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        with pytest.raises(BadRequestException):
            runner.run_command("curl http://evil.com", ws)
        with pytest.raises(BadRequestException):
            runner.run_command("rm -rf /", ws)


def test_sandbox_runner_executes_allowed_command():
    runner = LocalIsolatedRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        res = runner.run_command("python -c 'print(\"sandbox-ok\")'", ws)
        assert res.exit_code == 0
        assert "sandbox-ok" in res.stdout
