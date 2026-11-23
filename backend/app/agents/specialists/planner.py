"""Specialist Agent 4: Planning Agent.
Task decomposition, DAG generation, test criteria, and implementation roadmap.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import DevoraWorkflowState, TaskPlanOutput
from app.core.logging import get_logger

logger = get_logger("planning_agent")

PLANNER_SYSTEM_PROMPT = """You are the Senior Software Architect and Adaptive Planning Agent for Devora AI.
Your responsibility:
1. Review the task requirements, codebase analysis, and bug diagnosis.
2. Examine relevant historical engineering experiences and past verified failures.
3. Formulate an implementation strategy with an explicit rationale explaining why this strategy was chosen over alternatives based on empirical evidence or first principles.
4. If historical failed approaches are present, ensure the plan explicitly avoids those pitfalls.
5. Formulate a discrete, step-by-step implementation plan:
   - Provide an actionable description for each step.
   - List the target files to modify or create.
   - State the verification check / test assertion to validate each step.
6. Define concrete test criteria and acceptance assertions.
7. Assess overall technical risk (LOW, MEDIUM, HIGH) and state key assumptions.

Keep steps minimal, focused, and directly addressing the user request without scope creep.
"""


async def planner_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Adaptive Planning Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    task_desc = state.get("task_description", "")
    task_type = state.get("task_type", "bug_fix")
    analysis = state.get("problem_analysis") or {}
    root_cause = state.get("root_cause_analysis") or {}
    memory_context = state.get("memory_context_summary") or "None"

    # Historical experiences & failure learning evidence
    experiences = state.get("historical_experiences") or []
    failures = state.get("historical_failures_to_avoid") or []

    exp_lines = []
    if experiences:
        exp_lines.append("Verified Past Experiences (Proven Guidance):")
        for exp in experiences[:3]:
            strat = exp.get("resolution_strategy") or exp.get("problem_summary") or ""
            exp_lines.append(f"- [{exp.get('task_category', '').upper()}] Status: {exp.get('status_type', 'verified')}; Strategy: {strat[:200]}")
    else:
        exp_lines.append("No prior successful experiences retrieved.")

    if failures:
        exp_lines.append("\nPrevious Failed Approaches (AVOID REPEATING):")
        for fail in failures[:3]:
            exp_lines.append(f"- [FAILED AT {fail.get('stage', 'TESTING')}] Cause: {fail.get('failure_type')}; Avoided Strategy: {fail.get('failed_strategy', '')[:150]}; Lesson: {fail.get('lessons_learned', '')[:150]}")
    
    adaptive_evidence = "\n".join(exp_lines)

    # Blast radius and impact analysis context
    impact = state.get("impact_analysis") or {}
    impact_lines = []
    if impact:
        impact_lines.append(f"Predicted Blast Radius: {impact.get('severity', 'UNKNOWN')} (Score: {impact.get('impact_score', 0)}/100, Confidence: {impact.get('confidence', 1.0)})")
        if impact.get("affected_files"):
            impact_lines.append(f"Downstream Affected Files: {', '.join(impact.get('affected_files', [])[:5])}")
        rec_tests = [t.get("test_file_path", "") for t in impact.get("recommended_tests", []) if isinstance(t, dict) and t.get("test_file_path")]
        if rec_tests:
            impact_lines.append(f"Recommended Test Coverage: {', '.join(rec_tests[:3])}")
    impact_summary = "\n".join(impact_lines) if impact_lines else "None provided"

    # Architecture intelligence & discovered conventions
    arch_patterns = state.get("architecture_patterns") or []
    arch_conventions = state.get("architecture_conventions") or []
    arch_lines = []
    if arch_patterns:
        arch_lines.append("Confirmed Architecture Patterns:")
        for p in arch_patterns[:3]:
            if isinstance(p, dict):
                arch_lines.append(f"- {p.get('name', '')} ({p.get('evidence_status', '')}): {p.get('description', '')[:120]}")
    if arch_conventions:
        arch_lines.append("Discovered Coding Conventions:")
        for c in arch_conventions[:3]:
            if isinstance(c, dict):
                arch_lines.append(f"- {c.get('name', '')}: {c.get('description', '')[:120]}")
    arch_summary = "\n".join(arch_lines) if arch_lines else "None provided"

    # Technical Debt & Drift Context
    drift = state.get("architecture_drift") or {}
    tech_debt = state.get("technical_debt") or {}
    debt_lines = []
    if drift and drift.get("drift_status") != "HEALTHY":
        debt_lines.append(f"Architectural Drift: {drift.get('drift_status')} ({drift.get('total_violations', 0)} active violations)")
    if tech_debt:
        debt_lines.append(f"Technical Debt Score: {tech_debt.get('overall_debt_score', 0)}/100 (Severity: {tech_debt.get('severity', 'CLEAN')})")
    debt_summary = "\n".join(debt_lines) if debt_lines else "Repository architecture is healthy with no elevated debt."

    # Refactoring Plan Context (Stage 10.6)
    refactoring_plan = state.get("refactoring_plan") or {}
    refact_lines = []
    if refactoring_plan:
        refact_lines.append(f"Approved Refactoring Plan: {refactoring_plan.get('name', 'Refactoring Plan')} (Category: {refactoring_plan.get('category', 'GENERAL')})")
        refact_lines.append(f"Risk Score: {refactoring_plan.get('risk_score', 0)}/100, Scope Target Files: {', '.join(refactoring_plan.get('target_files', []))}")
        steps = refactoring_plan.get("steps", [])
        if steps:
            refact_lines.append("Approved Steps:")
            for s in steps:
                if isinstance(s, dict):
                    refact_lines.append(f"- Step {s.get('step_number', 1)} [{s.get('action_type', '')}]: {s.get('description', '')} (Target: {s.get('target_file', '')})")
    refactoring_summary = "\n".join(refact_lines) if refact_lines else "None active"

    prompt = (
        f"Task Description: {task_desc}\n"
        f"Task Type: {task_type}\n"
        f"Candidate Files: {analysis.get('candidate_files', [])}\n"
        f"Key Symbols: {analysis.get('key_symbols', [])}\n"
        f"Root Cause (if bug): {root_cause.get('root_cause', 'N/A')}\n"
        f"Fix Pattern: {root_cause.get('recommended_fix_pattern', 'Standard engineering implementation')}\n\n"
        f"Blast Radius & Downstream Impact:\n{impact_summary}\n\n"
        f"Architecture Intelligence & Conventions:\n{arch_summary}\n\n"
        f"Technical Debt & Drift Posture:\n{debt_summary}\n\n"
        f"Active Refactoring Plan Context:\n{refactoring_summary}\n\n"
        f"Adaptive Historical Experience Evidence:\n{adaptive_evidence}\n\n"
        f"Project Conventions & Engineering Memory:\n{memory_context}\n\n"
        f"Produce a structured implementation plan with strategy, strategy_rationale, discrete steps, and test criteria."
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
