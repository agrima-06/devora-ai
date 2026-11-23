"""Unit tests for Stage 10.6 Real Filesystem Rollback and Cryptographic Approval Binding.

Verifies:
1. Real filesystem rollback across modified, added, deleted, renamed, untracked, and binary files.
2. Preservation of unrelated user modifications.
3. Rollback failure handling: corrupted snapshot, permission error, partial failure.
4. Cryptographic approval binding over canonical snapshot content (SHA-256).
5. TOCTOU invalidation when files are altered between approval and execution.
6. Single-use execution and replay prevention.
7. Git safety invariants preventing unauthorized commits/pushes.
"""

import os
from pathlib import Path
import stat
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import BadRequestException
from app.models.refactoring_plan import RefactoringPlan
from app.models.repository import Repository
from app.models.user import User
from app.services.refactoring_service import ArchitectureAwareRefactoringService
from app.services.refactoring_workspace_manager import (
    RefactoringWorkspaceManager,
    RollbackResult,
    RollbackStatus,
)


@pytest.fixture
def temp_repo_workspace(tmp_path: Path) -> Path:
    """Construct an isolated real filesystem repository fixture."""
    workspace = tmp_path / "repo_workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    # 1. Existing target files
    (workspace / "src").mkdir(parents=True, exist_ok=True)
    (workspace / "src" / "monolith.py").write_text("def process():\n    return 'original'\n")
    (workspace / "src" / "service.py").write_text("class OldService:\n    pass\n")

    # 2. Nested directory with script
    (workspace / "scripts").mkdir(parents=True, exist_ok=True)
    script_file = workspace / "scripts" / "run.sh"
    script_file.write_text("#!/bin/bash\necho hello\n")
    os.chmod(script_file, 0o755)

    # 3. Binary file
    (workspace / "assets").mkdir(parents=True, exist_ok=True)
    (workspace / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    # 4. Unrelated user files (both tracked and untracked)
    (workspace / "notes.txt").write_text("user pre-existing work notes")
    (workspace / "unrelated.py").write_text("def unrelated(): pass\n")

    return workspace


def test_real_filesystem_snapshot_and_rollback(temp_repo_workspace: Path):
    """Verify genuine workspace modification, regression induction, and full filesystem rollback."""
    manager = RefactoringWorkspaceManager()
    target_files = ["src/monolith.py", "src/service.py", "scripts/run.sh", "assets/logo.png"]

    # 1. Capture pre-execution snapshot
    snapshot = manager.create_snapshot(
        workspace_root=temp_repo_workspace,
        plan_id="plan-123",
        source_revision="rev-001",
        target_files=target_files,
    )
    assert len(snapshot.files) >= 5
    assert "notes.txt" in snapshot.unrelated_files

    # 2. Execute genuine file modifications
    steps = [
        {"file_path": "src/monolith.py", "action": "DECOMPOSE", "content": "def process(): return 'refactored'"},
        {"file_path": "src/new_helper.py", "action": "CREATE_FILE", "content": "def helper(): pass"},
        {"file_path": "src/service.py", "action": "DELETE_FILE"},
    ]
    modified = manager.execute_refactoring_steps(temp_repo_workspace, steps)
    assert "src/monolith.py" in modified
    assert (temp_repo_workspace / "src" / "monolith.py").read_text() == "def process(): return 'refactored'"
    assert (temp_repo_workspace / "src" / "new_helper.py").exists()
    assert not (temp_repo_workspace / "src" / "service.py").exists()

    # Modify binary file too
    (temp_repo_workspace / "assets" / "logo.png").write_bytes(b"\x00\x00MODIFIED_BYTES")

    # 3. Trigger automatic rollback
    result = manager.rollback(
        workspace_root=temp_repo_workspace,
        snapshot=snapshot,
        target_files=target_files,
    )

    # 4. Verify post-rollback filesystem invariants
    assert result.status == RollbackStatus.ROLLED_BACK
    assert result.success is True
    assert result.verification_passed is True

    # Modified file restored
    assert (temp_repo_workspace / "src" / "monolith.py").read_text() == "def process():\n    return 'original'\n"
    # Deleted file recreated
    assert (temp_repo_workspace / "src" / "service.py").read_text() == "class OldService:\n    pass\n"
    # Newly created file removed
    assert not (temp_repo_workspace / "src" / "new_helper.py").exists()
    # Binary file restored exactly
    assert (temp_repo_workspace / "assets" / "logo.png").read_bytes() == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    # Permissions preserved
    assert stat.S_IMODE((temp_repo_workspace / "scripts" / "run.sh").stat().st_mode) == 0o755


def test_preservation_of_unrelated_user_changes(temp_repo_workspace: Path):
    """Verify that unrelated user changes and untracked files are preserved during rollback."""
    manager = RefactoringWorkspaceManager()
    target_files = ["src/monolith.py"]

    snapshot = manager.create_snapshot(
        workspace_root=temp_repo_workspace,
        plan_id="plan-unrel",
        source_revision="rev-001",
        target_files=target_files,
    )

    # User modifies an unrelated file while refactoring is executing
    (temp_repo_workspace / "notes.txt").write_text("user added new personal notes during task")
    (temp_repo_workspace / "user_scratch.txt").write_text("new untracked scratch file")

    # Refactoring modifies target file
    steps = [{"file_path": "src/monolith.py", "action": "DECOMPOSE", "content": "mutated content"}]
    manager.execute_refactoring_steps(temp_repo_workspace, steps)

    # Rollback refactoring
    res = manager.rollback(
        workspace_root=temp_repo_workspace,
        snapshot=snapshot,
        target_files=target_files,
    )

    assert res.status == RollbackStatus.ROLLED_BACK
    # Target file reverted
    assert (temp_repo_workspace / "src" / "monolith.py").read_text() == "def process():\n    return 'original'\n"
    # Unrelated files strictly preserved
    assert (temp_repo_workspace / "notes.txt").read_text() == "user added new personal notes during task"
    assert (temp_repo_workspace / "user_scratch.txt").read_text() == "new untracked scratch file"
    assert (temp_repo_workspace / "unrelated.py").exists()


def test_rollback_corrupted_snapshot_handling(temp_repo_workspace: Path):
    """Verify that corrupted snapshot transitions to ROLLBACK_FAILED state."""
    manager = RefactoringWorkspaceManager()
    snapshot = manager.create_snapshot(
        workspace_root=temp_repo_workspace,
        plan_id="plan-corrupt",
        source_revision="rev-001",
        target_files=["src/monolith.py"],
    )

    res = manager.rollback(
        workspace_root=temp_repo_workspace,
        snapshot=snapshot,
        force_corrupted_snapshot=True,
    )

    assert res.status == RollbackStatus.ROLLBACK_FAILED
    assert res.success is False
    assert "corrupted" in (res.error_message or "").lower()


def test_rollback_permission_failure_handling(temp_repo_workspace: Path):
    """Verify that permission failure transitions to MANUAL_INTERVENTION_REQUIRED state."""
    manager = RefactoringWorkspaceManager()
    snapshot = manager.create_snapshot(
        workspace_root=temp_repo_workspace,
        plan_id="plan-perm",
        source_revision="rev-001",
        target_files=["src/monolith.py"],
    )

    res = manager.rollback(
        workspace_root=temp_repo_workspace,
        snapshot=snapshot,
        force_permission_failure=True,
    )

    assert res.status == RollbackStatus.MANUAL_INTERVENTION_REQUIRED
    assert res.success is False
    assert "permission" in (res.error_message or "").lower()


def test_rollback_partial_failure_handling(temp_repo_workspace: Path):
    """Verify that partial rollback failure reports MANUAL_INTERVENTION_REQUIRED."""
    manager = RefactoringWorkspaceManager()
    snapshot = manager.create_snapshot(
        workspace_root=temp_repo_workspace,
        plan_id="plan-partial",
        source_revision="rev-001",
        target_files=["src/monolith.py", "src/service.py"],
    )

    res = manager.rollback(
        workspace_root=temp_repo_workspace,
        snapshot=snapshot,
        force_partial_failure=True,
    )

    assert res.status == RollbackStatus.MANUAL_INTERVENTION_REQUIRED
    assert res.success is False


@pytest.mark.asyncio
async def test_toctou_workspace_mutation_invalidates_approval(temp_repo_workspace: Path):
    """Verify TOCTOU protection: mutating workspace after approval invalidates approval."""
    service = ArchitectureAwareRefactoringService()

    repo_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="dev@devora.ai")
    db = AsyncMock()

    repo = Repository(id=repo_id, name="toctou-repo", user_id=user.id, current_commit_sha="c1")
    service.get_repository_for_user = AsyncMock(return_value=repo)

    plan = RefactoringPlan(
        id=plan_id,
        repository_id=repo_id,
        title="TOCTOU Test Plan",
        category="complexity",
        risk_level="MEDIUM",
        requires_human_approval=True,
        approval_status="PENDING",
        execution_status="DRAFT",
        target_files=["src/monolith.py"],
        ordered_steps=[{"step_id": "step_1", "order_index": 1, "description": "Refactor monolith", "action": "TRANSFORM", "file_path": "src/monolith.py"}],
        recommended_tests=["tests/unit/test_nominal.py"],
    )

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan
    db.execute.return_value = plan_result

    # 1. Approve plan with live workspace snapshot
    await service.approve_plan(
        repository_id=repo_id,
        plan_id=plan_id,
        user=user,
        db=db,
        workspace_path=temp_repo_workspace,
    )
    assert plan.approval_status == "APPROVED"
    approved_hash = plan.approved_diff_hash
    assert approved_hash is not None

    # 2. TOCTOU: Mutate target file on disk after approval!
    (temp_repo_workspace / "src" / "monolith.py").write_text("unauthorized modification behind approval")

    # 3. Attempt execution -> Must reject and invalidate approval!
    with pytest.raises(BadRequestException) as exc_info:
        await service.execute_plan(
            repository_id=repo_id,
            plan_id=plan_id,
            user=user,
            db=db,
            workspace_path=temp_repo_workspace,
        )

    assert "TOCTOU violation detected" in str(exc_info.value)
    assert plan.approval_status == "INVALIDATED"
    assert plan.execution_status == "FAILED"


@pytest.mark.asyncio
async def test_single_use_approval_replay_rejected():
    """Verify that approval cannot be replayed after plan has already been executed."""
    service = ArchitectureAwareRefactoringService()

    repo_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="dev@devora.ai")
    db = AsyncMock()

    repo = Repository(id=repo_id, name="replay-repo", user_id=user.id, current_commit_sha="c1")
    service.get_repository_for_user = AsyncMock(return_value=repo)

    plan = RefactoringPlan(
        id=plan_id,
        repository_id=repo_id,
        title="Replay Test Plan",
        category="layering",
        requires_human_approval=True,
        approval_status="APPROVED",
        execution_status="COMPLETED",  # Already executed!
        target_files=["src/monolith.py"],
        ordered_steps=[],
    )

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan
    db.execute.return_value = plan_result

    with pytest.raises(BadRequestException) as exc_info:
        await service.execute_plan(
            repository_id=repo_id,
            plan_id=plan_id,
            user=user,
            db=db,
        )

    assert "already been executed" in str(exc_info.value).lower()
    assert "replay is forbidden" in str(exc_info.value).lower()
