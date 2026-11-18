"""Workflow Execution Service: coordinates LangGraph execution, database persistence, and SSE event broadcast."""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.events import WorkflowEventBroadcaster
from app.agents.graph import create_workflow_graph
from app.agents.state import DevoraWorkflowState
from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger
from app.models.agent_run import AgentRun
from app.models.approval import Approval
from app.models.file_change import FileChange
from app.models.report import Report
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_plan import TaskPlan
from app.models.test_run import TestRun
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.services.sandbox_service import SandboxService
from app.services.search_service import CodeSearchService

logger = get_logger("workflow_service")


class WorkflowService:
    """Service orchestrating end-to-end multi-agent execution, checkpointing, and audit persistence."""

    _shared_checkpointer: BaseCheckpointSaver = MemorySaver()

    def __init__(
        self,
        broadcaster: Optional[WorkflowEventBroadcaster] = None,
        sandbox: Optional[SandboxService] = None,
        search_service: Optional[CodeSearchService] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        self.broadcaster = broadcaster or WorkflowEventBroadcaster.get_instance()
        self.sandbox = sandbox or SandboxService()
        self.search_service = search_service or CodeSearchService()
        self.checkpointer = checkpointer or self._shared_checkpointer
        # Compile graph with human approval interrupt
        self.graph = create_workflow_graph(checkpointer=self.checkpointer, interrupt_on_approval=True)

    async def start_task_workflow(
        self,
        task_id: uuid.UUID,
        user: User,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Initiate or resume multi-agent engineering workflow for a task."""
        # 1. Fetch Task and Repository with tenant verification
        stmt = (
            select(Task)
            .where(Task.id == task_id)
        )
        task_res = await db.execute(stmt)
        task = task_res.scalar_one_or_none()
        if not task:
            raise NotFoundException("Task", task_id)

        repo_res = await db.execute(
            select(Repository).where(Repository.id == task.repository_id, Repository.user_id == user.id)
        )
        repo = repo_res.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", task.repository_id)

        # 2. Prepare ephemeral task workspace
        repo_workspace = Path(settings.WORKSPACE_BASE_DIR) / str(repo.id)
        task_workspace = self.sandbox.prepare_workspace(str(task.id), repo_workspace)

        # 3. Retrieve preliminary code context and symbols
        arch_data = await self.search_service.get_architecture_summary(repo.id, user, db)
        files = await self.search_service.list_files(repo.id, user, db)
        symbols = await self.search_service.list_symbols(repo.id, user, db)

        # 4. Construct initial strongly typed state
        initial_state: DevoraWorkflowState = {
            "task_id": str(task.id),
            "user_id": str(user.id),
            "repository_id": str(repo.id),
            "workspace_path": str(task_workspace),
            "commit_sha": repo.current_commit_sha or "0000000",
            "target_branch": task.target_branch,
            "task_description": f"{task.title}\n{task.prompt}",
            "task_type": task.task_type,
            "error_traceback": task.error_traceback,
            "repository_context": arch_data,
            "retrieved_files": [{"file_path": f.file_path, "summary": f.summary} for f in files[:20]],
            "retrieved_symbols": symbols[:30],
            "retry_count": 0,
            "maximum_retries": 3,
            "execution_status": "PLANNING",
            "current_agent": "orchestrator",
            "agent_execution_history": [],
            "proposed_file_changes": [],
            "applied_file_changes": [],
            "git_diff": "",
            "errors": [],
        }

        task.status = "PLANNING"
        await db.flush()

        await self.broadcaster.emit(
            task_id=str(task.id),
            event_type="WORKFLOW_STARTED",
            agent_name="orchestrator",
            message=f"Starting autonomous workflow for task: {task.title}",
            payload={"task_type": task.task_type},
            db=db,
        )

        # 5. Execute LangGraph state machine with thread configuration
        config = {"configurable": {"thread_id": str(task.id)}}
        step_index = 0

        try:
            async for event in self.graph.astream(initial_state, config=config):
                for node_name, node_output in event.items():
                    step_index += 1
                    logger.info("agent_node_executed", node=node_name, step=step_index)

                    # Broadcast node completion event
                    await self.broadcaster.emit(
                        task_id=str(task.id),
                        event_type=f"AGENT_{node_name.upper()}_COMPLETED",
                        agent_name=node_name,
                        message=f"Specialist Agent '{node_name}' finished execution step.",
                        payload=node_output,
                        db=db,
                    )

                    # Persist AgentRun record
                    agent_run = AgentRun(
                        task_id=task.id,
                        agent_name=node_name,
                        step_number=step_index,
                        input_state={},
                        output_state=node_output if isinstance(node_output, dict) else {},
                        duration_ms=500,
                    )
                    db.add(agent_run)

                    # Save domain entities based on node outputs
                    if node_name == "planner" and "implementation_plan" in node_output:
                        plan_data = node_output["implementation_plan"]
                        task_plan = TaskPlan(
                            task_id=task.id,
                            steps=plan_data.get("steps", []),
                            test_criteria=plan_data.get("test_criteria", []),
                            risk_level=plan_data.get("risk_level", "MEDIUM"),
                        )
                        db.add(task_plan)
                        task.status = "IN_PROGRESS"

                    if node_name == "coder" and "applied_file_changes" in node_output:
                        for mod in node_output["applied_file_changes"]:
                            fc = FileChange(
                                task_id=task.id,
                                file_path=mod["file_path"],
                                change_type=mod.get("change_type", "modified"),
                                original_content=mod.get("original_content"),
                                new_content=mod.get("new_content"),
                                diff=mod.get("diff", ""),
                            )
                            db.add(fc)

                    if node_name == "tester" and "test_results" in node_output:
                        tr_data = node_output["test_results"]
                        test_run = TestRun(
                            task_id=task.id,
                            iteration=task.iterations_count + 1,
                            command=tr_data.get("command", "pytest"),
                            exit_code=tr_data.get("exit_code", 0),
                            passed=tr_data.get("passed", False),
                            total_tests=tr_data.get("total_tests", 0),
                            passed_tests=tr_data.get("passed_tests", 0),
                            failed_tests=tr_data.get("failed_tests", 0),
                            stdout=tr_data.get("raw_stdout"),
                            stderr=tr_data.get("raw_stderr"),
                            duration_seconds=tr_data.get("duration_seconds", 0.0),
                        )
                        db.add(test_run)
                        task.iterations_count += 1

                    if node_name == "reporter" and "final_report" in node_output:
                        rep_data = node_output["final_report"]
                        report_rec = Report(
                            task_id=task.id,
                            title=rep_data.get("title", task.title),
                            summary=rep_data.get("summary", ""),
                            root_cause_analysis=rep_data.get("root_cause_analysis", ""),
                            test_summary=node_output.get("test_results") or {},
                            markdown_content=rep_data.get("markdown_report", ""),
                        )
                        db.add(report_rec)

            await db.flush()

            # 6. Check state snapshot to see if paused for human approval
            state_snap = self.graph.get_state(config)
            if state_snap and state_snap.values:
                cp_id = str(state_snap.config.get("configurable", {}).get("checkpoint_id", uuid.uuid4().hex))
                cp_ns = str(state_snap.config.get("configurable", {}).get("checkpoint_ns", ""))
                blob = json.loads(json.dumps(dict(state_snap.values), default=str))
                db_cp = WorkflowCheckpoint(
                    task_id=task.id,
                    thread_id=str(task.id),
                    checkpoint_ns=cp_ns,
                    checkpoint_id=cp_id,
                    state_blob=blob,
                )
                db.add(db_cp)
                await db.flush()

            if state_snap.next and "human_approval" in state_snap.next:
                task.status = "WAITING_APPROVAL"
                # Create Approval record
                approval_rec = Approval(
                    task_id=task.id,
                    requested_by=user.id,
                    status="PENDING",
                    notes="Awaiting human approval before publishing proposed code changes.",
                )
                db.add(approval_rec)
                await db.flush()

                await self.broadcaster.emit(
                    task_id=str(task.id),
                    event_type="APPROVAL_REQUIRED",
                    agent_name="orchestrator",
                    message="Proposed modifications require developer approval before publishing.",
                    payload={"approval_id": str(approval_rec.id)},
                    db=db,
                )
            else:
                final_val = state_snap.values
                final_status = final_val.get("execution_status", "COMPLETED")
                task.status = final_status if final_status in ("COMPLETED", "FAILED") else "COMPLETED"
                await db.flush()

                await self.broadcaster.emit(
                    task_id=str(task.id),
                    event_type=task.status,
                    agent_name="orchestrator",
                    message=f"Task workflow finished with status: {task.status}",
                    payload={},
                    db=db,
                )

            return {
                "task_id": str(task.id),
                "status": task.status,
                "current_step": step_index,
                "next_node": list(state_snap.next) if state_snap.next else [],
            }

        except Exception as exc:
            logger.error("workflow_execution_failed", task_id=str(task.id), error=str(exc))
            task.status = "FAILED"
            await db.flush()
            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="FAILED",
                agent_name="orchestrator",
                message=f"Workflow failed: {str(exc)}",
                payload={"error": str(exc)},
                db=db,
            )
            raise BadRequestException(f"Workflow execution failed: {str(exc)}")

    async def submit_approval_action(
        self,
        task_id: uuid.UUID,
        action: str,  # "approve", "reject", "request_changes"
        user: User,
        db: AsyncSession,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process developer approval decision and resume or terminate workflow."""
        stmt = select(Task).where(Task.id == task_id)
        task_res = await db.execute(stmt)
        task = task_res.scalar_one_or_none()
        if not task:
            raise NotFoundException("Task", task_id)

        # Find pending approval
        appr_stmt = (
            select(Approval)
            .where(Approval.task_id == task.id, Approval.status == "PENDING")
            .order_by(Approval.created_at.desc())
        )
        appr_res = await db.execute(appr_stmt)
        approval = appr_res.scalars().first()
        if not approval:
            raise BadRequestException(f"Task is in '{task.status}' state and has no pending approvals awaiting action.")

        config = {"configurable": {"thread_id": str(task.id)}}

        if action.lower() == "approve":
            if approval:
                approval.status = "APPROVED"
                approval.reviewed_by = user.id
                approval.responded_at = datetime.now(timezone.utc)
                approval.notes = notes

            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="APPROVED",
                agent_name="human_approval",
                message="Developer approved changes. Finalizing engineering report and completing task.",
                payload={"notes": notes},
                db=db,
            )

            # If server restarted or memory checkpoint lost, restore state from PostgreSQL workflow_checkpoints
            state_snap = self.graph.get_state(config)
            if not state_snap.values or not state_snap.next:
                cp_stmt = (
                    select(WorkflowCheckpoint)
                    .where(WorkflowCheckpoint.task_id == task.id)
                    .order_by(WorkflowCheckpoint.created_at.desc())
                )
                cp_res = await db.execute(cp_stmt)
                saved_cp = cp_res.scalars().first()
                if saved_cp and saved_cp.state_blob:
                    logger.info("recovering_workflow_from_database_checkpoint", task_id=str(task.id))
                    self.graph.update_state(config, saved_cp.state_blob, as_node="security_reviewer")

            # Resume LangGraph execution from checkpoint
            async for event in self.graph.astream(None, config=config):
                for node_name, node_output in event.items():
                    if node_name == "reporter" and "final_report" in node_output:
                        rep_data = node_output["final_report"]
                        report_rec = Report(
                            task_id=task.id,
                            title=rep_data.get("title", task.title),
                            summary=rep_data.get("summary", ""),
                            root_cause_analysis=rep_data.get("root_cause_analysis", ""),
                            test_summary={},
                            markdown_content=rep_data.get("markdown_report", ""),
                        )
                        db.add(report_rec)

            final_snap = self.graph.get_state(config)
            if final_snap and final_snap.values:
                cp_id = str(final_snap.config.get("configurable", {}).get("checkpoint_id", uuid.uuid4().hex))
                blob = json.loads(json.dumps(dict(final_snap.values), default=str))
                final_cp = WorkflowCheckpoint(
                    task_id=task.id,
                    thread_id=str(task.id),
                    checkpoint_ns="",
                    checkpoint_id=cp_id,
                    state_blob=blob,
                )
                db.add(final_cp)

            task.status = "COMPLETED"
            await db.flush()

            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="COMPLETED",
                agent_name="orchestrator",
                message="Task completed successfully.",
                payload={},
                db=db,
            )
            return {"status": "COMPLETED", "message": "Changes approved and task completed."}

        else:
            # Rejection or Request Changes
            new_status = "REJECTED" if action.lower() == "reject" else "CHANGES_REQUESTED"
            if approval:
                approval.status = new_status
                approval.reviewed_by = user.id
                approval.responded_at = datetime.now(timezone.utc)
                approval.notes = notes

            task.status = "CANCELLED" if new_status == "REJECTED" else "WAITING_APPROVAL"
            await db.flush()

            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type=new_status,
                agent_name="human_approval",
                message=f"Developer marked task as {new_status}.",
                payload={"notes": notes},
                db=db,
            )
            return {"status": task.status, "message": f"Changes {new_status.lower()}."}
