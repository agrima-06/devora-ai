"""Specialist Agent 3: Bug Investigation Agent.
Root-cause analysis, traceback dissection, and failure reproduction design.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import BugInvestigationOutput, DevoraWorkflowState
from app.core.logging import get_logger

logger = get_logger("bug_investigator_agent")

BUG_INVESTIGATION_SYSTEM_PROMPT = """You are the Lead Bug Investigator for Devora AI.
Your responsibility:
1. Examine the developer's bug report, supplied error tracebacks, and codebase analysis findings.
2. Determine the specific failure mode or bug taxonomy (e.g. ZeroDivisionError, KeyError, NullPointerException, OffByOne, ResourceLeak).
3. Identify the verified or most probable root cause of the defect.
4. Pinpoint the exact execution conditions, inputs, or edge cases triggering the failure.
5. Formulate ranked hypotheses and propose an evidence-based fix strategy.

Distinguish clearly between confirmed root causes and working hypotheses.
"""


async def bug_investigator_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Bug Investigation Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    traceback = state.get("error_traceback") or "No traceback provided."
    analysis = state.get("problem_analysis") or {}
    ml_pred = state.get("ml_bug_prediction") or {}

    ml_context = ""
    if ml_pred:
        ml_context = (
            f"Empirical ML Classifier Prior:\n"
            f"- Machine-Learned Category: {ml_pred.get('predicted_category')}\n"
            f"- Model Confidence: {ml_pred.get('confidence', 0.0) * 100:.1f}%\n"
            f"- Ambiguity / Low Confidence: {ml_pred.get('is_low_confidence', False)}\n"
            f"- Diagnostic Warning: {ml_pred.get('warning') or 'High confidence fingerprint'}\n\n"
        )

    prompt = (
        f"Bug Description: {task_desc}\n\n"
        f"Error Traceback / Error Message:\n{traceback}\n\n"
        f"{ml_context}"
        f"Candidate Files: {analysis.get('candidate_files', [])}\n"
        f"Symbols Involved: {analysis.get('key_symbols', [])}\n"
        f"Architectural Context: {analysis.get('architectural_summary', '')}\n\n"
        f"Investigate the root cause, determine the trigger conditions, and outline the fix strategy."
    )

    investigation: BugInvestigationOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=BugInvestigationOutput,
        system_instruction=BUG_INVESTIGATION_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "bug_investigator",
        "action": "diagnosed_root_cause",
        "bug_category": investigation.bug_category,
        "root_cause": investigation.root_cause,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("bug_investigation_completed", category=investigation.bug_category)

    return {
        "current_agent": "bug_investigator",
        "root_cause_analysis": investigation.model_dump(),
        "agent_execution_history": history,
    }
