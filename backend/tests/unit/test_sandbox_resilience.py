"""Unit tests for Phase 9 Stage 9.3: Sandbox Resilience, OOM Classification & Resource Telemetry."""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.config import settings
from app.services.sandbox_service import (
    DockerSandboxRunner,
    ExecutionResult,
    LocalIsolatedRunner,
    SandboxExitClassifier,
    SandboxUnavailableException,
    parse_memory_to_bytes,
    sanitize_output,
)
from app.services.test_discovery_service import TestTimeoutScaler, TestExecutionPlan


# ===========================================================================
# 1. Container Exit Code Classification Tests
# ===========================================================================

def test_exit_classification_success():
    """Exit code 0 must classify as SUCCESS."""
    assert SandboxExitClassifier.classify(exit_code=0) == "SUCCESS"


def test_exit_classification_timeout():
    """Exit code 124, -1, or timed_out=True must classify as TIMEOUT."""
    assert SandboxExitClassifier.classify(exit_code=124) == "TIMEOUT"
    assert SandboxExitClassifier.classify(exit_code=-1) == "TIMEOUT"
    assert SandboxExitClassifier.classify(exit_code=1, timed_out=True) == "TIMEOUT"


def test_exit_classification_command_not_executable():
    """Exit code 126 must classify as COMMAND_NOT_EXECUTABLE."""
    assert SandboxExitClassifier.classify(exit_code=126) == "COMMAND_NOT_EXECUTABLE"


def test_exit_classification_command_not_found():
    """Exit code 127 must classify as COMMAND_NOT_FOUND."""
    assert SandboxExitClassifier.classify(exit_code=127) == "COMMAND_NOT_FOUND"


def test_exit_classification_oom_killed_only_when_confirmed():
    """Exit code 137 must classify as OOM_KILLED only with independent confirmation."""
    # When OOM is confirmed by kernel/container telemetry
    assert SandboxExitClassifier.classify(exit_code=137, oom_killed=True) == "OOM_KILLED"
    assert SandboxExitClassifier.classify(exit_code=-9, oom_killed=True) == "OOM_KILLED"

    # Crucial rule: When OOM is NOT confirmed, classify safely as PROCESS_KILLED
    assert SandboxExitClassifier.classify(exit_code=137, oom_killed=False) == "PROCESS_KILLED"
    assert SandboxExitClassifier.classify(exit_code=-9, oom_killed=False) == "PROCESS_KILLED"


def test_exit_classification_general_failure():
    """Other non-zero exit codes classify as EXECUTION_FAILURE."""
    assert SandboxExitClassifier.classify(exit_code=1) == "EXECUTION_FAILURE"
    assert SandboxExitClassifier.classify(exit_code=2) == "EXECUTION_FAILURE"


def test_exit_classification_infrastructure_states():
    """Daemon unavailable and startup failures must be distinct."""
    assert SandboxExitClassifier.classify(exit_code=1, is_daemon_unavailable=True) == "RUNNER_UNAVAILABLE"
    assert SandboxExitClassifier.classify(exit_code=1, is_startup_failure=True) == "SANDBOX_STARTUP_FAILURE"


def test_is_environment_or_resource_failure():
    """Verify classification helper accurately identifies resource/environment constraints."""
    assert SandboxExitClassifier.is_environment_or_resource_failure("OOM_KILLED") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("PROCESS_KILLED") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("TIMEOUT") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("COMMAND_NOT_FOUND") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("COMMAND_NOT_EXECUTABLE") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("RUNNER_UNAVAILABLE") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("SANDBOX_STARTUP_FAILURE") is True
    assert SandboxExitClassifier.is_environment_or_resource_failure("EXECUTION_FAILURE") is False
    assert SandboxExitClassifier.is_environment_or_resource_failure("SUCCESS") is False


# ===========================================================================
# 2. Resource Telemetry & Parsing Tests
# ===========================================================================

def test_parse_memory_to_bytes():
    """Verify memory string parsing across megabytes, gigabytes, and kilobytes."""
    assert parse_memory_to_bytes("1500m") == 1500 * 1024 * 1024
    assert parse_memory_to_bytes("1g") == 1024 * 1024 * 1024
    assert parse_memory_to_bytes("512k") == 512 * 1024
    assert parse_memory_to_bytes("1024") == 1024
    assert parse_memory_to_bytes(None) is None
    assert parse_memory_to_bytes("invalid") is None


def test_sanitize_output_strips_secrets():
    """Sensitive GitHub tokens and API keys must be redacted in output."""
    raw = "Failed with ghp_1234567890abcdefghijklmnopqrstuvwxyz and AIzaSyD1234567890abcdefghijklmnopqr"
    sanitized = sanitize_output(raw)
    assert "ghp_" not in sanitized
    assert "[REDACTED_GITHUB_TOKEN]" in sanitized
    assert "AIza" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized


def test_execution_result_defaults_and_telemetry():
    """Verify ExecutionResult retains telemetry fields without fabricating zero values."""
    res = ExecutionResult(
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_seconds=1.23,
        peak_memory_rss_bytes=104857600,
        peak_memory_rss_mb=100.0,
        cpu_time_seconds=0.45,
        wall_time_seconds=1.23,
        memory_limit_bytes=1572864000,
        memory_limit_mb=1500.0,
        cpu_limit=2.0,
        oom_killed=False,
        exit_classification="SUCCESS",
        resource_telemetry_available=True,
    )
    assert res.peak_memory_rss_mb == 100.0
    assert res.resource_telemetry_available is True
    assert res.oom_killed is False


def test_missing_telemetry_is_not_fabricated():
    """When telemetry is unavailable, fields must be None rather than misleading 0.0 values."""
    res = ExecutionResult(
        exit_code=1,
        stdout="",
        stderr="error",
        duration_seconds=0.5,
        resource_telemetry_available=False,
    )
    assert res.peak_memory_rss_bytes is None
    assert res.peak_memory_rss_mb is None
    assert res.cpu_time_seconds is None
    assert res.resource_telemetry_available is False


# ===========================================================================
# 3. Dynamic Test Timeout Scaling Tests
# ===========================================================================

def test_timeout_scaler_below_threshold():
    """Suites <= 50 tests must retain the base timeout."""
    timeout, reason = TestTimeoutScaler.calculate_timeout(total_tests=30, base_timeout=60)
    assert timeout == 60
    assert "Standard suite" in reason


def test_timeout_scaler_exactly_at_threshold():
    """Suites with exactly 50 tests must retain base timeout."""
    timeout, reason = TestTimeoutScaler.calculate_timeout(total_tests=50, base_timeout=60)
    assert timeout == 60


def test_timeout_scaler_above_threshold():
    """Suites > 50 tests must apply multiplier (default 1.5x)."""
    timeout, reason = TestTimeoutScaler.calculate_timeout(total_tests=75, base_timeout=60)
    assert timeout == 90  # 60 * 1.5 = 90
    assert "Large suite detected" in reason


def test_timeout_scaler_ceiling_enforcement():
    """Timeout scaling must never exceed the strict ceiling (default 300s)."""
    timeout, reason = TestTimeoutScaler.calculate_timeout(total_tests=500, base_timeout=250)
    assert timeout == 300  # 250 * 1.5 = 375, capped at 300
    assert timeout <= settings.TEST_MAX_TIMEOUT_SECONDS


# ===========================================================================
# 4. Local Isolated Runner Execution & Telemetry Tests
# ===========================================================================

def test_local_runner_captures_wall_and_cpu_time(tmp_path: Path):
    """LocalIsolatedRunner should execute allowed command and capture duration and telemetry."""
    runner = LocalIsolatedRunner()
    res = runner.run_command(command="python -c 'print(\"hello\")'", workspace_path=tmp_path)
    assert res.exit_code == 0
    assert "hello" in res.stdout
    assert res.duration_seconds >= 0.0
    assert res.exit_classification == "SUCCESS"
    assert res.wall_time_seconds is not None


def test_local_runner_timeout_handling(tmp_path: Path):
    """Local runner must handle process timeouts cleanly without leaking."""
    runner = LocalIsolatedRunner()
    res = runner.run_command(command="python -c 'import time; time.sleep(10)'", workspace_path=tmp_path, timeout_seconds=1)
    assert res.timed_out is True
    assert res.exit_code in (124, -1)
    assert res.exit_classification == "TIMEOUT"
    assert "timed out" in res.stderr.lower()


# ===========================================================================
# 5. Docker Runner Lifecycle & Container Cleanup Verification
# ===========================================================================

def test_docker_runner_cleans_up_container_after_execution(tmp_path: Path):
    """DockerSandboxRunner must unconditionally execute docker rm -f in finally block."""
    runner = DockerSandboxRunner()

    with patch.object(runner, "is_docker_available", return_value=True):
        with patch("subprocess.run") as mock_subproc:
            # Mock container run succeeding
            mock_subproc.side_effect = [
                # 1. docker run
                MagicMock(returncode=0, stdout="test pass", stderr=""),
                # 2. docker inspect
                MagicMock(returncode=0, stdout='[{"State": {"OOMKilled": false, "ExitCode": 0}, "HostConfig": {"Memory": 1572864000, "NanoCpus": 2000000000}}]'),
                # 3. docker rm -f in finally
                MagicMock(returncode=0, stdout="", stderr=""),
            ]

            res = runner.run_command(command="pytest", workspace_path=tmp_path)
            assert res.exit_code == 0
            assert res.exit_classification == "SUCCESS"
            assert res.oom_killed is False
            assert res.memory_limit_mb == 1500.0
            assert res.cpu_limit == 2.0

            # Verify docker rm -f was called in the finally block
            rm_calls = [c for c in mock_subproc.call_args_list if c[0][0][0:3] == ["docker", "rm", "-f"]]
            assert len(rm_calls) == 1


def test_docker_runner_detects_oom_killed(tmp_path: Path):
    """DockerSandboxRunner must detect OOMKilled=True and classify as OOM_KILLED."""
    runner = DockerSandboxRunner()

    with patch.object(runner, "is_docker_available", return_value=True):
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.side_effect = [
                # 1. docker run killed by OOM (exit 137)
                MagicMock(returncode=137, stdout="", stderr="Killed"),
                # 2. docker inspect confirms OOMKilled=true
                MagicMock(returncode=0, stdout='[{"State": {"OOMKilled": true, "ExitCode": 137}, "HostConfig": {"Memory": 1572864000, "NanoCpus": 2000000000}}]'),
                # 3. docker rm -f in finally
                MagicMock(returncode=0, stdout="", stderr=""),
            ]

            res = runner.run_command(command="pytest", workspace_path=tmp_path)
            assert res.exit_code == 137
            assert res.oom_killed is True
            assert res.exit_classification == "OOM_KILLED"
            assert "OOMKilled" in (res.termination_reason or "")


def test_docker_runner_exit_137_without_oom_evidence_is_process_killed(tmp_path: Path):
    """Exit 137 without Docker OOMKilled evidence must be classified as PROCESS_KILLED."""
    runner = DockerSandboxRunner()

    with patch.object(runner, "is_docker_available", return_value=True):
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.side_effect = [
                # 1. docker run received SIGKILL (exit 137)
                MagicMock(returncode=137, stdout="", stderr="Terminated"),
                # 2. docker inspect confirms OOMKilled was false
                MagicMock(returncode=0, stdout='[{"State": {"OOMKilled": false, "ExitCode": 137}, "HostConfig": {"Memory": 1572864000}}]'),
                # 3. docker rm -f in finally
                MagicMock(returncode=0, stdout="", stderr=""),
            ]

            res = runner.run_command(command="pytest", workspace_path=tmp_path)
            assert res.exit_code == 137
            assert res.oom_killed is False
            assert res.exit_classification == "PROCESS_KILLED"
