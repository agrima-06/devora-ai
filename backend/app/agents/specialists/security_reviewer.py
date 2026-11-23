"""Specialist Agent 8: Security Review Agent.
Vulnerability detection, hardcoded secret scanning, workspace manifest security, and command execution auditing.
"""
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from app.agents.gateway.gateway import ModelGateway
from app.agents.state import DevoraWorkflowState, SecurityFinding, SecurityReviewOutput
from app.core.logging import get_logger

# Import secret patterns from scripts/security_scanner
scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

try:
    from security_scanner import SECRET_PATTERNS
except Exception:
    SECRET_PATTERNS = {
        "Google API Key": re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b"),
        "GitHub Personal Access Token": re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"),
        "OpenAI / Anthropic Secret Key": re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
        "Hardcoded Database Connection": re.compile(r"postgres(?:ql)?://[a-zA-Z0-9_-]+:[^@\s/:]+@[a-zA-Z0-9.-]+"),
    }

logger = get_logger("security_review_agent")

SECURITY_SYSTEM_PROMPT = """You are the Principal Application Security Engineer for Devora AI.
Your responsibility:
1. Inspect all modified files, package manifests, and the unified git diff for security vulnerabilities:
   - Hardcoded credentials, tokens, passwords, private keys, or API keys.
   - Package manifest security & workspace boundaries: unpinned or vulnerable dependencies, undeclared cross-package dependencies, malicious scripts in package.json/Cargo.toml/pyproject.toml.
   - Command injection (unsafe subprocess, os.system, eval).
   - SQL injection (raw query string interpolation).
   - Path traversal vulnerabilities.
   - Insecure deserialization.
   - Resource exhaustion risks.
   - Violations of architectural security boundaries: direct LLM calls bypassing ModelGateway, routes bypassing auth dependencies, or code bypassing sandbox runner.
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

    drift = state.get("architecture_drift") or {}
    sec_violations = [v for v in drift.get("violations", []) if v.get("category") == "security"]
    sec_context = ""
    if sec_violations:
        sec_context = "\nDetected Security Boundary Drift:\n" + "\n".join(f"- {v.get('name')}: {v.get('explanation')}" for v in sec_violations[:3]) + "\n"

    # Refactoring plan security boundary checks (Stage 10.6)
    refactoring_plan = state.get("refactoring_plan") or {}
    refact_sec_context = ""
    if refactoring_plan:
        refact_sec_context = f"\nRefactoring Plan Guardrail Active: Plan {refactoring_plan.get('id', 'N/A')}. Verify that refactoring does not bypass authorization guards or access controls.\n"

    prompt = (
        f"Modified Files: {applied_files}\n\n"
        f"Unified Git Diff:\n```diff\n{git_diff[:4000]}\n```\n"
        f"{sec_context}"
        f"{refact_sec_context}\n"
        f"Audit these modifications for security vulnerabilities, secret leaks, command injections, and architectural boundary violations."
    )

    security_res: SecurityReviewOutput = await gateway.generate_structured(
        prompt=prompt,
        response_model=SecurityReviewOutput,
        system_instruction=SECURITY_SYSTEM_PROMPT,
        temperature=0.1,
    )

    # Deterministic static secret pre-screening on diff additions
    for line_idx, line in enumerate(git_diff.splitlines(), start=1):
        if line.startswith("+") and not line.startswith("+++"):
            for sec_name, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    security_res.findings.append(
                        SecurityFinding(
                            rule_id="SEC-HARDCODED-SECRET",
                            severity="CRITICAL",
                            file_path=applied_files[0] if applied_files else "diff",
                            line_number=line_idx,
                            description=f"Automated scan detected exposed {sec_name}. Hardcoded secrets are strictly prohibited.",
                        )
                    )
                    security_res.passed = False
                    security_res.remediation_required = True

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
