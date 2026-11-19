"""Task creation and retrieval endpoints."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.events import WorkflowEventBroadcaster
from app.api.deps import get_current_user, get_db
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.agent_run import AgentRun
from app.models.approval import Approval
from app.models.file_change import FileChange
from app.models.project import Project
from app.models.report import Report
from app.models.repository import Repository
from app.models.task import Task
from app.models.test_run import TestRun
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.schemas.approval import ApprovalActionRequest, ApprovalResponse
from app.schemas.recovery import (
    CheckpointSummary,
    InterruptedTaskItem,
    InterruptedTaskScanResponse,
    TaskRecoveryStatusResponse,
    TaskResumeRequest,
    TaskResumeResponse,
)
from app.schemas.report import ReportResponse
from app.schemas.task import (
    AgentRunResponse,
    FileChangeResponse,
    StartWorkflowResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    TaskUpdate,
    TestRunResponse,
)
from app.services.recovery_manager import WorkflowRecoveryManager
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new engineering task",
)
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a new autonomous task targeted at a connected repository."""
    # Verify project exists and belongs to user
    project_result = await db.execute(
        select(Project).where(Project.id == payload.project_id, Project.owner_id == current_user.id)
    )
    if not project_result.scalar_one_or_none():
        raise NotFoundException("Project", payload.project_id)

    # Verify repository exists and belongs to user
    repo_result = await db.execute(
        select(Repository).where(
            Repository.id == payload.repository_id,
            Repository.project_id == payload.project_id,
            Repository.user_id == current_user.id,
        )
    )
    if not repo_result.scalar_one_or_none():
        raise NotFoundException("Repository", payload.repository_id)

    task = Task(
        project_id=payload.project_id,
        repository_id=payload.repository_id,
        created_by=current_user.id,
        title=payload.title,
        prompt=payload.prompt,
        error_traceback=payload.error_traceback,
        task_type=payload.task_type,
        status="PENDING",
        iterations_count=0,
        target_branch=payload.target_branch,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=List[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List engineering tasks",
)
async def list_tasks(
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
    repository_id: Optional[uuid.UUID] = Query(None, description="Filter by repository ID"),
    task_status: Optional[str] = Query(None, alias="status", description="Filter by task status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TaskResponse]:
    """List all tasks created by the authenticated user with optional filters."""
    query = select(Task).where(Task.created_by == current_user.id)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if repository_id:
        query = query.where(Task.repository_id == repository_id)
    if task_status:
        query = query.where(Task.status == task_status)
    query = query.order_by(Task.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve task details and execution plans",
)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskDetailResponse:
    """Retrieve full task details, including plans and metadata."""
    query = (
        select(Task)
        .options(selectinload(Task.plans))
        .where(Task.id == task_id, Task.created_by == current_user.id)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)
    return TaskDetailResponse.model_validate(task)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update task metadata",
)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Update task metadata."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    if payload.title is not None:
        task.title = payload.title
    if payload.status is not None:
        task.status = payload.status
    if payload.pull_request_url is not None:
        task.pull_request_url = payload.pull_request_url

    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/cancel",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a task",
)
async def cancel_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Cancel an active task."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    if task.status in ["COMPLETED", "CANCELLED"]:
        raise BadRequestException(f"Cannot cancel task in '{task.status}' state.")

    task.status = "CANCELLED"
    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/start",
    response_model=StartWorkflowResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start multi-agent engineering workflow",
)
async def start_workflow(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartWorkflowResponse:
    """Trigger the LangGraph 9-agent state machine for this task."""
    service = WorkflowService()
    res = await service.start_task_workflow(task_id, current_user, db)
    return StartWorkflowResponse(
        task_id=task_id,
        status=res.get("status", "IN_PROGRESS"),
        message=f"Workflow started. Current step: {res.get('current_step', 0)}",
    )


@router.get(
    "/{task_id}/events",
    summary="Subscribe to live workflow events stream (SSE)",
)
async def stream_workflow_events(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream real-time agent execution events and log output using Server-Sent Events."""
    # Verify task ownership
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    broadcaster = WorkflowEventBroadcaster.get_instance()
    return StreamingResponse(
        broadcaster.event_generator(str(task_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{task_id}/runs",
    response_model=List[AgentRunResponse],
    status_code=status.HTTP_200_OK,
    summary="List specialist agent execution history",
)
async def list_agent_runs(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AgentRunResponse]:
    """Retrieve full history of specialist agent executions for a task."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundException("Task", task_id)

    runs_stmt = (
        select(AgentRun)
        .where(AgentRun.task_id == task_id)
        .order_by(AgentRun.step_number.asc())
    )
    runs_res = await db.execute(runs_stmt)
    runs = runs_res.scalars().all()
    return [AgentRunResponse.model_validate(r) for r in runs]


@router.get(
    "/{task_id}/diff",
    response_model=List[FileChangeResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve proposed file modifications and unified diffs",
)
async def get_task_diff(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[FileChangeResponse]:
    """Retrieve code changes and unified diffs produced by Coding Agent."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundException("Task", task_id)

    changes_stmt = (
        select(FileChange)
        .where(FileChange.task_id == task_id)
        .order_by(FileChange.created_at.asc())
    )
    changes_res = await db.execute(changes_stmt)
    changes = changes_res.scalars().all()
    return [FileChangeResponse.model_validate(c) for c in changes]


@router.get(
    "/{task_id}/tests",
    response_model=List[TestRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve test execution results and telemetry",
)
async def get_task_test_runs(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TestRunResponse]:
    """Retrieve sandboxed test execution outputs and counts."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundException("Task", task_id)

    tests_stmt = (
        select(TestRun)
        .where(TestRun.task_id == task_id)
        .order_by(TestRun.iteration.asc())
    )
    tests_res = await db.execute(tests_stmt)
    tests = tests_res.scalars().all()
    return [TestRunResponse.model_validate(t) for t in tests]


@router.get(
    "/{task_id}/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve final engineering report",
)
async def get_task_report(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Retrieve audit-ready Markdown engineering report produced by Reporting Agent."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundException("Task", task_id)

    rep_stmt = (
        select(Report)
        .where(Report.task_id == task_id)
        .order_by(Report.created_at.desc())
    )
    rep_res = await db.execute(rep_stmt)
    report = rep_res.scalars().first()
    if not report:
        raise NotFoundException("Report for Task", task_id)

    return ReportResponse.model_validate(report)


@router.post(
    "/{task_id}/approval",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit human approval decision",
)
async def submit_task_approval(
    task_id: uuid.UUID,
    payload: ApprovalActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """Submit developer approval decision (APPROVE, REJECT, REQUEST_CHANGES) to resume or abort workflow."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    service = WorkflowService()
    await service.submit_approval_action(
        task_id=task_id,
        action=payload.action,
        user=current_user,
        db=db,
        notes=payload.notes,
    )

    # Return latest approval
    appr_stmt = (
        select(Approval)
        .where(Approval.task_id == task_id)
        .order_by(Approval.created_at.desc())
    )
    appr_res = await db.execute(appr_stmt)
    approval = appr_res.scalars().first()
    if not approval:
        raise NotFoundException("Approval record", task_id)

    return ApprovalResponse.model_validate(approval)


@router.post(
    "/recovery/scan",
    response_model=InterruptedTaskScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan and flag interrupted workflows",
)
async def scan_interrupted_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterruptedTaskScanResponse:
    """Scan active tasks for heartbeat timeouts or unhandled termination and flag for recovery."""
    manager = WorkflowRecoveryManager()
    items = await manager.scan_and_flag_interrupted_tasks(db)
    return InterruptedTaskScanResponse(
        scanned_tasks_count=len(items),
        interrupted_tasks=[InterruptedTaskItem(**i) for i in items],
    )


@router.get(
    "/{task_id}/recovery",
    response_model=TaskRecoveryStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get task workflow recovery status and eligibility",
)
async def get_task_recovery_status(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskRecoveryStatusResponse:
    """Evaluate whether an interrupted task can be safely resumed from its latest checkpoint."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    manager = WorkflowRecoveryManager()
    is_interrupted, interruption_reason = manager.check_interruption(task)
    eligible, elig_reason, checkpoint = await manager.is_eligible_for_recovery(task, db)

    cp_summary = None
    if checkpoint:
        cp_summary = CheckpointSummary(
            checkpoint_id=checkpoint.checkpoint_id,
            node_name=checkpoint.node_name,
            step_number=checkpoint.step_number,
            thread_id=checkpoint.thread_id,
            created_at=checkpoint.created_at,
        )

    return TaskRecoveryStatusResponse(
        task_id=str(task.id),
        status=task.status,
        recovery_status=task.recovery_status,
        is_interrupted=is_interrupted,
        interruption_reason=interruption_reason,
        is_eligible_for_recovery=eligible,
        eligibility_reason=elig_reason,
        recovery_attempts=task.recovery_attempts,
        max_recovery_attempts=manager.max_attempts,
        last_heartbeat_at=task.last_heartbeat_at,
        recovery_lease_owner=task.recovery_lease_owner,
        recovery_lease_expires_at=task.recovery_lease_expires_at,
        recovery_error=task.recovery_error,
        latest_checkpoint=cp_summary,
    )


@router.post(
    "/{task_id}/resume",
    response_model=TaskResumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Safely resume an interrupted task from last valid checkpoint",
)
async def resume_task(
    task_id: uuid.UUID,
    payload: Optional[TaskResumeRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResumeResponse:
    """Resume an interrupted task workflow from its last persisted database checkpoint."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException("Task", task_id)

    force_resume = payload.force if payload else False
    service = WorkflowService()
    res = await service.resume_task_workflow(
        task_id=task_id,
        user=current_user,
        db=db,
        force=force_resume,
    )

    return TaskResumeResponse(
        task_id=str(task.id),
        status=res["status"],
        recovery_status=res.get("recovery_status", "NOT_REQUIRED"),
        resumed_from_node=res.get("resumed_from_node", "orchestrator"),
        step_number=res.get("step_number", 0),
        recovery_attempts=res.get("recovery_attempts", 0),
        message=res.get("message", "Task successfully resumed"),
    )
