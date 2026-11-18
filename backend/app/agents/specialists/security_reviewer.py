"""Specialist Agent 8: Security Review Agent.
Vulnerability detection, hardcoded secret scanning, and command execution auditing.
"""
import time
from typing import Any, Dict
from app.agents.gateway.gateway import ModelGateway
from app.agents.state import DevoraWorkflowState, SecurityReviewOutput
from app.core.logging import get_logger

logger = get_logger("security_review_agent")

SECURITY_SYSTEM_PROMPT = """You are the Principal Application Security Engineer for Devora AI.
Your responsibility:
1. Inspect all modified files and the unified git diff for security vulnerabilities:
   - Hardcoded credentials, tokens, passwords, or API keys.
   - Command injection (unsafe subprocess, os.system, eval).
   - SQL injection (raw query string interpolation).
   - Path traversal vulnerabilities.
   - Insecure deserialization.
   - Resource exhaustion risks.
2. Deliver a clear security verdict:
   - `passed`: True if NO HIGH or CRITICAL severity vulnerabilities exist.
   - `findings`: List of specific vulnerabilities with rule_id, severity (LOW, MEDIUM, HIGH, CRITICAL), file_path, line_number, and description.
   - `remediation_required`: True if blocking issues must be resolved before deployment.
"""


async def security_reviewer_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function for Security Review Agent."""
    start_time = time.time()
    gateway = ModelGateway.get_instance()

    git_diff = state.get("git_diff", "")
    applied_files = [f.get("file_path", "") for f in state.get("applied_file_changes", [])]

    prompt = (
        f"Modified Files: {applied_files}\n\n"
        f"Unified Git Diff:\n```diff\n{git_diff[:4000]}\n```\n\n"
        f"Audit these modifications for security vulnerabilities, secret leaks, and command injections."
    )

    security_res: SecurityReviewOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=SecurityReviewOutput,
        system_instruction=SECURITY_SYSTEM_PROMPT,
        temperature=0.1,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "security_reviewer",
        "action": "completed_security_audit",
        "passed": security_res.passed,
        "findings_count": len(security_res.findings),
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info(
        "security_review_completed",
        passed=security_res.passed,
        findings=len(security_res.findings),
    )

    return {
        "current_agent": "security_reviewer",
        "security_results": security_res.model_dump(),
        "agent_execution_history": history,
    }
