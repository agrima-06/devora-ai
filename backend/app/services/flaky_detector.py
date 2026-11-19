"""Flaky Test Detection Engine: identifies non-deterministic test failures,
measures test stability, records historical flakiness, and prevents unnecessary LLM code-revision loops.
"""
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.flaky_test_record import FlakyTestRecord
from app.services.sandbox_service import SandboxService
from app.services.test_discovery_service import NormalizedTestResult, TestDiscoveryService

logger = get_logger("flaky_detector")


@dataclass
class SingleExecutionRecord:
    """Record of a single repeat test execution."""
    run_index: int
    exit_code: int
    passed: bool
    duration_seconds: float
    is_infra_error: bool = False
    is_timeout: bool = False
    error_preview: Optional[str] = None


@dataclass
class FlakyDetectionReport:
    """Comprehensive diagnostic report from the Flaky Test Detector."""
    test_identifier: str
    test_file: str
    framework: str
    command: str
    classification: str  # STABLE_PASS, CONSISTENT_FAILURE, FLAKY, INCONCLUSIVE, UNVERIFIED
    stability_score: float  # 0.0 - 100.0
    total_runs: int
    passed_runs: int
    failed_runs: int
    infrastructure_error_runs: int
    timeout_runs: int
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    diagnostic_message: str = ""
    is_flaky: bool = False


class FlakyTestDetector:
    """Detects, scores, and classifies non-deterministic test failures."""

    def __init__(
        self,
        sandbox: Optional[SandboxService] = None,
        discovery: Optional[TestDiscoveryService] = None,
    ):
        self.sandbox = sandbox or SandboxService()
        self.discovery = discovery or TestDiscoveryService()

    # ---------------------------------------------------------------------------
    # Eligibility Check
    # ---------------------------------------------------------------------------

    def is_eligible_for_flaky_detection(self, test_result: NormalizedTestResult) -> Tuple[bool, str]:
        """Determine whether a test failure is eligible for flaky detection."""
        if not settings.FLAKY_DETECTION_ENABLED:
            return False, "Flaky test detection is globally disabled in configuration."

        if test_result.passed:
            return False, "Test passed successfully; not eligible for flakiness check."

        if test_result.execution_status == "UNAVAILABLE" or test_result.failure_classification in ("RUNNER_UNAVAILABLE", "COMMAND_NOT_FOUND", "COMMAND_NOT_EXECUTABLE"):
            return False, "Test runner is unavailable in execution environment; not a test defect or flakiness."

        if test_result.execution_status in ("OOM_KILLED", "TIMED_OUT") or test_result.failure_classification in (
            "OOM_KILLED", "PROCESS_KILLED", "SANDBOX_STARTUP_FAILURE", "TIMEOUT", "EXECUTION_TIMEOUT"
        ):
            return False, "Failure caused by sandbox resource or environment constraint; not a test assertion defect or flakiness."

        if test_result.failure_classification == "MISSING_DEPENDENCY":
            return False, "Failure caused by missing project dependency; not a non-deterministic flaky failure."

        if test_result.total_tests == 0 and test_result.exit_code != 0:
            return False, "Zero tests discovered or executed."

        return True, "Eligible for flaky test verification."

    # ---------------------------------------------------------------------------
    # Fingerprint / Test Identifier Extraction
    # ---------------------------------------------------------------------------

    def extract_test_identifier(
        self,
        test_command: str,
        failure_details: Optional[List[str]] = None,
        selected_files: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Derive a canonical, stable test identifier and test file."""
        test_file = "unknown"
        if selected_files:
            test_file = selected_files[0]

        # Check failure details for explicit test name
        if failure_details:
            for detail in failure_details:
                # Go test pattern: --- FAIL: TestLogout
                m_go = re.search(r"---\s+FAIL:\s+([^\s]+)", detail)
                if m_go:
                    return m_go.group(1), test_file

                # Pytest pattern: FAILED tests/test_auth.py::test_login
                m_pytest = re.search(r"FAILED\s+([^\s:]+\.[a-zA-Z0-9]+)(?:::([^\s]+))?", detail)
                if m_pytest:
                    t_file = m_pytest.group(1)
                    t_func = m_pytest.group(2) or "all"
                    return f"{t_file}::{t_func}", t_file

                # Unittest pattern: FAIL: test_div (tests.test_math.TestMath)
                m_unit = re.search(r"^FAIL:\s+([^\s]+)\s+\(([^)]+)\)", detail)
                if m_unit:
                    return f"{m_unit.group(2)}.{m_unit.group(1)}", m_unit.group(2)

                # Jest/Vitest pattern: ✕ Button renders or FAIL src/Button.test.tsx
                m_jest = re.search(r"FAIL\s+([^\s]+)", detail)
                if m_jest:
                    return m_jest.group(1), m_jest.group(1)

                # Cargo pattern: test tests::test_sub ... FAILED
                m_cargo = re.search(r"test\s+([^\s]+)\s+\.\.\.\s+FAILED", detail)
                if m_cargo:
                    return m_cargo.group(1), test_file

        # Fallback to test command / test file
        cmd_clean = re.sub(r"^(?:pytest|npm test|go test|cargo test|mvn test)\s*", "", test_command).strip()
        ident = cmd_clean if cmd_clean else test_command
        return ident, test_file

    # ---------------------------------------------------------------------------
    # Stability Scoring Algorithm
    # ---------------------------------------------------------------------------

    def calculate_stability(
        self,
        runs: List[SingleExecutionRecord],
    ) -> Tuple[float, str]:
        """Calculate deterministic stability score and classification according to strict rules."""
        total = len(runs)
        if total == 0:
            return 0.0, "UNVERIFIED"

        passed_runs = sum(1 for r in runs if r.passed and not r.is_infra_error)
        failed_runs = sum(1 for r in runs if not r.passed and not r.is_infra_error and not r.is_timeout)
        infra_runs = sum(1 for r in runs if r.is_infra_error)
        timeout_runs = sum(1 for r in runs if r.is_timeout)

        valid_executions = passed_runs + failed_runs

        # If infrastructure errors prevent evaluation
        if valid_executions == 0:
            if timeout_runs > 0:
                return 0.0, "INCONCLUSIVE"
            if infra_runs > 0:
                return 0.0, "INCONCLUSIVE"
            return 0.0, "UNVERIFIED"

        stability_score = round((passed_runs / valid_executions) * 100.0, 1)

        if passed_runs == valid_executions:
            classification = "STABLE_PASS"
        elif failed_runs == valid_executions:
            classification = "CONSISTENT_FAILURE"
        else:
            # Mixed pass and fail outcomes
            classification = "FLAKY"

        return stability_score, classification

    # ---------------------------------------------------------------------------
    # Repeat Execution & Flakiness Analysis
    # ---------------------------------------------------------------------------

    def detect_flakiness(
        self,
        workspace_path: Path,
        test_command: str,
        framework: str,
        initial_failed_result: NormalizedTestResult,
        repeat_runs: Optional[int] = None,
        timeout_seconds: int = 60,
    ) -> FlakyDetectionReport:
        """Execute bounded repeat runs under identical conditions to assess stability."""
        # 1. Clamp repeat count between min and max
        runs_target = repeat_runs or settings.FLAKY_REPEAT_RUNS_DEFAULT
        runs_target = max(settings.FLAKY_REPEAT_RUNS_MIN, min(settings.FLAKY_REPEAT_RUNS_MAX, runs_target))

        ident, test_file = self.extract_test_identifier(
            test_command=test_command,
            failure_details=initial_failed_result.failure_details,
            selected_files=initial_failed_result.selected_test_files,
        )

        records: List[SingleExecutionRecord] = []
        # Include initial execution as run 1
        records.append(
            SingleExecutionRecord(
                run_index=1,
                exit_code=initial_failed_result.exit_code,
                passed=initial_failed_result.passed,
                duration_seconds=initial_failed_result.duration_seconds,
                is_infra_error=(initial_failed_result.execution_status == "UNAVAILABLE"),
                is_timeout=(initial_failed_result.execution_status == "TIMED_OUT"),
                error_preview=initial_failed_result.failure_details[0] if initial_failed_result.failure_details else None,
            )
        )

        logger.info(
            "flaky_detection_started",
            identifier=ident,
            command=test_command,
            runs_target=runs_target,
        )

        total_detection_start = time.time()
        for idx in range(2, runs_target + 1):
            # Check total detection budget
            if time.time() - total_detection_start > settings.FLAKY_TOTAL_TIMEOUT_SECONDS:
                logger.warning("flaky_detection_time_budget_exhausted", identifier=ident)
                break

            exec_res = self.sandbox.execute_command(
                workspace_path=workspace_path,
                command=test_command,
                timeout_seconds=timeout_seconds,
            )

            is_infra = (
                exec_res.oom_killed
                or exec_res.exit_classification in (
                    "OOM_KILLED", "COMMAND_NOT_FOUND", "COMMAND_NOT_EXECUTABLE", "PROCESS_KILLED", "SANDBOX_STARTUP_FAILURE", "RUNNER_UNAVAILABLE"
                )
                or exec_res.exit_code in (126, 127)
                or "command not found" in exec_res.stderr.lower()
            )
            is_to = exec_res.timed_out or exec_res.exit_code in (-1, 124) or exec_res.exit_classification == "TIMEOUT"
            passed = (exec_res.exit_code == 0)

            preview = None
            if not passed:
                preview = (exec_res.stderr.strip() or exec_res.stdout.strip())[:200]

            records.append(
                SingleExecutionRecord(
                    run_index=idx,
                    exit_code=exec_res.exit_code,
                    passed=passed,
                    duration_seconds=exec_res.duration_seconds,
                    is_infra_error=is_infra,
                    is_timeout=is_to,
                    error_preview=preview,
                )
            )

        stability_score, classification = self.calculate_stability(records)
        is_flaky = (classification == "FLAKY")

        passed_count = sum(1 for r in records if r.passed and not r.is_infra_error)
        failed_count = sum(1 for r in records if not r.passed and not r.is_infra_error and not r.is_timeout)
        infra_count = sum(1 for r in records if r.is_infra_error)
        to_count = sum(1 for r in records if r.is_timeout)

        diag_msg = (
            f"Test '{ident}' verified over {len(records)} runs. "
            f"Classification: {classification} (Stability: {stability_score}%, {passed_count} passed, {failed_count} failed)."
        )

        logger.info(
            "flaky_detection_completed",
            identifier=ident,
            classification=classification,
            stability_score=stability_score,
            is_flaky=is_flaky,
        )

        return FlakyDetectionReport(
            test_identifier=ident,
            test_file=test_file,
            framework=framework,
            command=test_command,
            classification=classification,
            stability_score=stability_score,
            total_runs=len(records),
            passed_runs=passed_count,
            failed_runs=failed_count,
            infrastructure_error_runs=infra_count,
            timeout_runs=to_count,
            execution_history=[asdict(r) for r in records],
            diagnostic_message=diag_msg,
            is_flaky=is_flaky,
        )

    # ---------------------------------------------------------------------------
    # Database Persistence & Historical Retrieval
    # ---------------------------------------------------------------------------

    def _sanitize_record_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scrub tokens, credentials, and API keys from execution history."""
        clean_hist = []
        token_pat = re.compile(r"(ghp_[a-zA-Z0-9]{36}|AIza[0-9A-Za-z-_]{35}|Bearer\s+[a-zA-Z0-9_\-\.]+)")
        for h in history:
            clean_item = dict(h)
            if clean_item.get("error_preview"):
                clean_item["error_preview"] = token_pat.sub("[REDACTED]", str(clean_item["error_preview"]))
            clean_hist.append(clean_item)
        return clean_hist

    async def record_flaky_test(
        self,
        repository_id: uuid.UUID,
        task_id: uuid.UUID,
        report: FlakyDetectionReport,
        db: AsyncSession,
    ) -> FlakyTestRecord:
        """Upsert a flaky test record in PostgreSQL."""
        # Check for existing record for repository and test identifier
        stmt = select(FlakyTestRecord).where(
            FlakyTestRecord.repository_id == repository_id,
            FlakyTestRecord.test_identifier == report.test_identifier,
        )
        res = await db.execute(stmt)
        record = res.scalars().first()

        now = datetime.now(timezone.utc)
        safe_history = self._sanitize_record_history(report.execution_history)

        if record:
            record.task_id = task_id
            record.classification = report.classification
            record.stability_score = report.stability_score
            record.total_runs += report.total_runs
            record.passed_runs += report.passed_runs
            record.failed_runs += report.failed_runs
            record.infrastructure_error_runs += report.infrastructure_error_runs
            record.timeout_runs += report.timeout_runs
            record.execution_history = {
                "latest_runs": safe_history,
                "history_summary": f"Updated at {now.isoformat()} with {report.total_runs} runs",
            }
            record.last_detected_at = now
            record.last_verified_at = now
        else:
            record = FlakyTestRecord(
                repository_id=repository_id,
                task_id=task_id,
                test_identifier=report.test_identifier,
                test_file=report.test_file,
                framework=report.framework,
                language="python",
                test_command=report.command,
                classification=report.classification,
                stability_score=report.stability_score,
                total_runs=report.total_runs,
                passed_runs=report.passed_runs,
                failed_runs=report.failed_runs,
                infrastructure_error_runs=report.infrastructure_error_runs,
                timeout_runs=report.timeout_runs,
                execution_history={"latest_runs": safe_history},
                first_detected_at=now,
                last_detected_at=now,
                last_verified_at=now,
            )
            db.add(record)

        await db.flush()
        return record

    async def get_repository_flaky_tests(
        self,
        repository_id: uuid.UUID,
        db: AsyncSession,
        classification: Optional[str] = None,
    ) -> List[FlakyTestRecord]:
        """Query flaky test records for a repository."""
        stmt = select(FlakyTestRecord).where(FlakyTestRecord.repository_id == repository_id)
        if classification:
            stmt = stmt.where(FlakyTestRecord.classification == classification)
        stmt = stmt.order_by(FlakyTestRecord.last_detected_at.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def get_task_flaky_tests(
        self,
        task_id: uuid.UUID,
        db: AsyncSession,
    ) -> List[FlakyTestRecord]:
        """Query flaky test records identified in a task."""
        stmt = select(FlakyTestRecord).where(FlakyTestRecord.task_id == task_id).order_by(FlakyTestRecord.created_at.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def get_repository_stability_summary(
        self,
        repository_id: uuid.UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Aggregate test stability statistics for a repository."""
        stmt = select(
            func.count(FlakyTestRecord.id).label("total_tests_tracked"),
            func.avg(FlakyTestRecord.stability_score).label("avg_stability_score"),
            func.sum(FlakyTestRecord.total_runs).label("total_repeat_runs"),
        ).where(FlakyTestRecord.repository_id == repository_id)

        res = await db.execute(stmt)
        row = res.first()

        flaky_stmt = select(func.count(FlakyTestRecord.id)).where(
            FlakyTestRecord.repository_id == repository_id,
            FlakyTestRecord.classification == "FLAKY",
        )
        flaky_count = (await db.execute(flaky_stmt)).scalar() or 0

        stable_stmt = select(func.count(FlakyTestRecord.id)).where(
            FlakyTestRecord.repository_id == repository_id,
            FlakyTestRecord.classification == "STABLE_PASS",
        )
        stable_count = (await db.execute(stable_stmt)).scalar() or 0

        fail_stmt = select(func.count(FlakyTestRecord.id)).where(
            FlakyTestRecord.repository_id == repository_id,
            FlakyTestRecord.classification == "CONSISTENT_FAILURE",
        )
        consistent_fail_count = (await db.execute(fail_stmt)).scalar() or 0

        total_tracked = row.total_tests_tracked if row else 0
        avg_score = round(float(row.avg_stability_score or 0.0), 1) if row else 0.0
        total_runs = row.total_repeat_runs if row else 0

        return {
            "repository_id": str(repository_id),
            "total_tests_tracked": total_tracked,
            "flaky_tests_count": flaky_count,
            "stable_pass_count": stable_count,
            "consistent_failure_count": consistent_fail_count,
            "average_stability_score": avg_score,
            "total_repeat_runs_executed": total_runs,
        }
