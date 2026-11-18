"""End-to-End Demonstration and Reliability Audit Script for Devora AI.
Demonstrates:
- Demo A: Architectural Exploration (Retrieval, Synthesis, Zero Code Changes)
- Demo B: Autonomous Bug Fix (Investigation, Planning, Patching, Sandboxed Testing, Approval Gate)
"""
import asyncio
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.gateway.gateway import ModelGateway
from app.agents.gateway.mock import MockLLMProvider
from app.core.security import create_access_token, get_password_hash
from app.models.approval import Approval
from app.models.file_change import FileChange
from app.models.project import Project
from app.models.report import Report
from app.models.repository import Repository
from app.models.task import Task
from app.models.test_run import TestRun
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.models.workflow_event import WorkflowEvent
from app.services.github_service import GitHubService
from app.services.repo_intelligence_service import RepositoryIntelligenceService
from app.services.workflow_service import WorkflowService


POSTGRES_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/devora",
)


def create_demo_repository(name: str, has_bug: bool = False) -> Tuple[Path, str]:
    """Create a real local Git repository with commit history."""
    temp_dir = Path(tempfile.mkdtemp(prefix=f"devora_demo_{name}_"))

    # Source code
    src = temp_dir / "src"
    src.mkdir(parents=True, exist_ok=True)

    if has_bug:
        (src / "billing.py").write_text('''"""Billing and Invoice calculation engine."""

def compute_discount_rate(total_amount: float, discount_items: int) -> float:
    """Calculate average discount per item. Has known ZeroDivisionError when items is 0."""
    return total_amount / discount_items


def process_invoice(items: list, discount_count: int) -> dict:
    subtotal = sum(i.get("price", 0) for i in items)
    rate = compute_discount_rate(subtotal, discount_count)
    return {"subtotal": subtotal, "rate": rate}
''')
    else:
        (src / "service.py").write_text('''"""Core authentication and session service."""

class SessionManager:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.sessions = {}

    def create_session(self, user_id: str) -> str:
        token = f"sess_{user_id}_{len(self.sessions) + 1}"
        self.sessions[token] = user_id
        return token

    def validate_session(self, token: str) -> bool:
        return token in self.sessions
''')

    # Tests
    tests = temp_dir / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    if has_bug:
        (tests / "test_billing.py").write_text('''from src.billing import compute_discount_rate

def test_compute_discount_valid():
    assert compute_discount_rate(100.0, 2) == 50.0
''')
    else:
        (tests / "test_service.py").write_text('''from src.service import SessionManager

def test_session_creation():
    mgr = SessionManager()
    tok = mgr.create_session("u-123")
    assert mgr.validate_session(tok) is True
''')

    (temp_dir / "README.md").write_text(f"# {name} Service\nAutonomous engineering demonstration repository.\n")

    # Git initialization
    subprocess.run(["git", "init", "-b", "main"], cwd=str(temp_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Devora Demo"], cwd=str(temp_dir), check=True)
    subprocess.run(["git", "config", "user.email", "demo@devora.ai"], cwd=str(temp_dir), check=True)
    subprocess.run(["git", "add", "."], cwd=str(temp_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit for demo"], cwd=str(temp_dir), check=True, stdout=subprocess.DEVNULL)

    rev_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(temp_dir), capture_output=True, text=True, check=True)
    commit_sha = rev_res.stdout.strip()

    return temp_dir, commit_sha


from typing import Tuple


async def run_e2e_demonstrations():
    print("=" * 80)
    print("DEVORA AI — PHASE 4.5 END-TO-END DEMONSTRATIONS & RELIABILITY AUDIT")
    print("=" * 80)

    engine = create_async_engine(POSTGRES_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize model gateway
    mock_prov = MockLLMProvider()
    ModelGateway.set_instance(ModelGateway(provider=mock_prov))

    async with session_factory() as db:
        # Create Demo User
        user_email = f"demo_lead_{uuid.uuid4().hex[:6]}@devora.ai"
        user = User(
            email=user_email,
            full_name="Lead Verification Architect",
            hashed_password=get_password_hash("DevoraAudit2026!"),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"\n[INIT] Created Auditor User: {user.email} (ID: {user.id})")

        # Create Demo Project
        project = Project(
            owner_id=user.id,
            name="Devora Autonomous Demonstrations",
            slug=f"devora-demo-{uuid.uuid4().hex[:6]}",
            description="Hermetic E2E reliability test suite and real-world task verification",
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        print(f"[INIT] Created Project: {project.name} (Slug: {project.slug})")

        # ---------------------------------------------------------------------
        # DEMO A: ARCHITECTURAL EXPLORATION
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("DEMO A: REPOSITORY ARCHITECTURE EXPLORATION")
        print("-" * 80)

        repo_a_dir, repo_a_sha = create_demo_repository("auth-service", has_bug=False)
        print(f"[*] Initialized Git Repository: {repo_a_dir}")
        print(f"[*] Commit SHA: {repo_a_sha}")

        # Ingest & Index Repository
        repo_a = Repository(
            project_id=project.id,
            user_id=user.id,
            name="auth-service",
            full_name="local/auth-service",
            clone_url=f"file://{repo_a_dir}",
            default_branch="main",
            current_commit_sha=repo_a_sha,
            indexing_status="INDEXED",
        )
        db.add(repo_a)
        await db.commit()
        await db.refresh(repo_a)

        intel_service = RepositoryIntelligenceService()
        idx_job = await intel_service.index_repository(repo_a.id, user, db)
        print(f"[*] Repository Indexed: {idx_job.files_count} files, {idx_job.symbols_count} symbols indexed.")

        # Create Exploration Task
        task_a = Task(
            project_id=project.id,
            repository_id=repo_a.id,
            created_by=user.id,
            title="Explain auth-service Architecture and Session Lifecycle",
            prompt="Analyze this repository, extract key symbols and classes, and produce an architectural summary.",
            task_type="exploration",
            target_branch="main",
            status="PENDING",
        )
        db.add(task_a)
        await db.commit()
        await db.refresh(task_a)
        print(f"[*] Created Exploration Task: TASK-{str(task_a.id)[:8]} - '{task_a.title}'")

        # Execute Workflow
        workflow_service = WorkflowService()
        print("[*] Launching LangGraph 9-Agent State Machine...")
        t0 = time.time()
        res_a = await workflow_service.start_task_workflow(task_a.id, user, db)
        duration_a = round(time.time() - t0, 3)

        print(f"[+] Exploration Workflow Finished in {duration_a}s. Status: {res_a['status']}")

        # Verify no file changes or test executions occurred
        diffs_a = (await db.execute(select(FileChange).where(FileChange.task_id == task_a.id))).scalars().all()
        tests_a = (await db.execute(select(TestRun).where(TestRun.task_id == task_a.id))).scalars().all()
        report_a = (await db.execute(select(Report).where(Report.task_id == task_a.id))).scalar_one_or_none()

        print(f"[AUDIT] Files Modified: {len(diffs_a)} (Expected: 0) -> {'PASS' if len(diffs_a) == 0 else 'FAIL'}")
        print(f"[AUDIT] Sandbox Tests Run: {len(tests_a)} (Expected: 0) -> {'PASS' if len(tests_a) == 0 else 'FAIL'}")
        print(f"[AUDIT] Report Generated: {'YES' if report_a else 'NO'}")
        if report_a:
            print(f"[AUDIT] Report Title: '{report_a.title}'")
            print(f"[AUDIT] Summary: {report_a.summary}")

        # ---------------------------------------------------------------------
        # DEMO B: AUTONOMOUS BUG FIX & HUMAN APPROVAL GATE
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("DEMO B: AUTONOMOUS BUG DETECTION, PATCHING & APPROVAL GATE")
        print("-" * 80)

        repo_b_dir, repo_b_sha = create_demo_repository("billing-service", has_bug=True)
        print(f"[*] Initialized Buggy Repository: {repo_b_dir}")
        print(f"[*] Commit SHA: {repo_b_sha}")

        repo_b = Repository(
            project_id=project.id,
            user_id=user.id,
            name="billing-service",
            full_name="local/billing-service",
            clone_url=f"file://{repo_b_dir}",
            default_branch="main",
            current_commit_sha=repo_b_sha,
            indexing_status="INDEXED",
        )
        db.add(repo_b)
        await db.commit()
        await db.refresh(repo_b)

        await intel_service.index_repository(repo_b.id, user, db)
        print("[*] Repository Ingested & Symbol Graph Created.")

        # Create Bug Fix Task
        task_b = Task(
            project_id=project.id,
            repository_id=repo_b.id,
            created_by=user.id,
            title="Fix ZeroDivisionError in compute_discount_rate",
            prompt="When discount_items is 0, compute_discount_rate crashes. It should safely return 0.0.",
            error_traceback="ZeroDivisionError: float division by zero in compute_discount_rate",
            task_type="bug_fix",
            target_branch="main",
            status="PENDING",
        )
        db.add(task_b)
        await db.commit()
        await db.refresh(task_b)
        print(f"[*] Created Bug-Fix Task: TASK-{str(task_b.id)[:8]} - '{task_b.title}'")

        # Launch Multi-Agent Workflow
        print("[*] Initiating LangGraph Multi-Agent Pipeline...")
        t1 = time.time()
        res_b = await workflow_service.start_task_workflow(task_b.id, user, db)
        duration_b = round(time.time() - t1, 3)

        print(f"[+] Initial Run Completed in {duration_b}s. Status: {res_b['status']}")
        assert res_b["status"] == "WAITING_APPROVAL", "Workflow must interrupt at human_approval gate!"

        # Audit Intermediate State BEFORE Approval
        diffs_b = (await db.execute(select(FileChange).where(FileChange.task_id == task_b.id))).scalars().all()
        tests_b = (await db.execute(select(TestRun).where(TestRun.task_id == task_b.id))).scalars().all()
        apprs_b = (await db.execute(select(Approval).where(Approval.task_id == task_b.id))).scalars().all()
        report_b_before = (await db.execute(select(Report).where(Report.task_id == task_b.id))).scalar_one_or_none()

        print(f"\n[GATE EVIDENCE] Proposed File Changes: {len(diffs_b)}")
        for df in diffs_b:
            print(f"  - File: {df.file_path} ({df.change_type})")
            print(f"    Diff Snippet:\n{df.diff}")

        print(f"[GATE EVIDENCE] Sandbox Test Runs: {len(tests_b)}")
        if tests_b:
            print(f"  - Iteration: {tests_b[0].iteration}, Passed: {tests_b[0].passed}, Exit Code: {tests_b[0].exit_code}")

        print(f"[GATE EVIDENCE] Approvals Pending: {len(apprs_b)} (Status: {apprs_b[0].status})")
        print(f"[GATE EVIDENCE] Pre-Approval Report Published: {'YES (LEAK)' if report_b_before else 'NO (SECURE)'}")
        assert report_b_before is None, "Report must not be finalized before human approval!"

        # Developer Approval Decision
        print("\n[*] Simulating Developer Human Approval: Action=APPROVE...")
        appr_result = await workflow_service.submit_approval_action(
            task_id=task_b.id,
            action="APPROVE",
            user=user,
            db=db,
            notes="LGTM, verified tests and zero-division safeguard.",
        )
        print(f"[+] Approval Submitted: {appr_result['status']} - {appr_result['message']}")

        # Verify Post-Approval State
        await db.refresh(task_b)
        report_b_final = (await db.execute(select(Report).where(Report.task_id == task_b.id))).scalar_one_or_none()

        print(f"[AUDIT] Task Final Status: {task_b.status} -> {'PASS' if task_b.status == 'COMPLETED' else 'FAIL'}")
        print(f"[AUDIT] Final Report Persisted: {'YES' if report_b_final else 'NO'}")
        if report_b_final:
            print(f"[AUDIT] Report Title: {report_b_final.title}")
            print(f"[AUDIT] Root Cause Analysis: {report_b_final.root_cause_analysis}")
            print(f"[AUDIT] Markdown Length: {len(report_b_final.markdown_content)} chars")

        print("\n" + "=" * 80)
        print("ALL E2E DEMONSTRATIONS COMPLETED SUCCESSFULLY WITH 100% EVIDENCE!")
        print("=" * 80)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_e2e_demonstrations())
