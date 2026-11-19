"""Deterministic Mock LLM Provider for unit testing and offline development."""
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

from app.agents.gateway.base import BaseLLMProvider
from app.agents.state import (
    AnalysisOutput,
    BugInvestigationOutput,
    CodeReviewOutput,
    CodingOutput,
    FileEdit,
    FinalReportOutput,
    OrchestratorDecision,
    PlanStep,
    SecurityFinding,
    SecurityReviewOutput,
    TaskPlanOutput,
    TestRunOutput,
)

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider supplying realistic responses without network calls."""

    def __init__(self, model_name: str = "mock-model"):
        self.provider_name = "mock"
        self.model_name = model_name
        self._custom_responses: Dict[Type[BaseModel], BaseModel] = {}
        self.call_history: List[Dict[str, Any]] = []

    def set_response(self, model_class: Type[BaseModel], instance: BaseModel):
        """Override the response for a specific Pydantic model type."""
        self._custom_responses[model_class] = instance

    def clear_responses(self):
        """Clear custom responses."""
        self._custom_responses.clear()
        self.call_history.clear()

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        """Return registered custom response or synthetic domain-accurate response."""
        self.call_history.append({
            "type": "structured",
            "model": response_model.__name__,
            "prompt": prompt,
            "system_instruction": system_instruction,
        })

        if response_model in self._custom_responses:
            instance = self._custom_responses[response_model]
            return instance, {"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50}  # type: ignore

        # Default fallback responses for core Devora agents
        default_instance = self._generate_default(response_model, prompt)
        return default_instance, {"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50}  # type: ignore

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Return synthesized markdown/text response."""
        self.call_history.append({
            "type": "text",
            "prompt": prompt,
            "system_instruction": system_instruction,
        })
        text = f"# Engineering Report\n\nTask evaluated successfully.\n\nPrompt summary: {prompt[:120]}..."
        return text, {"total_tokens": 200, "prompt_tokens": 120, "completion_tokens": 80}

    def _generate_default(self, model_class: Type[BaseModel], prompt: str) -> Any:
        """Construct realistic default instances for each Pydantic schema."""
        if model_class == OrchestratorDecision:
            task_type = "exploration" if "explain" in prompt.lower() or "explore" in prompt.lower() else "bug_fix"
            next_agent = "codebase_analyst"
            return OrchestratorDecision(
                next_agent=next_agent,
                task_type=task_type,
                status="PLANNING",
                reasoning="Identified engineering requirements and routed to Codebase Analyst.",
                requires_human_approval=False,
            )

        if model_class == AnalysisOutput:
            return AnalysisOutput(
                candidate_files=["src/calculator.py"],
                key_symbols=["MathEngine", "compute_sum"],
                dependencies=["fastapi", "pytest"],
                architectural_summary="Python service with modular architecture and pytest test suite.",
            )

        if model_class == BugInvestigationOutput:
            return BugInvestigationOutput(
                bug_category="ZeroDivisionError",
                root_cause="Division by zero occurring when numbers array is empty or denominator equals zero.",
                trigger_condition="Invoking arithmetic operation with empty collection or zero denominator.",
                recommended_fix_pattern="Add explicit zero/empty boundary guard check returning 0.0 or raising graceful exception.",
                hypotheses=["Missing denominator validation", "Empty collection input in helper function"],
            )

        if model_class == TaskPlanOutput:
            return TaskPlanOutput(
                objective="Resolve ZeroDivisionError with explicit boundary guard and regression tests.",
                steps=[
                    PlanStep(
                        step_number=1,
                        description="Add boundary check for zero denominator in arithmetic function",
                        target_files=["src/calculator.py"],
                        verification_check="Zero denominator returns safe value without raising ZeroDivisionError",
                        status="PENDING",
                    ),
                    PlanStep(
                        step_number=2,
                        description="Add unit tests validating zero and boundary conditions",
                        target_files=["tests/test_calculator.py"],
                        verification_check="pytest tests/test_calculator.py passes",
                        status="PENDING",
                    ),
                ],
                test_criteria=["pytest tests/test_calculator.py passes with 0 failures"],
                risk_level="LOW",
            )

        if model_class == CodingOutput:
            return CodingOutput(
                changes=[
                    FileEdit(
                        file_path="src/calculator.py",
                        original_snippet="    return a / b",
                        new_snippet="    if b == 0:\n        return 0.0\n    return a / b",
                        explanation="Add zero denominator guard to prevent ZeroDivisionError.",
                        change_type="modified",
                    )
                ],
                summary_of_changes="Added defensive check against zero denominator in calculator division.",
                diff="--- a/src/calculator.py\n+++ b/src/calculator.py\n@@ -10,1 +10,3 @@\n-    return a / b\n+    if b == 0:\n+        return 0.0\n+    return a / b\n",
            )

        if model_class == TestRunOutput:
            return TestRunOutput(
                command="pytest",
                exit_code=0,
                passed=True,
                total_tests=5,
                passed_tests=5,
                failed_tests=0,
                duration_seconds=1.2,
                raw_stdout="5 passed in 1.20s",
                raw_stderr="",
                failure_details=[],
            )

        if model_class == CodeReviewOutput:
            return CodeReviewOutput(
                approved=True,
                quality_score=95,
                comments=["Clean defensive coding.", "Conforms to PEP 8 conventions.", "No unwanted side effects."],
                suggested_refactorings=[],
            )

        if model_class == SecurityReviewOutput:
            return SecurityReviewOutput(
                passed=True,
                findings=[],
                remediation_required=False,
            )

        if model_class == FinalReportOutput:
            return FinalReportOutput(
                title="Engineering Report: ZeroDivisionError Resolution",
                summary="Successfully identified and fixed division by zero vulnerability with boundary check.",
                root_cause_analysis="Division occurred without checking if denominator was zero.",
                changes_made=["Added zero check in src/calculator.py", "Added regression test in tests/test_calc.py"],
                verification_evidence="All 5 unit tests passed with exit code 0.",
                limitations=None,
                markdown_report="# Engineering Report\n\n## Overview\nResolved division by zero.\n\n## Evidence\nTests passed with 0 errors.",
            )

        raise ValueError(f"No mock generator defined for {model_class}")

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate 768-dim normalized pseudo-random projection vector for offline/testing."""
        from app.services.repo_intelligence_service import generate_embedding_vector
        return generate_embedding_vector(text, dim=768)
