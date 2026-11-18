"""Specialist Agent 1: Orchestrator Agent.
Central workflow supervisor, task classifier, and conditional router.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import DevoraWorkflowState, OrchestratorDecision
from app.core.logging import get_logger

logger = get_logger("orchestrator_agent")

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Lead Orchestrator for Devora AI, an autonomous software engineering system.
Your responsibility:
1. Understand incoming developer requests and optional error tracebacks.
2. Classify the task into exactly one category:
   - "bug_fix": Fixing a defect, error, exception, or unexpected behavior.
   - "feature": Implementing new capabilities, endpoints, or components.
   - "refactor": Improving structure, readability, or performance without behavior change.
   - "exploration": Explaining architecture, summarizing code, or analyzing functionality without modifying code.
3. Determine the immediate next agent to invoke.
   - Typically "codebase_analyst" to first understand the codebase context.
4. Set the high-level workflow status.
5. Provide concise reasoning for your routing.
"""


async def orchestrator_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Orchestrator Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    traceback = state.get("error_traceback") or "None"
    current_status = state.get("execution_status", "PLANNING")

    prompt = (
        f"Developer Request: {task_desc}\n\n"
        f"Error Traceback: {traceback}\n\n"
        f"Current Status: {current_status}\n\n"
        f"Analyze the request, classify the task type, and decide the next agent."
    )

    decision: OrchestratorDecision = await gateway.generate_structured(
        prompt=prompt,
        response_model=OrchestratorDecision,
        system_instruction=ORCHESTRATOR_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "orchestrator",
        "action": "routed_task",
        "task_type": decision.task_type,
        "next_agent": decision.next_agent,
        "reasoning": decision.reasoning,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("orchestrator_decision", task_type=decision.task_type, next_agent=decision.next_agent)

    return {
        "task_type": decision.task_type,
        "current_agent": "orchestrator",
        "execution_status": decision.status,
        "agent_execution_history": history,
    }
