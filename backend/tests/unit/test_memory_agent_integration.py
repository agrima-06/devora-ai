"""Unit tests for Memory Engine integration into LangGraph Agent Workflow."""
import tempfile
import uuid
from pathlib import Path
import pytest
from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.agents.specialists.coder import coder_node
from app.agents.specialists.planner import planner_node
from app.agents.state import DevoraWorkflowState
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.memory_service import MemoryService
from app.services.sandbox_service import LocalIsolatedRunner, SandboxService
from app.services.workflow_service import WorkflowService


@pytest.fixture(autouse=True)
def mock_gateway():
    mock_prov = MockLLMProvider()
    gw = ModelGateway(provider=mock_prov)
    ModelGateway.set_instance(gw)
    return mock_prov


@pytest.mark.asyncio
async def test_planner_and_coder_receive_memory_conventions(monkeypatch):
    """Planner and Coder agents must receive retrieved memory context in their prompts."""
    # Capture prompts sent to mock gateway
    captured_prompts = []
    real_gen_structured = ModelGateway.get_instance().generate_structured

    async def capturing_structured(prompt, response_model, system_instruction=None, temperature=0.2, max_output_tokens=None):
        captured_prompts.append(prompt)
        return await real_gen_structured(prompt, response_model, system_instruction, temperature, max_output_tokens)

    monkeypatch.setattr(ModelGateway.get_instance(), "generate_structured", capturing_structured)

    # 1. State with injected memory context
    state: DevoraWorkflowState = {
        "task_id": "task-mem-1",
        "task_description": "Implement ratio division with zero handling",
        "task_type": "bug_fix",
        "memory_context_summary": "- [CODING_CONVENTIONS] Zero Handling: Always raise ZeroDivisionError with explicit error message.",
        "problem_analysis": {"candidate_files": ["src/calculator.py"], "key_symbols": ["calculate_ratio"]},
        "root_cause_analysis": {"root_cause": "Division without denominator validation", "recommended_fix_pattern": "Guard clause"},
        "agent_execution_history": [],
    }

    # 2. Run Planner Node
    plan_out = await planner_node(state)
    assert plan_out["current_agent"] == "planner"
    assert any("Zero Handling" in p for p in captured_prompts)

    # 3. Run Coder Node
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "src").mkdir()
        (ws / "src" / "calculator.py").write_text("def calculate_ratio(a, b): return a / b\n")

        state["workspace_path"] = str(ws)
        state["implementation_plan"] = plan_out["implementation_plan"]
        captured_prompts.clear()

        coder_out = await coder_node(state)
        assert coder_out["current_agent"] == "coder"
        assert any("Zero Handling" in p for p in captured_prompts)


@pytest.mark.asyncio
async def test_task_outcome_distillation_into_memory(db_session, test_user, test_repository):
    """Verified task outcomes must be distilled into persistent repository memory."""
    service = MemoryService()

    task = Task(
        project_id=test_repository.project_id,
        repository_id=test_repository.id,
        created_by=test_user.id,
        title="Fix NullPointer in parser",
        prompt="Check null nodes before traversing tree",
        task_type="bug_fix",
        status="COMPLETED",
        iterations_count=1,
        target_branch="main",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    distilled_memory = await service.distill_task_outcome(
        task=task,
        user=test_user,
        db=db_session,
        test_passed=True,
        diff_patch="--- a/parser.py\n+++ b/parser.py\n+if node is None: return None",
        root_cause="Node was None during empty input traversal",
        resolution_strategy="Guard clause returning None early",
    )

    assert distilled_memory is not None
    assert distilled_memory.category == "task_outcome"
    assert distilled_memory.verification_status == "verified_outcome"
    assert "Guard clause returning None early" in distilled_memory.content

    # Verify memory is searchable
    search_results = await service.search_memories(
        repository_id=test_repository.id,
        query="empty input traversal null check",
        user=test_user,
        db=db_session,
    )
    assert len(search_results) >= 1
    assert any(s["id"] == str(distilled_memory.id) for s in search_results)
