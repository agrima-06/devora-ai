"""Unit tests for all 9 Specialist Agent nodes."""
import tempfile
from pathlib import Path
import pytest

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.agents.specialists.bug_investigator import bug_investigator_node
from app.agents.specialists.code_reviewer import code_reviewer_node
from app.agents.specialists.codebase_analyst import codebase_analyst_node
from app.agents.specialists.coder import coder_node
from app.agents.specialists.orchestrator import orchestrator_node
from app.agents.specialists.planner import planner_node
from app.agents.specialists.reporter import reporter_node
from app.agents.specialists.security_reviewer import security_reviewer_node
from app.agents.specialists.tester import tester_node as run_tester_agent_node
from app.agents.state import DevoraWorkflowState


@pytest.fixture(autouse=True)
def setup_mock_gateway():
    mock_prov = MockLLMProvider()
    gateway = ModelGateway(provider=mock_prov)
    ModelGateway.set_instance(gateway)
    yield


@pytest.mark.asyncio
async def test_agent_1_orchestrator():
    state: DevoraWorkflowState = {
        "task_description": "Fix ZeroDivisionError in calculation",
        "error_traceback": "ZeroDivisionError: division by zero",
    }
    out = await orchestrator_node(state)
    assert out["task_type"] == "bug_fix"
    assert out["current_agent"] == "orchestrator"
    assert len(out["agent_execution_history"]) == 1


@pytest.mark.asyncio
async def test_agent_2_codebase_analyst():
    state: DevoraWorkflowState = {
        "task_description": "Locate arithmetic calculator class",
        "retrieved_files": [{"file_path": "src/calculator.py", "summary": "Calculator module"}],
        "retrieved_symbols": [{"name": "MathEngine"}],
    }
    out = await codebase_analyst_node(state)
    assert out["current_agent"] == "codebase_analyst"
    analysis = out["problem_analysis"]
    assert "candidate_files" in analysis
    assert "src/calculator.py" in analysis["candidate_files"]


@pytest.mark.asyncio
async def test_agent_3_bug_investigator():
    state: DevoraWorkflowState = {
        "task_description": "Fix ZeroDivisionError in calculation",
        "error_traceback": "Traceback: ZeroDivisionError: division by zero",
        "problem_analysis": {"candidate_files": ["src/calculator.py"]},
    }
    out = await bug_investigator_node(state)
    assert out["current_agent"] == "bug_investigator"
    rca = out["root_cause_analysis"]
    assert rca["bug_category"] is not None
    assert rca["root_cause"] is not None


@pytest.mark.asyncio
async def test_agent_4_planner():
    state: DevoraWorkflowState = {
        "task_description": "Implement safe division guard",
        "task_type": "bug_fix",
        "problem_analysis": {"candidate_files": ["src/calculator.py"]},
        "root_cause_analysis": {"root_cause": "Division by zero without guard"},
    }
    out = await planner_node(state)
    assert out["current_agent"] == "planner"
    plan = out["implementation_plan"]
    assert len(plan["steps"]) >= 1
    assert plan["risk_level"] in ("LOW", "MEDIUM", "HIGH")


@pytest.mark.asyncio
async def test_agent_5_coder():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "src").mkdir()
        (ws / "src" / "calculator.py").write_text("def divide(a, b):\n    return a / b\n")

        state: DevoraWorkflowState = {
            "task_description": "Fix division by zero",
            "workspace_path": str(ws),
            "implementation_plan": {
                "objective": "Safe division",
                "steps": [{"target_files": ["src/calculator.py"]}],
            },
            "retry_count": 0,
        }
        out = await coder_node(state)
        assert out["current_agent"] == "coder"
        assert len(out["applied_file_changes"]) >= 1
        assert "diff" in out["applied_file_changes"][0]
        # Verify file modified on disk
        new_content = (ws / "src" / "calculator.py").read_text()
        assert "if b == 0:" in new_content


@pytest.mark.asyncio
async def test_agent_6_tester():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "tests").mkdir()
        (ws / "tests" / "test_sample.py").write_text("def test_ok(): assert True\n")

        state: DevoraWorkflowState = {
            "workspace_path": str(ws),
        }
        out = await run_tester_agent_node(state)
        assert out["current_agent"] == "tester"
        tr = out["test_results"]
        assert tr["passed"] is True
        assert tr["exit_code"] == 0


@pytest.mark.asyncio
async def test_agent_7_code_reviewer():
    state: DevoraWorkflowState = {
        "task_description": "Review safe division fix",
        "git_diff": "+    if b == 0:\n+        return 0.0\n",
        "applied_file_changes": [{"file_path": "src/calculator.py"}],
    }
    out = await code_reviewer_node(state)
    assert out["current_agent"] == "code_reviewer"
    rev = out["review_results"]
    assert rev["approved"] is True
    assert rev["quality_score"] > 0


@pytest.mark.asyncio
async def test_agent_8_security_reviewer():
    state: DevoraWorkflowState = {
        "git_diff": "+    if b == 0:\n+        return 0.0\n",
        "applied_file_changes": [{"file_path": "src/calculator.py"}],
    }
    out = await security_reviewer_node(state)
    assert out["current_agent"] == "security_reviewer"
    sec = out["security_results"]
    assert sec["passed"] is True
    assert isinstance(sec["findings"], list)


@pytest.mark.asyncio
async def test_agent_9_reporter():
    state: DevoraWorkflowState = {
        "task_description": "Fix ZeroDivisionError",
        "task_type": "bug_fix",
        "commit_sha": "abc1234",
        "test_results": {"passed": True, "passed_tests": 5, "failed_tests": 0, "exit_code": 0},
        "applied_file_changes": [{"file_path": "src/calculator.py"}],
        "git_diff": "+    if b == 0: return 0.0\n",
    }
    out = await reporter_node(state)
    assert out["current_agent"] == "reporter"
    rep = out["final_report"]
    assert rep["title"] is not None
    assert len(rep["markdown_report"]) > 0
    assert out["execution_status"] == "COMPLETED"
