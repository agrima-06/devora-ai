"""Specialist Agent 9: Reporting Agent.
Synthesizes verified execution logs, diffs, test telemetry, and reviews into audit-ready engineering reports.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import DevoraWorkflowState, FinalReportOutput
from app.core.logging import get_logger

logger = get_logger("reporting_agent")

REPORTER_SYSTEM_PROMPT = """You are the Lead Engineering Reporter for Devora AI.
Your responsibility:
1. Synthesize all verified execution history, file changes, test outputs, and review audits into an official Engineering Report.
2. Structure the report with:
   - Descriptive title.
   - Executive Summary.
   - Root Cause Analysis (if applicable).
   - Summary of Changes Made.
   - Verification & Test Evidence (exact counts, test commands, duration).
   - Code Quality & Security Audit Findings.
   - Limitations or Next Steps.
3. Generate a complete, polished Markdown document (`markdown_report`).

AXIOM:
Never claim success or completion without concrete execution evidence.
If tests failed or retry limits were reached, explicitly report the unresolved status and failure diagnosis.
"""


async def reporter_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Reporting Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    task_type = state.get("task_type", "bug_fix")
    commit_sha = state.get("commit_sha", "unknown")
    plan = state.get("implementation_plan") or {}
    root_cause = state.get("root_cause_analysis") or {}
    applied_files = [f.get("file_path", "") for f in state.get("applied_file_changes", [])]
    git_diff = state.get("git_diff", "")
    test_results = state.get("test_results") or {}
    review = state.get("review_results") or {}
    security = state.get("security_results") or {}
    retries = state.get("retry_count", 0)
    impact = state.get("impact_analysis") or {}
    impact_summary = f"Severity: {impact.get('severity', 'N/A')}, Score: {impact.get('impact_score', 0)}/100, Affected Files: {len(impact.get('affected_files', []))}" if impact else "None"

    drift = state.get("architecture_drift") or {}
    tech_debt = state.get("technical_debt") or {}
    debt_info = f"Drift: {drift.get('drift_status', 'HEALTHY')}, Debt Score: {tech_debt.get('overall_debt_score', 0)}/100" if (drift or tech_debt) else "Healthy"

    # Refactoring Execution Telemetry (Stage 10.6)
    refactoring_plan = state.get("refactoring_plan") or {}
    refactoring_exec = state.get("refactoring_execution") or {}
    refact_info = ""
    if refactoring_plan or refactoring_exec:
        refact_info = (
            f"Refactoring Operation: {refactoring_plan.get('name', 'N/A')} ({refactoring_plan.get('category', 'GENERAL')}), "
            f"Plan Status: {refactoring_plan.get('status', 'N/A')}, "
            f"Execution Success: {refactoring_exec.get('is_success', 'N/A')}, "
            f"Preserved Semantics: {refactoring_exec.get('preserved_semantics', True)}"
        )

    prompt = (
        f"Task Description: {task_desc}\n"
        f"Task Type: {task_type}\n"
        f"Commit SHA: {commit_sha}\n"
        f"Retries Conducted: {retries}\n"
        f"Root Cause: {root_cause.get('root_cause', 'N/A')}\n"
        f"Plan Objective: {plan.get('objective', 'N/A')}\n"
        f"Modified Files: {applied_files}\n"
        f"Blast Radius Impact: {impact_summary}\n"
        f"Architecture & Technical Debt Posture: {debt_info}\n"
        f"Refactoring Operation & Behavioral Preservation: {refact_info if refact_info else 'N/A'}\n"
        f"Diff Size: {len(git_diff)} bytes\n"
        f"Test Results: passed={test_results.get('passed', False)}, "
        f"passed_count={test_results.get('passed_tests', 0)}, "
        f"failed_count={test_results.get('failed_tests', 0)}, "
        f"exit_code={test_results.get('exit_code', -1)}\n"
        f"Code Review Approved: {review.get('approved', False)}, score={review.get('quality_score', 0)}\n"
        f"Security Passed: {security.get('passed', True)}, findings={len(security.get('findings', []))}\n\n"
        f"Draft a comprehensive, evidence-grounded final engineering report."
    )

    report_res: FinalReportOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=FinalReportOutput,
        system_instruction=REPORTER_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "reporter",
        "action": "generated_final_report",
        "title": report_res.title,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("reporting_completed", title=report_res.title)

    # Determine final completion status
    tests_passed = test_results.get("passed", False) if applied_files else True
    final_status = "COMPLETED" if tests_passed else "FAILED"

    return {
        "current_agent": "reporter",
        "final_report": report_res.model_dump(),
        "execution_status": final_status,
        "agent_execution_history": history,
    }
