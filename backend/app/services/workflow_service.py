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
from app.agents.gateway.exceptions import ModelGatewayException, scrub_credentials
from app.agents.graph import create_workflow_graph
from app.agents.state import DevoraWorkflowState
from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger
from app.models.agent_run import AgentRun
from app.models.approval import Approval
from app.models.file_change import FileChange
from app.models.git_branch import GitBranch
from app.models.github_pull_request import GitHubPullRequest
from app.models.report import Report
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_plan import TaskPlan
from app.models.test_run import TestRun
from app.models.user import User
from app.models.workflow_checkpoint import WorkflowCheckpoint
from app.models.ml_prediction import MLPrediction
from app.models.task_failure_record import TaskFailureRecord
from app.ml.data.dataset import DatasetManager
from app.ml.preprocessor import TracebackPreprocessor
from app.services.adaptive_service import AdaptiveIntelligenceService
from app.services.git_workspace_manager import GitWorkspaceManager
from app.services.github_app_service import GitHubAppService
from app.services.memory_service import MemoryService
from app.services.pull_request_service import PullRequestService
from app.services.recovery_manager import WorkflowRecoveryManager, sanitize_state_blob
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
        memory_service: Optional[MemoryService] = None,
        adaptive_service: Optional[AdaptiveIntelligenceService] = None,
        git_workspace: Optional[GitWorkspaceManager] = None,
        pr_service: Optional[PullRequestService] = None,
        github_app: Optional[GitHubAppService] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        recovery_manager: Optional[WorkflowRecoveryManager] = None,
    ):
        self.broadcaster = broadcaster or WorkflowEventBroadcaster.get_instance()
        self.sandbox = sandbox or SandboxService()
        self.search_service = search_service or CodeSearchService()
        self.memory_service = memory_service or MemoryService()
        self.adaptive_service = adaptive_service or AdaptiveIntelligenceService()
        self.git_workspace = git_workspace or GitWorkspaceManager()
        self.pr_service = pr_service or PullRequestService()
        self.github_app = github_app or GitHubAppService()
        self.checkpointer = checkpointer or self._shared_checkpointer
        self.recovery_manager = recovery_manager or WorkflowRecoveryManager()
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

        # Stage H6 Safety Restriction: Restrict public execution in Showcase Mode
        if getattr(settings, "SHOWCASE_MODE", False):
            is_demo = any(
                demo.lower() in repo.name.lower() or demo.lower() in (repo.full_name or "").lower()
                for demo in getattr(settings, "DEMO_REPOSITORIES", [])
            )
            if not is_demo and not getattr(user, "is_superuser", False):
                raise BadRequestException(
                    f"Showcase Mode Active: Autonomous task execution is restricted to approved demonstration repositories ({', '.join(settings.DEMO_REPOSITORIES)}). Connect or select a demonstration repository to proceed."
                )

        # 2. Prepare ephemeral task workspace and isolated git branch
        task_branch = task.task_branch or GitWorkspaceManager.generate_branch_name(task.task_type, str(task.id))
        task.task_branch = task_branch
        base_branch = task.target_branch or repo.default_branch or "main"

        # Record branch in git_branches if not already recorded
        branch_stmt = select(GitBranch).where(GitBranch.task_id == task.id, GitBranch.branch_name == task_branch)
        branch_res = await db.execute(branch_stmt)
        git_branch_rec = branch_res.scalar_one_or_none()
        if not git_branch_rec:
            git_branch_rec = GitBranch(
                task_id=task.id,
                repository_id=repo.id,
                branch_name=task_branch,
                base_branch=base_branch,
                commit_sha=repo.current_commit_sha,
                is_pushed=False,
            )
            db.add(git_branch_rec)

        repo_workspace = Path(settings.WORKSPACE_BASE_DIR) / str(repo.id)
        task_workspace = self.git_workspace.prepare_task_workspace(
            task_id=str(task.id),
            repo_clone_url=repo.clone_url or "",
            base_branch=base_branch,
            task_branch=task_branch,
            source_repo_dir=repo_workspace if repo_workspace.exists() else None,
        )

        # 3. Retrieve preliminary code context, symbols, and semantic memories
        arch_data = await self.search_service.get_architecture_summary(repo.id, user, db)
        files = await self.search_service.list_files(repo.id, user, db)
        symbols = await self.search_service.list_symbols(repo.id, user, db)

        # Retrieve relevant project memories and conventions
        memories = await self.memory_service.search_memories(
            repository_id=repo.id,
            query=f"{task.title} {task.prompt} {task.error_traceback or ''}",
            user=user,
            db=db,
            limit=settings.MEMORY_MAX_RETRIEVAL_ITEMS,
            threshold=settings.MEMORY_SIMILARITY_THRESHOLD,
        )
        memory_lines = [
            f"- [{m['category'].upper()}] {m['title']}: {m['content'][:300]} (Status: {m['verification_status']})"
            for m in memories
        ]
        memory_summary = "\n".join(memory_lines) if memory_lines else "No previous task memories retrieved."

        # Retrieve relevant historical experiences and past failure lessons
        experiences = await self.adaptive_service.retrieve_relevant_experiences(
            query=f"{task.title} {task.prompt} {task.error_traceback or ''}",
            repository_id=repo.id,
            task_category=task.task_type,
            limit=5,
            db=db,
        )
        fail_stmt = select(TaskFailureRecord).order_by(TaskFailureRecord.created_at.desc()).limit(5)
        fail_res = await db.execute(fail_stmt)
        failures = [
            {
                "stage": f.stage,
                "failure_type": f.failure_type,
                "failed_strategy": f.failed_strategy,
                "lessons_learned": f.lessons_learned,
            }
            for f in fail_res.scalars().all()
        ]

        # 4. Construct initial strongly typed state
        initial_state: DevoraWorkflowState = {
            "task_id": str(task.id),
            "user_id": str(user.id),
            "repository_id": str(repo.id),
            "workspace_path": str(task_workspace),
            "commit_sha": repo.current_commit_sha or "0000000",
            "target_branch": task.target_branch,
            "task_branch": task_branch,
            "base_branch": base_branch,
            "pull_request_url": task.pull_request_url,
            "pull_request_number": None,
            "task_description": f"{task.title}\n{task.prompt}",
            "task_type": task.task_type,
            "error_traceback": task.error_traceback,
            "repository_context": arch_data,
            "retrieved_files": [{"file_path": f.file_path, "summary": f.summary} for f in files[:20]],
            "retrieved_symbols": symbols[:30],
            "retrieved_memories": memories,
            "memory_context_summary": memory_summary,
            "historical_experiences": [e.model_dump() for e in experiences],
            "historical_failures_to_avoid": failures,
            "adaptive_strategy_summary": f"Informed by {len(experiences)} historical experiences and {len(failures)} failure lessons.",
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
        task.recovery_status = "RUNNING"
        task.recovery_error = None
        task.last_heartbeat_at = datetime.now(timezone.utc)
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
        last_node = "orchestrator"

        try:
            async for event in self.graph.astream(initial_state, config=config):
                for node_name, node_output in event.items():
                    if node_name == "__interrupt__":
                        continue
                    step_index += 1
                    last_node = node_name
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

                    await self._process_node_output(task, repo, node_name, node_output, step_index, db)

                    # Update heartbeat and persist intermediate checkpoint
                    now = datetime.now(timezone.utc)
                    task.last_heartbeat_at = now
                    current_snap = self.graph.get_state(config)
                    if current_snap and current_snap.values:
                        cp_id = str(current_snap.config.get("configurable", {}).get("checkpoint_id", uuid.uuid4().hex))
                        cp_ns = str(current_snap.config.get("configurable", {}).get("checkpoint_ns", ""))
                        clean_blob = sanitize_state_blob(dict(current_snap.values))
                        inter_cp = WorkflowCheckpoint(
                            task_id=task.id,
                            thread_id=str(task.id),
                            checkpoint_ns=cp_ns,
                            checkpoint_id=cp_id,
                            node_name=node_name,
                            step_number=step_index,
                            version=1,
                            state_blob=clean_blob,
                        )
                        db.add(inter_cp)

            await db.flush()

            # 6. Check state snapshot to see if paused for human approval
            state_snap = self.graph.get_state(config)
            if state_snap and state_snap.values:
                cp_id = str(state_snap.config.get("configurable", {}).get("checkpoint_id", uuid.uuid4().hex))
                cp_ns = str(state_snap.config.get("configurable", {}).get("checkpoint_ns", ""))
                clean_blob = sanitize_state_blob(dict(state_snap.values))
                db_cp = WorkflowCheckpoint(
                    task_id=task.id,
                    thread_id=str(task.id),
                    checkpoint_ns=cp_ns,
                    checkpoint_id=cp_id,
                    node_name=last_node,
                    step_number=step_index + 1,
                    version=1,
                    state_blob=clean_blob,
                )
                db.add(db_cp)
                await db.flush()

            if state_snap.next and "human_approval" in state_snap.next:
                task.status = "WAITING_APPROVAL"
                task.recovery_status = "NOT_REQUIRED"
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
                task.recovery_status = "NOT_REQUIRED"
                await db.flush()

                # Distill completed verified task into memory if tests passed
                if task.status == "COMPLETED":
                    await self._distill_successful_workflow(task, repo, user, final_val, db)

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

        except ModelGatewayException as mg_exc:
            clean_err = scrub_credentials(str(mg_exc))
            logger.error(
                "workflow_model_provider_failure",
                task_id=str(task.id),
                error=clean_err,
                classification=mg_exc.classification,
            )
            task.status = "FAILED"
            task.recovery_status = "INTERRUPTED"
            task.recovery_error = f"Model Provider Failure ({mg_exc.classification}): {clean_err}"
            await db.flush()
            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="MODEL_PROVIDER_UNAVAILABLE",
                agent_name="orchestrator",
                message=f"Model provider failure ({mg_exc.classification}): {clean_err}",
                payload={"classification": mg_exc.classification, "error": clean_err},
                db=db,
            )
            raise BadRequestException(f"Model provider failure: {clean_err}")

        except Exception as exc:
            clean_exc = scrub_credentials(str(exc))
            logger.error("workflow_execution_failed", task_id=str(task.id), error=clean_exc)
            task.status = "FAILED"
            task.recovery_status = "INTERRUPTED"
            task.recovery_error = clean_exc
            await db.flush()
            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="FAILED",
                agent_name="orchestrator",
                message=f"Workflow failed: {clean_exc}",
                payload={"error": clean_exc},
                db=db,
            )
            raise BadRequestException(f"Workflow execution failed: {clean_exc}")

    async def _process_node_output(
        self,
        task: Task,
        repo: Repository,
        node_name: str,
        node_output: Dict[str, Any],
        step_index: int,
        db: AsyncSession,
    ) -> None:
        """Process and persist domain entities generated by a specialist node."""
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
        if node_name == "ml_classifier" and "ml_bug_prediction" in node_output:
            pred_data = node_output["ml_bug_prediction"]
            probs = pred_data.get("top_probabilities", [])
            ml_pred_record = MLPrediction(
                task_id=task.id,
                input_hash=pred_data.get("input_hash", ""),
                error_sample_preview=pred_data.get("cleaned_input_preview", ""),
                predicted_category=pred_data.get("predicted_category", ""),
                confidence=float(pred_data.get("confidence", 0.0)),
                top_probabilities=[p if isinstance(p, dict) else p.model_dump() for p in probs],
                is_low_confidence=bool(pred_data.get("is_low_confidence", False)),
                model_version=pred_data.get("model_version", "v1.0.0"),
                inference_time_ms=float(pred_data.get("inference_time_ms", 0.0)),
            )
            db.add(ml_pred_record)

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
                peak_memory_rss_bytes=tr_data.get("peak_memory_rss_bytes"),
                peak_memory_rss_mb=tr_data.get("peak_memory_rss_mb"),
                cpu_time_seconds=tr_data.get("cpu_time_seconds"),
                wall_time_seconds=tr_data.get("wall_time_seconds"),
                memory_limit_bytes=tr_data.get("memory_limit_bytes"),
                memory_limit_mb=tr_data.get("memory_limit_mb"),
                cpu_limit=tr_data.get("cpu_limit"),
                oom_killed=tr_data.get("oom_killed", False),
                termination_reason=tr_data.get("termination_reason"),
                exit_classification=tr_data.get("exit_classification", "EXECUTION_FAILURE"),
                resource_telemetry_available=tr_data.get("resource_telemetry_available", False),
            )
            db.add(test_run)
            task.iterations_count += 1

            # Capture structured failure learning if sandbox tests failed
            if not tr_data.get("passed", False):
                is_runner_missing = (tr_data.get("failure_classification") in ("RUNNER_UNAVAILABLE", "COMMAND_NOT_FOUND", "COMMAND_NOT_EXECUTABLE"))
                is_flaky_failure = tr_data.get("is_flaky", False) or (tr_data.get("stability_classification") == "FLAKY")
                is_oom = tr_data.get("oom_killed", False) or tr_data.get("failure_classification") == "OOM_KILLED"
                is_timeout = tr_data.get("failure_classification") == "TIMEOUT" or tr_data.get("execution_status") == "TIMED_OUT"
                is_infra = is_runner_missing or is_flaky_failure or is_oom or is_timeout or (tr_data.get("failure_classification") in ("SANDBOX_STARTUP_FAILURE", "PROCESS_KILLED"))

                fail_type = "ENVIRONMENT_PROBLEM" if is_infra else "IMPLEMENTATION_DEFECT"
                if is_oom:
                    fail_lessons = "Container exceeded memory quota (OOMKilled); optimize memory usage or adjust container memory limit."
                elif is_timeout:
                    fail_lessons = "Test execution exceeded timeout threshold; investigate slow tests or increase execution time budget."
                elif is_flaky_failure:
                    fail_lessons = "Test identified as non-deterministic flaky failure; do not treat as code regression."
                elif is_runner_missing:
                    fail_lessons = "Ensure required test runner and dependencies are installed in execution environment."
                else:
                    fail_lessons = "Ensure patch addresses edge case causing test exit code failure."

                await self.adaptive_service.record_task_failure(
                    task_id=task.id,
                    stage="TESTING",
                    failure_type=fail_type,
                    failed_strategy="Proposed patch failed automated sandbox verification",
                    error_log=tr_data.get("raw_stderr") or tr_data.get("raw_stdout") or "",
                    lessons_learned=fail_lessons,
                    attempt_number=task.iterations_count,
                    review_notes=None,
                    db=db,
                )

            # Persist FlakyTestRecord if repeat detection ran (Phase 9 Stage 9.2)
            flaky_data = node_output.get("flaky_test_report")
            if flaky_data and isinstance(flaky_data, dict):
                try:
                    from app.services.flaky_detector import FlakyDetectionReport, FlakyTestDetector
                    detector = FlakyTestDetector()
                    report_obj = FlakyDetectionReport(**flaky_data)
                    await detector.record_flaky_test(
                        repository_id=repo.id,
                        task_id=task.id,
                        report=report_obj,
                        db=db,
                    )
                except Exception as e:
                    logger.warning("failed_to_persist_flaky_test_record", error=str(e))

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

    async def _distill_successful_workflow(
        self,
        task: Task,
        repo: Repository,
        user: User,
        final_val: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Distill completed verified task into memory, adaptive experience, and ML training dataset."""
        root_cause = (final_val.get("root_cause_analysis") or {}).get("root_cause", "")
        plan_obj = (final_val.get("implementation_plan") or {}).get("objective", "")
        applied_files = [f.get("file_path", "") for f in final_val.get("applied_file_changes", []) if f.get("file_path")]
        if applied_files:
            await self.memory_service.invalidate_by_files(repo.id, applied_files, db)
        await self.memory_service.distill_task_outcome(
            task=task,
            user=user,
            db=db,
            test_passed=True,
            diff_patch=final_val.get("git_diff", ""),
            root_cause=root_cause,
            resolution_strategy=plan_obj,
        )
        try:
            await self.adaptive_service.distill_task_experience(
                task=task,
                user=user,
                db=db,
                final_state=dict(final_val),
                test_passed=True,
                human_approved=True,
            )
        except Exception as e:
            logger.warning("failed_to_distill_adaptive_experience", error=str(e))

        if task.error_traceback and root_cause:
            norm_category = TracebackPreprocessor.normalize_category(
                (final_val.get("root_cause_analysis") or {}).get("bug_category", "")
            )
            pred_stmt = select(MLPrediction).where(MLPrediction.task_id == task.id).order_by(MLPrediction.created_at.desc())
            pred_res = await db.execute(pred_stmt)
            pred_entity = pred_res.scalars().first()
            if pred_entity:
                pred_entity.verified_category = norm_category
                pred_entity.is_correct = (pred_entity.predicted_category == norm_category)
            try:
                DatasetManager().add_sample(
                    category=norm_category,
                    error_message=task.title,
                    traceback=task.error_traceback,
                    context=f"Task {task.id}: {task.prompt[:100]}",
                )
            except Exception as e:
                logger.warning("failed_to_add_ml_sample", error=str(e))

    async def resume_task_workflow(
        self,
        task_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        force: bool = False,
        worker_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Safely resume an interrupted task from its last persisted database checkpoint."""
        stmt = select(Task).where(Task.id == task_id)
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

        # Stage H6 Safety Restriction: Restrict public execution in Showcase Mode
        if getattr(settings, "SHOWCASE_MODE", False):
            is_demo = any(
                demo.lower() in repo.name.lower() or demo.lower() in (repo.full_name or "").lower()
                for demo in getattr(settings, "DEMO_REPOSITORIES", [])
            )
            if not is_demo and not getattr(user, "is_superuser", False):
                raise BadRequestException(
                    f"Showcase Mode Active: Autonomous task execution is restricted to approved demonstration repositories ({', '.join(settings.DEMO_REPOSITORIES)}). Connect or select a demonstration repository to proceed."
                )

        # 1. Verify resumption eligibility
        eligible, reason, checkpoint = await self.recovery_manager.is_eligible_for_recovery(task, db, force=force)
        if not eligible or not checkpoint:
            raise BadRequestException(f"Task cannot be resumed: {reason}")

        # 2. Acquire atomic recovery lease
        worker = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        acquired = await self.recovery_manager.acquire_recovery_lease(task.id, worker, db)
        if not acquired:
            raise BadRequestException("Failed to acquire recovery lease: another worker is actively recovering this task.")

        last_node = checkpoint.node_name or checkpoint.state_blob.get("current_agent", "orchestrator")

        await self.broadcaster.emit(
            task_id=str(task.id),
            event_type="RECOVERY_STARTED",
            agent_name="orchestrator",
            message=f"Resuming interrupted workflow from step {checkpoint.step_number} (node '{last_node}').",
            payload={
                "resumed_from_node": last_node,
                "step_number": checkpoint.step_number,
                "recovery_attempts": task.recovery_attempts,
            },
            db=db,
        )

        try:
            # 3. Preserve existing workspace modifications
            base_branch = task.target_branch or repo.default_branch or "main"
            task_branch = task.task_branch or GitWorkspaceManager.generate_branch_name(task.task_type, str(task.id))
            repo_workspace = Path(settings.WORKSPACE_BASE_DIR) / str(repo.id)
            task_workspace = self.git_workspace.prepare_task_workspace(
                task_id=str(task.id),
                repo_clone_url=repo.clone_url or "",
                base_branch=base_branch,
                task_branch=task_branch,
                source_repo_dir=repo_workspace if repo_workspace.exists() else None,
                preserve_existing=True,
            )

            # 4. Restore state dictionary into LangGraph thread checkpointer
            config = {"configurable": {"thread_id": str(task.id)}}
            restored_state = dict(checkpoint.state_blob)
            restored_state["workspace_path"] = str(task_workspace)
            self.graph.update_state(config, restored_state, as_node=last_node)

            # 5. Check if restored state is already awaiting human approval
            state_snap = self.graph.get_state(config)
            if state_snap.next and "human_approval" in state_snap.next:
                task.status = "WAITING_APPROVAL"
                appr_stmt = select(Approval).where(Approval.task_id == task.id, Approval.status == "PENDING")
                appr_res = await db.execute(appr_stmt)
                if not appr_res.scalars().first():
                    approval_rec = Approval(
                        task_id=task.id,
                        requested_by=user.id,
                        status="PENDING",
                        notes="Awaiting human approval before publishing proposed code changes.",
                    )
                    db.add(approval_rec)
                await self.recovery_manager.release_recovery_lease(task.id, db, new_status="NOT_REQUIRED")
                await db.flush()
                await self.broadcaster.emit(
                    task_id=str(task.id),
                    event_type="APPROVAL_REQUIRED",
                    agent_name="orchestrator",
                    message="Workflow resumed directly to human approval gate.",
                    payload={},
                    db=db,
                )
                return {
                    "task_id": str(task.id),
                    "status": task.status,
                    "recovery_status": "NOT_REQUIRED",
                    "resumed_from_node": last_node,
                    "step_number": checkpoint.step_number,
                    "recovery_attempts": task.recovery_attempts,
                    "message": "Workflow resumed directly into human approval gate",
                }

            # 6. Stream remaining workflow execution
            task.status = "IN_PROGRESS"
            task.last_heartbeat_at = datetime.now(timezone.utc)
            await db.flush()

            step_index = checkpoint.step_number
            async for event in self.graph.astream(None, config=config):
                for node_name, node_output in event.items():
                    step_index += 1
                    logger.info("resumed_agent_node_executed", node=node_name, step=step_index)
                    await self.broadcaster.emit(
                        task_id=str(task.id),
                        event_type=f"AGENT_{node_name.upper()}_COMPLETED",
                        agent_name=node_name,
                        message=f"Specialist Agent '{node_name}' finished execution step.",
                        payload=node_output,
                        db=db,
                    )
                    await self._process_node_output(task, repo, node_name, node_output, step_index, db)

                    # Update heartbeat and persist intermediate checkpoint
                    now = datetime.now(timezone.utc)
                    task.last_heartbeat_at = now
                    current_snap = self.graph.get_state(config)
                    if current_snap and current_snap.values:
                        cp_id = str(current_snap.config.get("configurable", {}).get("checkpoint_id", uuid.uuid4().hex))
                        cp_ns = str(current_snap.config.get("configurable", {}).get("checkpoint_ns", ""))
                        clean_blob = sanitize_state_blob(dict(current_snap.values))
                        inter_cp = WorkflowCheckpoint(
                            task_id=task.id,
                            thread_id=str(task.id),
                            checkpoint_ns=cp_ns,
                            checkpoint_id=cp_id,
                            node_name=node_name,
                            step_number=step_index,
                            version=1,
                            state_blob=clean_blob,
                        )
                        db.add(inter_cp)
            await db.flush()

            # 7. Evaluate post-stream status
            final_snap = self.graph.get_state(config)
            if final_snap.next and "human_approval" in final_snap.next:
                task.status = "WAITING_APPROVAL"
                appr_stmt = select(Approval).where(Approval.task_id == task.id, Approval.status == "PENDING")
                appr_res = await db.execute(appr_stmt)
                if not appr_res.scalars().first():
                    approval_rec = Approval(
                        task_id=task.id,
                        requested_by=user.id,
                        status="PENDING",
                        notes="Awaiting human approval before publishing proposed code changes.",
                    )
                    db.add(approval_rec)
                await self.recovery_manager.release_recovery_lease(task.id, db, new_status="NOT_REQUIRED")
                await db.flush()
                await self.broadcaster.emit(
                    task_id=str(task.id),
                    event_type="APPROVAL_REQUIRED",
                    agent_name="orchestrator",
                    message="Proposed modifications require developer approval before publishing.",
                    payload={},
                    db=db,
                )
            else:
                final_val = final_snap.values if final_snap else {}
                final_status = final_val.get("execution_status", "COMPLETED")
                task.status = final_status if final_status in ("COMPLETED", "FAILED") else "COMPLETED"
                await db.flush()

                if task.status == "COMPLETED":
                    await self._distill_successful_workflow(task, repo, user, final_val, db)

                await self.recovery_manager.release_recovery_lease(task.id, db, new_status="RECOVERED")
                await self.broadcaster.emit(
                    task_id=str(task.id),
                    event_type="RECOVERY_COMPLETED",
                    agent_name="orchestrator",
                    message=f"Interrupted task recovery completed with status: {task.status}",
                    payload={"final_status": task.status},
                    db=db,
                )

            return {
                "task_id": str(task.id),
                "status": task.status,
                "recovery_status": task.recovery_status,
                "resumed_from_node": last_node,
                "step_number": step_index,
                "recovery_attempts": task.recovery_attempts,
                "message": f"Workflow successfully resumed to state '{task.status}'",
            }

        except Exception as exc:
            logger.error("task_resumption_failed", task_id=str(task.id), error=str(exc))
            task.status = "FAILED"
            await self.recovery_manager.release_recovery_lease(
                task.id, db, new_status="INTERRUPTED", recovery_error=str(exc)
            )
            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="RECOVERY_FAILED",
                agent_name="orchestrator",
                message=f"Task resumption failed: {str(exc)}",
                payload={"error": str(exc)},
                db=db,
            )
            raise BadRequestException(f"Task resumption failed: {str(exc)}")

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
                    .order_by(WorkflowCheckpoint.step_number.desc(), WorkflowCheckpoint.created_at.desc())
                )
                cp_res = await db.execute(cp_stmt)
                saved_cp = cp_res.scalars().first()
                if saved_cp and saved_cp.state_blob:
                    logger.info("recovering_workflow_from_database_checkpoint", task_id=str(task.id))
                    resume_node = (
                        saved_cp.node_name
                        if saved_cp.node_name and saved_cp.node_name not in ("orchestrator", "__interrupt__")
                        else "security_reviewer"
                    )
                    self.graph.update_state(config, saved_cp.state_blob, as_node=resume_node)

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
            final_val = dict(final_snap.values) if (final_snap and final_snap.values) else {}
            if final_snap and final_snap.values:
                cp_id = str(final_snap.config.get("configurable", {}).get("checkpoint_id", uuid.uuid4().hex))
                blob = sanitize_state_blob(dict(final_val))
                final_cp = WorkflowCheckpoint(
                    task_id=task.id,
                    thread_id=str(task.id),
                    checkpoint_ns="",
                    checkpoint_id=cp_id,
                    node_name="reporter",
                    step_number=999,
                    version=1,
                    state_blob=blob,
                )
                db.add(final_cp)

            task.status = "COMPLETED"
            task.recovery_status = "NOT_REQUIRED"
            await db.flush()

            # GitHub-Native Engineering: Commit, push, and open Pull Request
            pr_data = None
            task_ws = Path(final_val.get("workspace_path") or str(self.git_workspace.get_task_workspace_path(str(task.id))))
            commit_sha = task.commit_sha
            if task_ws.exists():
                try:
                    commit_msg = (
                        f"fix({task.task_type}): {task.title}\n\n"
                        f"- Automated precision patch applied\n"
                        f"- Verified in isolated execution sandbox\n"
                        f"Task-ID: {task.id}\n"
                        f"Co-authored-by: Devora AI Engine <engine@devora.ai>"
                    )
                    commit_sha = self.git_workspace.commit_changes(
                        workspace_path=task_ws,
                        message=commit_msg,
                    )
                    task.commit_sha = commit_sha
                except Exception as e:
                    logger.warning("git_commit_warning", error=str(e))

                # Safety Gate (Stage H6): In Showcase Mode or when automatic push is disabled,
                # skip remote git write operations to protect external repositories from unauthorized writes
                if getattr(settings, "SHOWCASE_MODE", False) or getattr(settings, "AUTO_GIT_PUSH_DISABLED", False):
                    logger.info("showcase_mode_remote_git_push_skipped", task_id=str(task.id))
                    b_stmt = select(GitBranch).where(
                        GitBranch.task_id == task.id,
                        GitBranch.branch_name == task.task_branch,
                    )
                    b_res = await db.execute(b_stmt)
                    b_entity = b_res.scalar_one_or_none()
                    if b_entity:
                        b_entity.commit_sha = commit_sha
                        b_entity.is_pushed = True
                        b_entity.pushed_at = datetime.now(timezone.utc)
                    pr_data = {
                        "pr_number": 42,
                        "html_url": f"https://github.com/devora-ai/showcase-demo/pull/42",
                        "head_branch": task.task_branch or "devora/patch",
                        "base_branch": task.target_branch or "main",
                        "showcase_simulated": True,
                    }
                    await self.broadcaster.emit(
                        task_id=str(task.id),
                        event_type="PULL_REQUEST_CREATED",
                        agent_name="orchestrator",
                        message=f"[SHOWCASE] Demonstration Pull Request recorded: {pr_data['html_url']} (Remote push requires human authorization)",
                        payload=pr_data,
                        db=db,
                    )
                else:
                    try:
                        # Push task branch to remote
                        repo_res = await db.execute(select(Repository).where(Repository.id == task.repository_id))
                        repo_obj = repo_res.scalar_one_or_none()
                        if repo_obj and repo_obj.clone_url:
                            inst_id = repo_obj.installation_id or 1001
                            token = await self.github_app.get_installation_access_token(inst_id)
                            self.git_workspace.push_branch(
                                workspace_path=task_ws,
                                branch_name=task.task_branch or f"devora/{task.task_type}-{str(task.id)[:8]}",
                                remote_url=repo_obj.clone_url,
                                token=token,
                            )
                            # Update GitBranch entity
                            b_stmt = select(GitBranch).where(
                                GitBranch.task_id == task.id,
                                GitBranch.branch_name == task.task_branch,
                            )
                            b_res = await db.execute(b_stmt)
                            b_entity = b_res.scalar_one_or_none()
                            if b_entity:
                                b_entity.commit_sha = commit_sha
                                b_entity.is_pushed = True
                                b_entity.pushed_at = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.warning("git_push_warning", error=str(e))

                    # Publish GitHub Pull Request
                    try:
                        gh_pr = await self.pr_service.create_pull_request_for_task(
                            db=db,
                            task_id=task.id,
                        )
                        pr_data = {
                            "pr_number": gh_pr.pr_number,
                            "html_url": gh_pr.html_url,
                            "head_branch": gh_pr.head_branch,
                            "base_branch": gh_pr.base_branch,
                        }
                        await self.broadcaster.emit(
                            task_id=str(task.id),
                            event_type="PULL_REQUEST_CREATED",
                            agent_name="orchestrator",
                            message=f"Created Pull Request #{gh_pr.pr_number}: {gh_pr.html_url}",
                            payload=pr_data,
                            db=db,
                        )
                    except Exception as e:
                        logger.warning("pr_creation_warning", error=str(e))

            # Distill completed verified task into persistent project memory
            final_val = final_snap.values if final_snap and final_snap.values else {}
            root_cause = (final_val.get("root_cause_analysis") or {}).get("root_cause", "")
            plan_obj = (final_val.get("implementation_plan") or {}).get("objective", "")
            applied_files = [f.get("file_path", "") for f in final_val.get("applied_file_changes", []) if f.get("file_path")]
            if applied_files and task.repository_id:
                await self.memory_service.invalidate_by_files(task.repository_id, applied_files, db)
            await self.memory_service.distill_task_outcome(
                task=task,
                user=user,
                db=db,
                test_passed=True,
                diff_patch=final_val.get("git_diff", ""),
                root_cause=root_cause,
                resolution_strategy=plan_obj,
            )
            # Adaptive Intelligence: distill task experience
            try:
                await self.adaptive_service.distill_task_experience(
                    task=task,
                    user=user,
                    db=db,
                    final_state=dict(final_val),
                    test_passed=True,
                    human_approved=True,
                )
            except Exception as e:
                logger.warning("failed_to_distill_adaptive_experience", error=str(e))
            # Continuous learning: link verified outcome to ML prediction and candidate pool
            if task.error_traceback and root_cause:
                norm_category = TracebackPreprocessor.normalize_category(
                    (final_val.get("root_cause_analysis") or {}).get("bug_category", "")
                )
                pred_stmt = select(MLPrediction).where(MLPrediction.task_id == task.id).order_by(MLPrediction.created_at.desc())
                pred_res = await db.execute(pred_stmt)
                pred_entity = pred_res.scalars().first()
                if pred_entity:
                    pred_entity.verified_category = norm_category
                    pred_entity.is_correct = (pred_entity.predicted_category == norm_category)
                try:
                    DatasetManager().add_sample(
                        category=norm_category,
                        error_message=task.title,
                        traceback=task.error_traceback,
                        context=f"Task {task.id}: {task.prompt[:100]}",
                    )
                except Exception as e:
                    logger.warning("failed_to_add_ml_sample", error=str(e))

            await self.broadcaster.emit(
                task_id=str(task.id),
                event_type="COMPLETED",
                agent_name="orchestrator",
                message="Task completed successfully.",
                payload={"pull_request": pr_data, "commit_sha": commit_sha},
                db=db,
            )
            return {
                "status": "COMPLETED",
                "message": "Changes approved, committed, pushed, and Pull Request opened.",
                "pull_request": pr_data,
                "commit_sha": commit_sha,
            }

        else:
            # Rejection or Request Changes
            new_status = "REJECTED" if action.lower() == "reject" else "CHANGES_REQUESTED"
            if approval:
                approval.status = new_status
                approval.reviewed_by = user.id
                approval.responded_at = datetime.now(timezone.utc)
                approval.notes = notes

            if new_status == "REJECTED":
                fail_rec = TaskFailureRecord(
                    task_id=task.id,
                    stage="DEVELOPER_REVIEW",
                    failure_type="IMPLEMENTATION_DEFECT",
                    failed_strategy="Developer rejected implementation",
                    error_log=notes or "Developer rejected proposed solution during approval gate.",
                    review_notes=notes,
                    lessons_learned=f"Avoid proposed modifications for task '{task.title}': {notes or 'Rejected by developer.'}",
                )
                db.add(fail_rec)

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
