"""Specialist Agent 7: Code Review Agent.
Quality assurance, regression checking, and maintainability audit.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import CodeReviewOutput, DevoraWorkflowState
from app.core.logging import get_logger

logger = get_logger("code_review_agent")

CODE_REVIEW_SYSTEM_PROMPT = """You are the Senior Code Reviewer for Devora AI.
Your responsibility:
1. Thoroughly review proposed code modifications and the resulting git diff.
2. Check for:
   - Logic correctness and potential edge-case failures.
   - Unintended side-effects or regressions in unrelated code.
   - Adherence to language idioms and clean code practices.
   - Redundant or stray debug statements (print, console.log).
3. Deliver an objective verdict:
   - approved: True if code is clean and production-ready.
   - quality_score: Integer 0-100.
   - comments: Bullet points detailing specific constructive feedback.
   - suggested_refactorings: Optional non-blocking recommendations.
"""


async def code_reviewer_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Code Review Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    git_diff = state.get("git_diff", "")
    applied_files = [f.get("file_path", "") for f in state.get("applied_file_changes", [])]
    test_results = state.get("test_results") or {}
    impact = state.get("impact_analysis") or {}

    impact_context = ""
    if impact:
        impact_context = (
            f"\nPredicted Blast Radius: Severity {impact.get('severity', 'UNKNOWN')} "
            f"(Score {impact.get('impact_score', 0)}/100). "
            f"Downstream Affected Files: {impact.get('affected_files', [])[:5]}.\n"
            f"Ensure code changes do not inadvertently break downstream consumer interfaces.\n"
        )

    # Architectural conventions context
    arch_conventions = state.get("architecture_conventions") or []
    conv_context = ""
    if arch_conventions:
        conv_items = [
            f"- {c.get('name')}: {c.get('description')}"
            for c in arch_conventions[:4]
            if isinstance(c, dict) and c.get("name")
        ]
        if conv_items:
            conv_context = "\nEnforced Repository Conventions:\n" + "\n".join(conv_items) + "\nVerify diff conforms to these architectural conventions.\n"

    # Architecture drift & debt context
    drift = state.get("architecture_drift") or {}
    drift_context = ""
    if drift and drift.get("drift_status") != "HEALTHY":
        drift_context = f"\nActive Architecture Drift: {drift.get('drift_status')} ({drift.get('total_violations', 0)} violations). Ensure diff does not introduce new layering, cycle, or boundary violations.\n"

    # Refactoring Scope & Semantics Verification (Stage 10.6)
    refactoring_plan = state.get("refactoring_plan") or {}
    refact_context = ""
    if refactoring_plan:
        allowed_files = set(refactoring_plan.get("target_files", []))
        out_of_scope = [f for f in applied_files if f and f not in allowed_files]
        scope_warning = f" WARNING: Edits detected outside planned scope: {out_of_scope}." if out_of_scope else " All edits within planned target files."
        refact_context = (
            f"\nApproved Refactoring Plan: {refactoring_plan.get('name', 'Refactoring')} ({refactoring_plan.get('category', 'GENERAL')}).\n"
            f"Planned Target Files: {list(allowed_files)}.{scope_warning}\n"
            f"Verify that refactored code preserves behavioral semantics, adheres to approved steps, and introduces no extraneous edits.\n"
        )

    prompt = (
        f"Task Description: {task_desc}\n"
        f"Modified Files: {applied_files}\n"
        f"Test Run Passed: {test_results.get('passed', False)}\n"
        f"{impact_context}"
        f"{conv_context}"
        f"{drift_context}"
        f"{refact_context}\n"
        f"Unified Git Diff:\n```diff\n{git_diff[:4000]}\n```\n\n"
        f"Review these code changes and provide structured review feedback."
    )

    review: CodeReviewOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=CodeReviewOutput,
        system_instruction=CODE_REVIEW_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "code_reviewer",
        "action": "completed_review",
        "approved": review.approved,
        "quality_score": review.quality_score,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("code_review_completed", approved=review.approved, score=review.quality_score)

    return {
        "current_agent": "code_reviewer",
        "review_results": review.model_dump(),
        "agent_execution_history": history,
    }
