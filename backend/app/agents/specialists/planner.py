"""Specialist Agent 4: Planning Agent.
Task decomposition, DAG generation, test criteria, and implementation roadmap.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import DevoraWorkflowState, TaskPlanOutput
from app.core.logging import get_logger

logger = get_logger("planning_agent")

PLANNER_SYSTEM_PROMPT = """You are the Senior Software Architect and Planning Agent for Devora AI.
Your responsibility:
1. Review the task requirements, codebase analysis, and bug diagnosis.
2. Formulate a discrete, step-by-step implementation plan.
3. For each step:
   - Provide an actionable description.
   - List the target files to modify or create.
   - State the verification check / test assertion to validate the step.
4. Define concrete test criteria and acceptance assertions.
5. Assess overall technical risk (LOW, MEDIUM, HIGH).

Keep steps minimal, focused, and directly addressing the user request without scope creep.
"""


async def planner_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Planning Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    task_type = state.get("task_type", "bug_fix")
    analysis = state.get("problem_analysis") or {}
    root_cause = state.get("root_cause_analysis") or {}

    prompt = (
        f"Task Description: {task_desc}\n"
        f"Task Type: {task_type}\n"
        f"Candidate Files: {analysis.get('candidate_files', [])}\n"
        f"Key Symbols: {analysis.get('key_symbols', [])}\n"
        f"Root Cause (if bug): {root_cause.get('root_cause', 'N/A')}\n"
        f"Fix Pattern: {root_cause.get('recommended_fix_pattern', 'Standard engineering implementation')}\n\n"
        f"Produce a structured implementation plan with discrete steps and test criteria."
    )

    plan: TaskPlanOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=TaskPlanOutput,
        system_instruction=PLANNER_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "planner",
        "action": "generated_implementation_plan",
        "steps_count": len(plan.steps),
        "risk_level": plan.risk_level,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("planning_completed", steps=len(plan.steps), risk=plan.risk_level)

    return {
        "current_agent": "planner",
        "implementation_plan": plan.model_dump(),
        "execution_status": "IN_PROGRESS",
        "agent_execution_history": history,
    }
