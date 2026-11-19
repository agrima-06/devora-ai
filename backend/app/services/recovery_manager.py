"""Workflow Recovery Manager: safe resumption, checkpoint restoration, and lease coordination."""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger
from app.models.task import Task
from app.models.workflow_checkpoint import WorkflowCheckpoint

logger = get_logger("workflow_recovery_manager")

# Regexes for scrubbing secrets prior to persistence
SECRET_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"x-access-token:[a-zA-Z0-9_\-]+@"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{30,100}"),
    re.compile(r"AIza[0-9A-Za-z-_]{30,45}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
]


def sanitize_state_blob(obj: Any) -> Any:
    """Recursively scrub secrets and ensure JSON serializability for persisted checkpoints."""
    if isinstance(obj, str):
        sanitized = obj
        for pattern in SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized
    elif isinstance(obj, dict):
        return {str(k): sanitize_state_blob(v) for k, v in obj.items() if not str(k).startswith("_")}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_state_blob(item) for item in obj]
    elif isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    elif hasattr(obj, "model_dump"):
        return sanitize_state_blob(obj.model_dump())
    elif hasattr(obj, "__dict__"):
        return sanitize_state_blob({k: v for k, v in obj.__dict__.items() if not k.startswith("_")})
    else:
        return str(obj)


class WorkflowRecoveryManager:
    """Manages workflow interruption detection, eligibility evaluation, leases, and checkpoint restoration."""

    def __init__(self):
        self.heartbeat_timeout = settings.RECOVERY_HEARTBEAT_TIMEOUT_SECONDS
        self.max_attempts = settings.RECOVERY_MAX_ATTEMPTS
        self.lease_duration = settings.RECOVERY_LEASE_DURATION_SECONDS

    def check_interruption(self, task: Task) -> Tuple[bool, Optional[str]]:
        """Determine whether a task was interrupted by evaluating heartbeats and status."""
        active_statuses = {"PLANNING", "IN_PROGRESS", "ANALYZING", "TESTING", "CODING", "EXECUTING"}
        now = datetime.now(timezone.utc)

        # Explicitly marked as interrupted
        if task.recovery_status == "INTERRUPTED":
            return True, task.recovery_error or "Task explicitly marked as INTERRUPTED"

        # Active status with missing or expired heartbeat
        if task.status in active_statuses:
            ref_time = task.last_heartbeat_at or task.updated_at
            if ref_time:
                # Ensure timezone awareness
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=timezone.utc)
                elapsed = (now - ref_time).total_seconds()
                if elapsed > self.heartbeat_timeout:
                    return (
                        True,
                        f"Heartbeat timeout expired ({int(elapsed)}s > {self.heartbeat_timeout}s) while status is {task.status}",
                    )
            else:
                return True, f"Task has status {task.status} with no recorded heartbeat or timestamp"

        # Unexpected termination with recovery status
        if task.status == "FAILED" and task.recovery_status in ("INTERRUPTED", "RESUMING"):
            return True, task.recovery_error or "Workflow terminated with unhandled exception"

        return False, None

    async def is_eligible_for_recovery(
        self,
        task: Task,
        db: AsyncSession,
        force: bool = False,
    ) -> Tuple[bool, str, Optional[WorkflowCheckpoint]]:
        """Evaluate if an interrupted task can be safely resumed from a checkpoint."""
        if not settings.RECOVERY_ENABLED:
            return False, "Workflow recovery system is disabled in server configuration", None

        # Terminal completed or cancelled tasks cannot be resumed
        if task.status in ("COMPLETED", "CANCELLED"):
            return False, f"Task is in terminal state '{task.status}' and cannot be resumed", None

        # Human approval pause is a safe intentional state, not an interruption
        if task.status == "WAITING_APPROVAL":
            return False, "Task is awaiting developer approval; submit approval action to proceed", None

        # Permanently failed tasks require force flag to retry
        if task.status == "FAILED" and not force:
            return False, "Task is marked as FAILED; pass force=True to override", None

        # Exceeded maximum recovery attempts
        if task.recovery_attempts >= self.max_attempts and not force:
            return (
                False,
                f"Maximum recovery attempts ({self.max_attempts}) reached for task; pass force=True to override",
                None,
            )

        # Check for active unexpired lease held by another worker
        now = datetime.now(timezone.utc)
        if task.recovery_lease_owner and task.recovery_lease_expires_at:
            lease_exp = task.recovery_lease_expires_at
            if lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)
            if lease_exp > now:
                return (
                    False,
                    f"Active recovery lease held by worker '{task.recovery_lease_owner}' until {lease_exp.isoformat()}",
                    None,
                )

        # Retrieve the latest checkpoint from PostgreSQL
        cp_stmt = (
            select(WorkflowCheckpoint)
            .where(WorkflowCheckpoint.task_id == task.id)
            .order_by(WorkflowCheckpoint.step_number.desc(), WorkflowCheckpoint.created_at.desc())
        )
        cp_res = await db.execute(cp_stmt)
        checkpoint = cp_res.scalars().first()

        if not checkpoint:
            return False, "No persisted workflow checkpoint found for task", None

        if not checkpoint.state_blob or not isinstance(checkpoint.state_blob, dict):
            return False, "Latest persisted checkpoint contains empty or corrupted state blob", None

        node_name = checkpoint.node_name or checkpoint.state_blob.get("current_agent", "orchestrator")
        return (
            True,
            f"Eligible to resume from checkpoint {checkpoint.checkpoint_id[:8]} (node '{node_name}', step {checkpoint.step_number})",
            checkpoint,
        )

    async def acquire_recovery_lease(
        self,
        task_id: uuid.UUID,
        worker_id: str,
        db: AsyncSession,
    ) -> bool:
        """Acquire an atomic row-level lease on the task record for resumption."""
        stmt = select(Task).where(Task.id == task_id).with_for_update()
        res = await db.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            raise NotFoundException("Task", task_id)

        now = datetime.now(timezone.utc)
        if task.recovery_lease_owner and task.recovery_lease_expires_at:
            lease_exp = task.recovery_lease_expires_at
            if lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)
            if lease_exp > now and task.recovery_lease_owner != worker_id:
                logger.warning(
                    "recovery_lease_conflict",
                    task_id=str(task_id),
                    held_by=task.recovery_lease_owner,
                    worker_id=worker_id,
                )
                return False

        task.recovery_lease_owner = worker_id
        task.recovery_lease_expires_at = now + timedelta(seconds=self.lease_duration)
        task.recovery_status = "RESUMING"
        task.recovery_attempts += 1
        task.last_heartbeat_at = now
        await db.flush()
        logger.info(
            "recovery_lease_acquired",
            task_id=str(task_id),
            worker_id=worker_id,
            attempt=task.recovery_attempts,
        )
        return True

    async def release_recovery_lease(
        self,
        task_id: uuid.UUID,
        db: AsyncSession,
        new_status: Optional[str] = None,
        recovery_error: Optional[str] = None,
    ) -> None:
        """Release the recovery lease and update the task recovery status."""
        stmt = select(Task).where(Task.id == task_id).with_for_update()
        res = await db.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            return

        task.recovery_lease_owner = None
        task.recovery_lease_expires_at = None
        if new_status:
            task.recovery_status = new_status
        if recovery_error is not None:
            task.recovery_error = recovery_error
        await db.flush()
        logger.info("recovery_lease_released", task_id=str(task_id), final_status=new_status)

    async def scan_and_flag_interrupted_tasks(
        self,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Identify interrupted workflows across active and flagged tasks."""
        stmt = (
            select(Task)
            .where(
                (Task.status.in_(["PLANNING", "IN_PROGRESS", "ANALYZING", "TESTING", "CODING", "EXECUTING"]))
                | (Task.recovery_status.in_(["INTERRUPTED", "RESUMING"]))
            )
            .order_by(Task.updated_at.desc())
        )
        res = await db.execute(stmt)
        tasks = res.scalars().all()

        interrupted_items: List[Dict[str, Any]] = []

        for t in tasks:
            is_int, reason = self.check_interruption(t)
            if is_int:
                if t.recovery_status != "INTERRUPTED" and t.status != "COMPLETED":
                    t.recovery_status = "INTERRUPTED"
                    t.recovery_error = reason

                eligible, elig_reason, cp = await self.is_eligible_for_recovery(t, db)
                interrupted_items.append({
                    "task_id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "recovery_status": t.recovery_status,
                    "interruption_reason": reason or "Interrupted",
                    "eligible": eligible,
                    "recovery_attempts": t.recovery_attempts,
                    "last_heartbeat_at": t.last_heartbeat_at,
                    "latest_node": cp.node_name if cp else None,
                })

        await db.flush()
        return interrupted_items
