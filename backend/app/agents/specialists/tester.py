"""Specialist Agent 6: Testing Agent.
Execution auditor running tests inside the isolated sandbox, parsing results, and enforcing evidence.
"""
import re
import time
from pathlib import Path
from typing import Any, Dict
from app.agents.state import DevoraWorkflowState, TestRunOutput
from app.core.logging import get_logger
from app.services.sandbox_service import SandboxService

logger = get_logger("testing_agent")


async def tester_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Testing Agent.
    Runs actual tests in isolated sandbox and records verified results.
    """
    start_time = time.time()
    sandbox = SandboxService()
    workspace_path = Path(state.get("workspace_path", "/tmp/devora/workspace"))

    # Determine test command: default to pytest
    test_command = "pytest"
    if (workspace_path / "tests").exists():
        test_command = "pytest -v tests"

    logger.info("tester_running_command", command=test_command, workspace=str(workspace_path))

    exec_res = sandbox.execute_command(
        workspace_path=workspace_path,
        command=test_command,
        timeout_seconds=60,
    )

    stdout = exec_res.stdout
    stderr = exec_res.stderr
    exit_code = exec_res.exit_code
    passed = (exit_code == 0)

    # Parse passed/failed counts from stdout
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    failure_details = []

    # Look for pytest patterns like "5 passed, 1 failed in 0.12s"
    pass_match = re.search(r"(\d+)\s+passed", stdout)
    fail_match = re.search(r"(\d+)\s+failed", stdout)

    if pass_match:
        passed_tests = int(pass_match.group(1))
    if fail_match:
        failed_tests = int(fail_match.group(1))

    total_tests = passed_tests + failed_tests
    if total_tests == 0 and passed:
        # If exit_code 0 with no specific count (e.g. basic script)
        total_tests = 1
        passed_tests = 1

    if not passed and stdout:
        # Extract failure lines
        for line in stdout.splitlines():
            if "FAILED" in line or "ERROR" in line or "AssertionError" in line:
                failure_details.append(line.strip())

    test_output = TestRunOutput(
        command=test_command,
        exit_code=exit_code,
        passed=passed,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        duration_seconds=exec_res.duration_seconds,
        raw_stdout=stdout,
        raw_stderr=stderr,
        failure_details=failure_details[:10],
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "tester",
        "action": "executed_tests",
        "passed": passed,
        "exit_code": exit_code,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info(
        "tester_completed",
        passed=passed,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        exit_code=exit_code,
    )

    return {
        "current_agent": "tester",
        "test_results": test_output.model_dump(),
        "last_test_stdout": stdout,
        "last_test_stderr": stderr,
        "last_test_exit_code": exit_code,
        "agent_execution_history": history,
    }
