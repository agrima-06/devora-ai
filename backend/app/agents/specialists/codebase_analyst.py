"""Specialist Agent 2: Codebase Analyst Agent.
Grounded repository static analysis, symbol retrieval, and architectural context extraction.
"""
import time
from typing import Any, Dict, List
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import AnalysisOutput, DevoraWorkflowState
from app.core.logging import get_logger

logger = get_logger("codebase_analyst_agent")

ANALYST_SYSTEM_PROMPT = """You are the Codebase Analyst for Devora AI.
Your responsibility:
1. Review the developer's request, error tracebacks, and actual repository search results.
2. Identify candidate source files directly involved in or affected by the task.
3. Identify key functions, classes, and architectural symbols involved.
4. Highlight internal and external dependencies.
5. Provide a succinct, grounded architectural summary.

CRITICAL:
Never invent imaginary files or functions. Rely strictly on the actual files and symbols provided in context.
"""


async def codebase_analyst_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Codebase Analyst Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    traceback = state.get("error_traceback") or "None"
    repo_context = state.get("repository_context", {})
    retrieved_files = state.get("retrieved_files", [])
    retrieved_symbols = state.get("retrieved_symbols", [])

    files_summary = ", ".join(f.get("file_path", "") for f in retrieved_files[:10]) or "None provided"
    symbols_summary = ", ".join(s.get("name", "") for s in retrieved_symbols[:15]) or "None provided"
    arch_summary = repo_context.get("architecture_summary", "Standard application")

    prompt = (
        f"Developer Request: {task_desc}\n\n"
        f"Error Traceback: {traceback}\n\n"
        f"Repository Architecture:\n{arch_summary}\n\n"
        f"Indexed Files Found:\n{files_summary}\n\n"
        f"Extracted AST Symbols:\n{symbols_summary}\n\n"
        f"Analyze this context and output candidate files, key symbols, dependencies, and architectural overview."
    )

    analysis: AnalysisOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=AnalysisOutput,
        system_instruction=ANALYST_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "codebase_analyst",
        "action": "analyzed_codebase",
        "candidate_files": analysis.candidate_files,
        "key_symbols": analysis.key_symbols,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info("codebase_analyst_completed", files=analysis.candidate_files)

    return {
        "current_agent": "codebase_analyst",
        "problem_analysis": analysis.model_dump(),
        "agent_execution_history": history,
    }
