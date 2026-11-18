"""Unit tests for LangGraph multi-agent routing, conditional branching, and bounded retry loops."""
import tempfile
from pathlib import Path
import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.agents.graph import create_workflow_graph
from app.agents.state import (
    CodingOutput,
    DevoraWorkflowState,
    FileEdit,
    OrchestratorDecision,
    TestRunOutput,
)


@pytest.fixture(autouse=True)
def setup_mock():
    mock_prov = MockLLMProvider()
    gateway = ModelGateway(provider=mock_prov)
    ModelGateway.set_instance(gateway)
    yield


@pytest.mark.asyncio
async def test_workflow_exploration_branching():
    """Exploration tasks must route Orchestrator -> Codebase Analyst -> Reporter -> END, skipping coder/tester."""
    mock_prov = MockLLMProvider()
    mock_prov.set_response(
        OrchestratorDecision,
        OrchestratorDecision(
            next_agent="codebase_analyst",
            task_type="exploration",
            status="PLANNING",
            reasoning="User asked for architecture walkthrough.",
            requires_human_approval=False,
        ),
    )
    ModelGateway.set_instance(ModelGateway(provider=mock_prov))

    graph = create_workflow_graph(checkpointer=MemorySaver(), interrupt_on_approval=False)

    initial_state: DevoraWorkflowState = {
        "task_id": "exp-1",
        "task_description": "Explain the project architecture and main modules",
        "task_type": "exploration",
        "retry_count": 0,
        "maximum_retries": 3,
        "agent_execution_history": [],
    }

    config = {"configurable": {"thread_id": "thread-exp-1"}}
    final_state = await graph.ainvoke(initial_state, config=config)

    agents_invoked = [h["agent"] for h in final_state["agent_execution_history"]]
    assert "orchestrator" in agents_invoked
    assert "codebase_analyst" in agents_invoked
    assert "reporter" in agents_invoked
    # Verify coding and testing agents were skipped!
    assert "coder" not in agents_invoked
    assert "tester" not in agents_invoked


@pytest.mark.asyncio
async def test_workflow_bounded_retry_loop_halts():
    """Verify that failing tests trigger retry attempts and halt strictly at maximum 3 retries."""
    mock_prov = MockLLMProvider()
    # Force tester to always return failing test result
    failing_test = TestRunOutput(
        command="pytest",
        exit_code=1,
        passed=False,
        total_tests=5,
        passed_tests=4,
        failed_tests=1,
        duration_seconds=0.5,
        raw_stdout="1 failed",
        raw_stderr="AssertionError",
        failure_details=["AssertionError in test_calc"],
    )
    mock_prov.set_response(TestRunOutput, failing_test)
    ModelGateway.set_instance(ModelGateway(provider=mock_prov))

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "src").mkdir()
        (ws / "src" / "calc.py").write_text("x = 1\n")

        graph = create_workflow_graph(checkpointer=MemorySaver(), interrupt_on_approval=False)

        initial_state: DevoraWorkflowState = {
            "task_id": "retry-1",
            "task_description": "Fix bug",
            "task_type": "bug_fix",
            "workspace_path": str(ws),
            "retry_count": 0,
            "maximum_retries": 3,
            "agent_execution_history": [],
        }

        config = {"configurable": {"thread_id": "thread-retry-1"}}
        final_state = await graph.ainvoke(initial_state, config=config)

        # Retry count must hit exactly maximum_retries (3)
        assert final_state["retry_count"] == 3
        # Must terminate at reporter with failed status
        assert final_state["current_agent"] == "reporter"
        assert final_state["execution_status"] == "FAILED"


@pytest.mark.asyncio
async def test_workflow_human_approval_interrupt_and_resume():
    """Workflow must pause before human approval, save checkpoint, and resume when approved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "src").mkdir()
        (ws / "src" / "calc.py").write_text("def add(a, b): return a + b\n")
        (ws / "tests").mkdir()
        (ws / "tests" / "test_calc.py").write_text("def test_dummy(): assert True\n")

        checkpointer = MemorySaver()
        graph = create_workflow_graph(checkpointer=checkpointer, interrupt_on_approval=True)

        initial_state: DevoraWorkflowState = {
            "task_id": "appr-1",
            "task_description": "Add safe addition",
            "task_type": "feature",
            "workspace_path": str(ws),
            "retry_count": 0,
            "maximum_retries": 3,
            "agent_execution_history": [],
        }

        config = {"configurable": {"thread_id": "thread-appr-1"}}

        # Run until interrupt
        interrupted_state = await graph.ainvoke(initial_state, config=config)
        state_snap = graph.get_state(config)
        assert state_snap.next == ("human_approval",)

        # Resume with approval
        resumed_state = await graph.ainvoke(None, config=config)
        assert resumed_state["current_agent"] == "reporter"
        assert resumed_state["execution_status"] == "COMPLETED"
