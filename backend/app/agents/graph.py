"""LangGraph Multi-Agent Workflow Graph with conditional routing, bounded retry, and human approval interrupts."""
from typing import Any, Dict, Literal
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.specialists.bug_investigator import bug_investigator_node
from app.agents.specialists.code_reviewer import code_reviewer_node
from app.agents.specialists.codebase_analyst import codebase_analyst_node
from app.agents.specialists.coder import coder_node
from app.agents.specialists.ml_classifier import ml_classifier_node
from app.agents.specialists.orchestrator import orchestrator_node
from app.agents.specialists.planner import planner_node
from app.agents.specialists.reporter import reporter_node
from app.agents.specialists.security_reviewer import security_reviewer_node
from app.agents.specialists.tester import tester_node
from app.agents.state import DevoraWorkflowState


def retry_incrementer_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """Increment the fix-test retry counter."""
    current_retries = state.get("retry_count", 0)
    return {"retry_count": current_retries + 1}


def human_approval_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """Human approval gate node.
    Invoked when developer approves the proposed changes.
    """
    approval_status = state.get("approval_status", "APPROVED")
    return {
        "current_agent": "human_approval",
        "approval_status": approval_status,
        "execution_status": "APPROVED" if approval_status == "APPROVED" else "REJECTED",
    }


# ---------------------------------------------------------------------------
# Conditional Routing Functions
# ---------------------------------------------------------------------------


def route_after_analysis(state: DevoraWorkflowState) -> Literal["ml_classifier", "planner", "reporter"]:
    """Route after Codebase Analyst based on task category."""
    task_type = state.get("task_type", "bug_fix")
    if task_type == "exploration":
        # Pure exploration does not modify code or run tests
        return "reporter"
    elif task_type == "bug_fix":
        return "ml_classifier"
    else:
        # feature or refactor
        return "planner"


def route_after_tester(state: DevoraWorkflowState) -> Literal["code_reviewer", "retry_incrementer", "reporter"]:
    """Evaluate test results and determine whether to review, retry, or fail."""
    test_results = state.get("test_results") or {}
    passed = test_results.get("passed", False)

    if passed:
        return "code_reviewer"

    # If the failure was due to resource limits, missing runners, timeouts, or environment constraints, do not waste LLM repair loops
    exec_status = test_results.get("execution_status")
    failure_class = test_results.get("failure_classification")
    exit_class = test_results.get("exit_classification")
    oom_killed = test_results.get("oom_killed", False)

    if (
        oom_killed
        or exec_status in ("UNAVAILABLE", "OOM_KILLED", "TIMED_OUT")
        or failure_class in (
            "RUNNER_UNAVAILABLE",
            "OOM_KILLED",
            "RESOURCE_EXHAUSTED",
            "TIMEOUT",
            "EXECUTION_TIMEOUT",
            "COMMAND_NOT_FOUND",
            "COMMAND_NOT_EXECUTABLE",
            "SANDBOX_STARTUP_FAILURE",
        )
        or exit_class in (
            "OOM_KILLED",
            "TIMEOUT",
            "COMMAND_NOT_FOUND",
            "COMMAND_NOT_EXECUTABLE",
            "SANDBOX_STARTUP_FAILURE",
            "RUNNER_UNAVAILABLE",
        )
    ):
        return "reporter"

    # If test failure was confirmed non-deterministic (FLAKY), do not waste LLM repair loops
    is_flaky = test_results.get("is_flaky", False)
    stability_class = test_results.get("stability_classification")
    if is_flaky or stability_class == "FLAKY":
        return "code_reviewer"

    # Test failed: check bounded retry limit
    retries = state.get("retry_count", 0)
    max_retries = state.get("maximum_retries", 3)

    if retries < max_retries:
        return "retry_incrementer"
    else:
        return "reporter"


def route_after_code_review(state: DevoraWorkflowState) -> Literal["security_reviewer", "retry_incrementer", "reporter"]:
    """Evaluate code review approval."""
    review = state.get("review_results") or {}
    approved = review.get("approved", True)

    if approved:
        return "security_reviewer"

    retries = state.get("retry_count", 0)
    max_retries = state.get("maximum_retries", 3)

    if retries < max_retries:
        return "retry_incrementer"
    else:
        return "reporter"


def route_after_security(state: DevoraWorkflowState) -> Literal["human_approval", "reporter"]:
    """Evaluate security audit."""
    security = state.get("security_results") or {}
    passed = security.get("passed", True)

    if passed:
        return "human_approval"
    return "reporter"


# ---------------------------------------------------------------------------
# Graph Construction & Compilation
# ---------------------------------------------------------------------------


def create_workflow_graph(
    checkpointer: BaseCheckpointSaver = None,
    interrupt_on_approval: bool = True,
):
    """Build and compile the Devora AI LangGraph multi-agent engineering workflow."""
    builder = StateGraph(DevoraWorkflowState)

    # 1. Register Nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("codebase_analyst", codebase_analyst_node)
    builder.add_node("ml_classifier", ml_classifier_node)
    builder.add_node("bug_investigator", bug_investigator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("coder", coder_node)
    builder.add_node("tester", tester_node)
    builder.add_node("retry_incrementer", retry_incrementer_node)
    builder.add_node("code_reviewer", code_reviewer_node)
    builder.add_node("security_reviewer", security_reviewer_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("reporter", reporter_node)

    # 2. Add Fixed Edges
    builder.add_edge(START, "orchestrator")
    builder.add_edge("orchestrator", "codebase_analyst")
    builder.add_edge("ml_classifier", "bug_investigator")
    builder.add_edge("bug_investigator", "planner")
    builder.add_edge("planner", "coder")
    builder.add_edge("coder", "tester")
    builder.add_edge("retry_incrementer", "coder")
    builder.add_edge("human_approval", "reporter")
    builder.add_edge("reporter", END)

    # 3. Add Conditional Routing Edges
    builder.add_conditional_edges(
        "codebase_analyst",
        route_after_analysis,
        {
            "ml_classifier": "ml_classifier",
            "planner": "planner",
            "reporter": "reporter",
        },
    )

    builder.add_conditional_edges(
        "tester",
        route_after_tester,
        {
            "code_reviewer": "code_reviewer",
            "retry_incrementer": "retry_incrementer",
            "reporter": "reporter",
        },
    )

    builder.add_conditional_edges(
        "code_reviewer",
        route_after_code_review,
        {
            "security_reviewer": "security_reviewer",
            "retry_incrementer": "retry_incrementer",
            "reporter": "reporter",
        },
    )

    builder.add_conditional_edges(
        "security_reviewer",
        route_after_security,
        {
            "human_approval": "human_approval",
            "reporter": "reporter",
        },
    )

    # Default in-memory checkpointer if none supplied
    saver = checkpointer or MemorySaver()

    interrupt_list = ["human_approval"] if interrupt_on_approval else []

    return builder.compile(checkpointer=saver, interrupt_before=interrupt_list)
