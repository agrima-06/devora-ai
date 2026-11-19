"""Specialist Agent 5: Coding Agent.
Minimal precision code modifications, diff generation, and failure-driven patch correction.
"""
import time
from pathlib import Path
from typing import Any, Dict, List
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import CodingOutput, DevoraWorkflowState
from app.core.logging import get_logger
from app.services.sandbox_service import SandboxService

logger = get_logger("coding_agent")

CODER_SYSTEM_PROMPT = """You are the Senior Software Engineer and Coding Agent for Devora AI.
Your responsibility:
1. Implement the technical plan with precision, modifying only files and functions within scope.
2. Produce structured FileEdit instructions with:
   - `file_path`: Relative path of file to modify or create.
   - `original_snippet`: The exact code snippet to replace (empty string if adding new file).
   - `new_snippet`: The replacement code or new file content.
   - `explanation`: Reason for the change.
   - `change_type`: "modified", "added", or "deleted".
3. If this is a RETRY iteration after a failed test or review:
   - Carefully inspect the test failures, traceback, compiler errors, or review feedback.
   - Address the exact defect without breaking other functionality.
4. Adhere strictly to project conventions and existing code style.
5. Minimize unnecessary edits.
"""


async def coder_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Coding Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()
    sandbox = SandboxService()

    task_desc = state.get("task_description", "")
    plan = state.get("implementation_plan") or {}
    retry_count = state.get("retry_count", 0)
    workspace_path = Path(state.get("workspace_path", "/tmp/devora/workspace"))

    # If retry, retrieve previous test failure outputs
    test_results = state.get("test_results") or {}
    test_stdout = state.get("last_test_stdout") or ""
    test_stderr = state.get("last_test_stderr") or ""
    review_results = state.get("review_results") or {}

    retry_context = ""
    if retry_count > 0:
        retry_context = (
            f"\n\n*** CORRECTION ATTEMPT (Iteration {retry_count + 1}) ***\n"
            f"Previous Test Exit Code: {test_results.get('exit_code', 1)}\n"
            f"Test Stdout:\n{test_stdout[:1000]}\n"
            f"Test Stderr:\n{test_stderr[:1000]}\n"
            f"Review Feedback:\n{review_results.get('comments', [])}\n"
            f"Please diagnose the test failure and correct the code changes."
        )

    # Read contents of target files if they exist in workspace
    target_files = []
    for step in plan.get("steps", []):
        target_files.extend(step.get("target_files", []))

    file_snippets: List[str] = []
    for rel_path in set(target_files):
        fpath = workspace_path / rel_path
        if fpath.exists() and fpath.is_file():
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                file_snippets.append(f"--- File: {rel_path} ---\n{content[:2500]}\n")
            except Exception as e:
                logger.debug("could_not_read_file_snippet", file=rel_path, error=str(e))

    files_context = "\n".join(file_snippets) if file_snippets else "No existing files read."

    memory_context = state.get("memory_context_summary") or ""
    conventions_block = f"Project Conventions & Architectural Patterns:\n{memory_context}\n\n" if memory_context else ""

    prompt = (
        f"Task Description: {task_desc}\n\n"
        f"Plan Objective: {plan.get('objective', '')}\n"
        f"Plan Steps: {plan.get('steps', [])}\n\n"
        f"{conventions_block}"
        f"Existing Workspace Files:\n{files_context}\n"
        f"{retry_context}\n\n"
        f"Produce the structured code changes to implement the solution adhering to project conventions."
    )

    coding_res: CodingOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=CodingOutput,
        system_instruction=CODER_SYSTEM_PROMPT,
        temperature=0.1,
    )

    # Safely apply the proposed file edits inside the task workspace
    applied_result = sandbox.apply_edits(workspace_path, coding_res.changes)

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "coder",
        "action": "applied_code_changes",
        "files_modified": [c.file_path for c in coding_res.changes],
        "iteration": retry_count + 1,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("coder_applied_edits", count=len(coding_res.changes), iteration=retry_count + 1)

    return {
        "current_agent": "coder",
        "proposed_file_changes": [c.model_dump() for c in coding_res.changes],
        "applied_file_changes": applied_result["modified_files"],
        "git_diff": applied_result["git_diff"],
        "agent_execution_history": history,
    }
