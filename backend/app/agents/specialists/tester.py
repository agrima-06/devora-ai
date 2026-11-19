"""Specialist Agent 6: Testing Agent.
Language-aware execution auditor discovering test frameworks, selecting targeted tests,
executing inside the isolated sandbox, parsing results, and enforcing execution evidence.
"""
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List
from app.agents.state import DevoraWorkflowState, TestRunOutput
from app.core.logging import get_logger
from app.services.flaky_detector import FlakyTestDetector
from app.services.sandbox_service import SandboxService
from app.services.test_discovery_service import TestDiscoveryService

logger = get_logger("testing_agent")


async def tester_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Testing Agent.
    Discovers repository languages and test frameworks, plans targeted or full test suites,
    runs execution inside isolated sandbox, and normalizes verified results.
    """
    start_time = time.time()
    sandbox = SandboxService()
    workspace_path = Path(state.get("workspace_path", "/tmp/devora/workspace"))

    # 1. Discover repository test suites and frameworks
    discovery = TestDiscoveryService(workspace_path=workspace_path)
    suite = discovery.discover_suite(workspace_path)

    # 2. Extract modified files for targeted test selection
    applied_changes = state.get("applied_file_changes", []) or []
    modified_files: List[str] = [
        f.get("file_path", "")
        for f in applied_changes
        if isinstance(f, dict) and f.get("file_path")
    ]
    if not modified_files:
        proposed_changes = state.get("proposed_file_changes", []) or []
        modified_files = [
            f.get("file_path", "")
            for f in proposed_changes
            if isinstance(f, dict) and f.get("file_path")
        ]

    # 3. Plan test execution (targeted vs fallback full suite)
    plan = discovery.select_tests_for_changes(
        suite=suite,
        repo_dir=workspace_path,
        modified_files=modified_files,
    )

    logger.info(
        "tester_executing_plan",
        command=plan.command,
        framework=plan.framework,
        is_targeted=plan.is_targeted,
        selected_files=plan.selected_files,
        workspace=str(workspace_path),
    )

    # 4. Execute test command in isolated sandbox
    exec_res = sandbox.execute_command(
        workspace_path=workspace_path,
        command=plan.command,
        timeout_seconds=plan.timeout_seconds,
    )

    # 5. Normalize output across all supported frameworks
    norm = discovery.parse_test_output(
        framework=plan.framework,
        stdout=exec_res.stdout,
        stderr=exec_res.stderr,
        exit_code=exec_res.exit_code,
        duration_seconds=exec_res.duration_seconds,
        command=plan.command,
        is_targeted=plan.is_targeted,
        selected_files=plan.selected_files,
        oom_killed=exec_res.oom_killed,
        termination_reason=exec_res.termination_reason,
        exit_classification=exec_res.exit_classification,
        peak_memory_rss_bytes=exec_res.peak_memory_rss_bytes,
        peak_memory_rss_mb=exec_res.peak_memory_rss_mb,
        cpu_time_seconds=exec_res.cpu_time_seconds,
        wall_time_seconds=exec_res.wall_time_seconds,
        memory_limit_bytes=exec_res.memory_limit_bytes,
        memory_limit_mb=exec_res.memory_limit_mb,
        cpu_limit=exec_res.cpu_limit,
        resource_telemetry_available=exec_res.resource_telemetry_available,
    )

    # 6. Flaky Test Detection (Phase 9 Stage 9.2)
    flaky_detector = FlakyTestDetector(sandbox=sandbox, discovery=discovery)
    flaky_report = None
    if not norm.passed:
        eligible, _ = flaky_detector.is_eligible_for_flaky_detection(norm)
        if eligible:
            logger.info("tester_initiating_flaky_detection", command=plan.command)
            flaky_report = flaky_detector.detect_flakiness(
                workspace_path=workspace_path,
                test_command=plan.command,
                framework=plan.framework,
                initial_failed_result=norm,
                timeout_seconds=plan.timeout_seconds,
            )

    # 7. Construct strongly typed TestRunOutput contract
    test_output = TestRunOutput(
        command=norm.command,
        exit_code=norm.exit_code,
        passed=norm.passed,
        total_tests=norm.total_tests,
        passed_tests=norm.passed_tests,
        failed_tests=norm.failed_tests,
        skipped_tests=norm.skipped_tests,
        duration_seconds=norm.duration_seconds,
        raw_stdout=norm.raw_stdout,
        raw_stderr=norm.raw_stderr,
        failure_details=norm.failure_details,
        detected_languages=suite.detected_languages,
        detected_frameworks=suite.detected_frameworks,
        package_manager=suite.package_manager,
        discovery_status=suite.discovery_status,
        execution_status=norm.execution_status,
        selected_test_files=norm.selected_test_files,
        is_targeted=norm.is_targeted,
        failure_classification=norm.failure_classification,
        diagnostic_warning=norm.diagnostic_warning,
        stability_classification=flaky_report.classification if flaky_report else ("STABLE_PASS" if norm.passed else None),
        stability_score=flaky_report.stability_score if flaky_report else (100.0 if norm.passed else None),
        is_flaky=flaky_report.is_flaky if flaky_report else False,
        flaky_repeat_runs=flaky_report.execution_history if flaky_report else [],
        peak_memory_rss_bytes=norm.peak_memory_rss_bytes,
        peak_memory_rss_mb=norm.peak_memory_rss_mb,
        cpu_time_seconds=norm.cpu_time_seconds,
        wall_time_seconds=norm.wall_time_seconds,
        memory_limit_bytes=norm.memory_limit_bytes,
        memory_limit_mb=norm.memory_limit_mb,
        cpu_limit=norm.cpu_limit,
        oom_killed=norm.oom_killed,
        termination_reason=norm.termination_reason,
        exit_classification=norm.exit_classification,
        resource_telemetry_available=norm.resource_telemetry_available,
        timeout_seconds=plan.timeout_seconds,
        timeout_scaling_reason=plan.timeout_scaling_reason,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "tester",
        "action": "executed_tests",
        "passed": norm.passed,
        "exit_code": norm.exit_code,
        "total_tests": norm.total_tests,
        "passed_tests": norm.passed_tests,
        "failed_tests": norm.failed_tests,
        "framework": plan.framework,
        "is_targeted": plan.is_targeted,
        "languages": suite.detected_languages,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info(
        "tester_completed",
        framework=plan.framework,
        passed=norm.passed,
        passed_tests=norm.passed_tests,
        failed_tests=norm.failed_tests,
        exit_code=norm.exit_code,
        execution_status=norm.execution_status,
    )

    return {
        "current_agent": "tester",
        "test_results": test_output.model_dump(),
        "flaky_test_report": asdict(flaky_report) if flaky_report else None,
        "test_discovery_info": {
            "languages": suite.detected_languages,
            "frameworks": suite.detected_frameworks,
            "primary_language": suite.primary_language,
            "primary_framework": suite.primary_framework,
            "package_manager": suite.package_manager,
            "is_targeted": plan.is_targeted,
            "selected_files": plan.selected_files,
            "selection_reason": plan.selection_reason,
            "fallback_occurred": plan.fallback_occurred,
        },
        "last_test_stdout": exec_res.stdout,
        "last_test_stderr": exec_res.stderr,
        "last_test_exit_code": exec_res.exit_code,
        "agent_execution_history": history,
    }
