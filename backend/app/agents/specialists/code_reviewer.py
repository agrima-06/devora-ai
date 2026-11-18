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

    prompt = (
        f"Task Description: {task_desc}\n"
        f"Modified Files: {applied_files}\n"
        f"Test Run Passed: {test_results.get('passed', False)}\n\n"
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
