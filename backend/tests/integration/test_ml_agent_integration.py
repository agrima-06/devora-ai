"""Integration tests for ML Bug Classifier LangGraph node and multi-agent routing."""
import pytest
from app.agents.graph import create_workflow_graph, route_after_analysis
from app.agents.specialists.ml_classifier import ml_classifier_node
from app.agents.state import DevoraWorkflowState
from app.ml.preprocessor import BugCategory


@pytest.mark.asyncio
async def test_ml_classifier_node_execution():
    state: DevoraWorkflowState = {
        "task_id": "test-task-1",
        "task_description": "Fix bug in calculating user discounts",
        "error_traceback": 'Traceback (most recent call last):\n  File "calc.py", line 12\n    return total / count\nZeroDivisionError: division by zero',
        "agent_execution_history": [],
    }

    result = await ml_classifier_node(state)

    assert result["current_agent"] == "ml_classifier"
    assert "ml_bug_prediction" in result
    pred = result["ml_bug_prediction"]
    assert pred["predicted_category"] == BugCategory.RUNTIME_LOGIC_ERROR.value
    assert pred["confidence"] > 0.0
    assert len(result["agent_execution_history"]) == 1
    assert result["agent_execution_history"][0]["agent"] == "ml_classifier"


def test_workflow_conditional_routing_bug_fix():
    bug_state: DevoraWorkflowState = {"task_type": "bug_fix"}
    feature_state: DevoraWorkflowState = {"task_type": "feature"}
    explore_state: DevoraWorkflowState = {"task_type": "exploration"}

    assert route_after_analysis(bug_state) == "ml_classifier"
    assert route_after_analysis(feature_state) == "planner"
    assert route_after_analysis(explore_state) == "reporter"


def test_workflow_graph_compilation_with_ml():
    graph = create_workflow_graph(interrupt_on_approval=False)
    assert graph is not None
    # Verify ml_classifier node is present in compiled graph nodes
    assert "ml_classifier" in graph.nodes
