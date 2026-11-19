"""Unit tests for WorkflowRecoveryManager: interruption detection, eligibility evaluation,
checkpoint serialization, secret sanitization, and lease coordination (Phase 9 Stage 9.4).
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import settings
from app.models.task import Task
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.services.recovery_manager import (
    WorkflowRecoveryManager,
    sanitize_state_blob,
)


@pytest.fixture
def manager():
    return WorkflowRecoveryManager()


@pytest.fixture
def dummy_task():
    task = Task()
    task.id = uuid.uuid4()
    task.title = "Fix invoice calculation bug"
    task.prompt = "Division by zero on empty cart"
    task.task_type = "bug_fix"
    task.status = "IN_PROGRESS"
    task.recovery_status = "NOT_REQUIRED"
    task.recovery_attempts = 0
    task.last_heartbeat_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    task.recovery_lease_owner = None
    task.recovery_lease_expires_at = None
    task.recovery_error = None
    return task


# ---------------------------------------------------------------------------
# 1. Secret Sanitization & Serialization Tests
# ---------------------------------------------------------------------------


def test_sanitize_state_blob_masks_github_tokens():
    raw = {
        "token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        "remote_url": "https://x-access-token:ghp_1234567890abcdefghijklmnopqrstuvwxyz@github.com/org/repo.git",
        "nested": {
            "api_key": "AIzaSyD-1234567890abcdefghijklmnopqr",
            "auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig",
        },
    }
    sanitized = sanitize_state_blob(raw)

    assert "[REDACTED]" in sanitized["token"]
    assert "ghp_" not in sanitized["token"]
    assert "[REDACTED]@" in sanitized["remote_url"]
    assert "x-access-token:" in sanitized["remote_url"]
    assert "[REDACTED]" in sanitized["nested"]["api_key"]
    assert "AIza" not in sanitized["nested"]["api_key"]
    assert "[REDACTED]" in sanitized["nested"]["auth"]


def test_sanitize_state_blob_handles_complex_types():
    data = {
        "step": 3,
        "active": True,
        "tags": ["fix", "ml"],
        "none_val": None,
        "custom": 12.5,
    }
    res = sanitize_state_blob(data)
    assert res["step"] == 3
    assert res["active"] is True
    assert res["tags"] == ["fix", "ml"]
    assert res["none_val"] is None
    assert res["custom"] == 12.5


# ---------------------------------------------------------------------------
# 2. Interruption Detection Tests
# ---------------------------------------------------------------------------


def test_check_interruption_active_fresh_heartbeat(manager: WorkflowRecoveryManager, dummy_task: Task):
    dummy_task.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=15)
    is_int, reason = manager.check_interruption(dummy_task)
    assert is_int is False
    assert reason is None


def test_check_interruption_active_expired_heartbeat(manager: WorkflowRecoveryManager, dummy_task: Task):
    # Set heartbeat older than timeout (120s)
    dummy_task.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=150)
    is_int, reason = manager.check_interruption(dummy_task)
    assert is_int is True
    assert "Heartbeat timeout expired" in reason
    assert "IN_PROGRESS" in reason


def test_check_interruption_explicitly_flagged(manager: WorkflowRecoveryManager, dummy_task: Task):
    dummy_task.recovery_status = "INTERRUPTED"
    dummy_task.recovery_error = "Server node killed unexpectedly"
    is_int, reason = manager.check_interruption(dummy_task)
    assert is_int is True
    assert "Server node killed unexpectedly" in reason


def test_check_interruption_terminal_completed(manager: WorkflowRecoveryManager, dummy_task: Task):
    dummy_task.status = "COMPLETED"
    dummy_task.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=10)
    is_int, reason = manager.check_interruption(dummy_task)
    assert is_int is False
    assert reason is None


# ---------------------------------------------------------------------------
# 3. Resumption Eligibility Matrix Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eligibility_disabled_setting(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    with patch.object(settings, "RECOVERY_ENABLED", False):
        eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db)
        assert eligible is False
        assert "disabled in server configuration" in reason
        assert cp is None


@pytest.mark.asyncio
async def test_eligibility_terminal_states(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    for terminal in ("COMPLETED", "CANCELLED"):
        dummy_task.status = terminal
        eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db)
        assert eligible is False
        assert f"terminal state '{terminal}'" in reason
        assert cp is None


@pytest.mark.asyncio
async def test_eligibility_waiting_approval_must_use_approval_flow(
    manager: WorkflowRecoveryManager, dummy_task: Task
):
    mock_db = AsyncMock()
    dummy_task.status = "WAITING_APPROVAL"
    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db)
    assert eligible is False
    assert "awaiting developer approval" in reason
    assert cp is None


@pytest.mark.asyncio
async def test_eligibility_failed_status_handling(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    dummy_task.status = "FAILED"

    # Without force -> not eligible
    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db, force=False)
    assert eligible is False
    assert "pass force=True to override" in reason

    # With force, but no checkpoint -> not eligible due to missing checkpoint
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db.execute.return_value = mock_result

    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db, force=True)
    assert eligible is False
    assert "No persisted workflow checkpoint" in reason


@pytest.mark.asyncio
async def test_eligibility_max_recovery_attempts(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    dummy_task.recovery_attempts = 3

    # Without force -> not eligible
    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db, force=False)
    assert eligible is False
    assert "Maximum recovery attempts" in reason

    # With force, but no checkpoint -> bypasses attempts check, proceeds to checkpoint lookup
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db.execute.return_value = mock_result

    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db, force=True)
    assert eligible is False
    assert "No persisted workflow checkpoint" in reason


@pytest.mark.asyncio
async def test_eligibility_active_lease_conflict(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    dummy_task.recovery_lease_owner = "worker-remote-123"
    dummy_task.recovery_lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=4)

    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db)
    assert eligible is False
    assert "Active recovery lease held by worker 'worker-remote-123'" in reason


@pytest.mark.asyncio
async def test_eligibility_successful_with_checkpoint(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    mock_checkpoint = WorkflowCheckpoint(
        task_id=dummy_task.id,
        thread_id=str(dummy_task.id),
        checkpoint_ns="",
        checkpoint_id="cp-abc12345",
        node_name="coder",
        step_number=5,
        version=1,
        state_blob={"task_id": str(dummy_task.id), "current_agent": "coder"},
    )
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = mock_checkpoint
    mock_db.execute.return_value = mock_result

    eligible, reason, cp = await manager.is_eligible_for_recovery(dummy_task, mock_db)
    assert eligible is True
    assert "Eligible to resume from checkpoint" in reason
    assert "coder" in reason
    assert cp == mock_checkpoint


# ---------------------------------------------------------------------------
# 4. Lease Management Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_and_release_recovery_lease(manager: WorkflowRecoveryManager, dummy_task: Task):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = dummy_task
    mock_db.execute.return_value = mock_result

    # 1. Acquire lease
    worker_id = "worker-proc-99"
    acquired = await manager.acquire_recovery_lease(dummy_task.id, worker_id, mock_db)
    assert acquired is True
    assert dummy_task.recovery_lease_owner == worker_id
    assert dummy_task.recovery_status == "RESUMING"
    assert dummy_task.recovery_attempts == 1
    assert dummy_task.recovery_lease_expires_at is not None

    # 2. Second worker attempts acquisition -> conflict
    acquired_second = await manager.acquire_recovery_lease(dummy_task.id, "worker-proc-100", mock_db)
    assert acquired_second is False

    # 3. Release lease
    await manager.release_recovery_lease(dummy_task.id, mock_db, new_status="RECOVERED")
    assert dummy_task.recovery_lease_owner is None
    assert dummy_task.recovery_lease_expires_at is None
    assert dummy_task.recovery_status == "RECOVERED"
