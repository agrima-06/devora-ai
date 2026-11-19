# Devora AI — Phase 9, Stage 9.3 Implementation Plan
## Sandbox Resilience, OOM Classification & Resource Telemetry

**Version:** 1.0.0  
**Phase:** 9 (Autonomous Engineering Reliability)  
**Stage:** 9.3  
**Status:** In Progress / Approved for Implementation  
**Target Baseline:** 183 passed backend tests, 15/15 compiled frontend routes  

---

## 1. Executive Summary

Phase 9, Stage 9.3 extends Devora AI's sandbox execution system (`SandboxService`) to provide robust execution resilience, deterministic container exit code classification, forensic out-of-memory (OOM) verification, real-time resource telemetry extraction, dynamic test timeout scaling, and adaptive failure routing.

This stage eliminates false-positive LLM code rewrite loops triggered by resource exhaustion (OOM, SIGKILL, CPU throttling, or timeouts) and provides transparent telemetry to developer operators via task detail views and SSE event streams.

---

## 2. Current Sandbox Architecture & Audit

### 2.1 Existing Execution Architecture
- **Runners:**
  - `DockerSandboxRunner`: Spawns isolated Docker containers (`python:3.11-slim-bookworm`) with `--network none`, `--memory 1500m`, `--cpus 2.0`, `--pids-limit 100`, `--cap-drop=ALL`, `--security-opt=no-new-privileges:true`. Currently uses `--rm` flag and returns basic `ExecutionResult(exit_code, stdout, stderr, duration_seconds, timed_out)`.
  - `LocalIsolatedRunner`: Fallback environment for environments without Docker or unit/integration testing with stripped environment variables (`safe_env`), working directory confinement, and command whitelisting (`ALLOWED_PREFIXES`).
- **Test Orchestration:**
  - `TestDiscoveryService`: Discovers manifests (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`) and executes test plans.
  - `FlakyTestDetector`: Evaluates non-deterministic test failures over repeated runs ($N=3 \dots 5$).
  - `tester_node`: Invokes sandbox test command and parses output into `TestRunOutput`.
  - `route_after_tester`: Directs control flow in LangGraph state machine based on test results.
  - `workflow_service`: Persists `TestRun` records and failure telemetry (`TaskFailureRecord`).

### 2.2 Identified Gaps & Deficiencies
1. **Ambiguous SIGKILL (Exit 137) Handling:**
   - Exit code 137 currently causes an execution failure with no distinction between true kernel OOM killer events and generic external process terminations (`SIGKILL`).
2. **Ephemeral `--rm` Container Lifecycles:**
   - Using `--rm` removes the container before `docker inspect` or cgroup v2 accounting metrics (`memory.events`, `oom_kill`, peak RSS) can be queried.
3. **No Centralized Exit Code Classification:**
   - Raw numeric exit codes (124, 126, 127, 137) are evaluated ad-hoc in string searches (`"command not found"`).
4. **Lack of Resource Telemetry:**
   - Peak RSS memory, CPU core execution time, and configured limits are not captured in `ExecutionResult`, `TestRunOutput`, or database `test_runs`.
5. **Static Execution Timeout:**
   - Test suites are executed with a fixed 60s timeout regardless of test count, risking false timeouts on large suites (>50 tests).
6. **False Implementation Defect Penalization:**
   - Sandbox resource failures (OOM or timeouts) risk being labeled as `IMPLEMENTATION_DEFECT` and triggering redundant Coding Agent prompt loops.

---

## 3. Technical Design & Architecture Specifications

### 3.1 Centralized Container Exit Code Classification

The sandbox will map process and container termination states using deterministic classification logic:

| Exit Status | Criteria / Evidence | Classification |
|---|---|---|
| `0` | Clean process termination | `SUCCESS` |
| `124` or `timed_out=True` | Subprocess or container timeout expired | `TIMEOUT` |
| `126` | Permission denied or unexecutable binary format | `COMMAND_NOT_EXECUTABLE` |
| `127` | Binary or runner not located on PATH | `COMMAND_NOT_FOUND` |
| `137` | Exit 137 **AND** confirmed via `OOMKilled=True` or `oom_kill > 0` | `OOM_KILLED` |
| `137` | Exit 137 **WITHOUT** independent OOM evidence | `PROCESS_KILLED` |
| `-1` | Python process timeout exception | `TIMEOUT` |
| `Non-zero` | Other general runtime or assertion failures | `EXECUTION_FAILURE` |

#### OOM Confirmation Methodology:
1. **Docker Container Inspection:** Query `docker inspect <container_id>` for `State.OOMKilled == true`.
2. **cgroup v2 Memory Events:** Inspect container cgroup `/sys/fs/cgroup/memory.events` for `oom_kill > 0`.
3. **Guard Rule:** Exit code 137 alone will **never** be classified as `OOM_KILLED` unless confirmed by Docker or cgroup metadata; otherwise it defaults safely to `PROCESS_KILLED`.

---

### 3.2 Extended Resource Telemetry Model

Extend `ExecutionResult` and `TestRunOutput` with complete telemetry fields:

```python
@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    
    # Telemetry & Resource Accounting (Phase 9 Stage 9.3)
    peak_memory_rss_bytes: Optional[int] = None
    peak_memory_rss_mb: Optional[float] = None
    cpu_time_seconds: Optional[float] = None
    wall_time_seconds: Optional[float] = None
    memory_limit_bytes: Optional[int] = None
    memory_limit_mb: Optional[float] = None
    cpu_limit: Optional[float] = None
    oom_killed: bool = False
    termination_reason: Optional[str] = None
    exit_classification: str = "EXECUTION_FAILURE"
    resource_telemetry_available: bool = False
```

#### Collection Strategy:
- **Docker Runner:**
  - Container named deterministically: `devora-sandbox-{uuid.hex[:12]}`.
  - Run without `--rm`, execute command, inspect container metrics via `docker inspect`, then unconditionally remove in `finally` block.
  - Extract `State.OOMKilled`, `HostConfig.Memory`, `HostConfig.NanoCpus`.
- **Local Runner:**
  - Use Python's `resource.getrusage(resource.RUSAGE_CHILDREN)` for accurate process CPU time (`ru_utime + ru_stime`) and peak memory RSS (converted from bytes/KB to MB).
  - Explicitly mark `resource_telemetry_available = True` when valid numbers are obtained, or `False` if unavailable. Never fabricate zeros.

---

### 3.3 Dynamic Test Timeout Scaling Engine

Implement intelligent scaling in `TestDiscoveryService`:

```python
class TestTimeoutScaler:
    BASE_TIMEOUT: int = 60
    LARGE_SUITE_THRESHOLD: int = 50
    LARGE_SUITE_MULTIPLIER: float = 1.5
    MAX_TIMEOUT: int = 300
    TASK_BUDGET_CEILING: int = 600

    @classmethod
    def calculate_timeout(cls, total_tests: int, requested_timeout: Optional[int] = None) -> Tuple[int, str]:
        base = requested_timeout or cls.BASE_TIMEOUT
        if total_tests <= cls.LARGE_SUITE_THRESHOLD:
            return base, f"Standard suite ({total_tests} tests <= {cls.LARGE_SUITE_THRESHOLD})"
        
        scaled = int(base * cls.LARGE_SUITE_MULTIPLIER)
        final_timeout = min(scaled, cls.MAX_TIMEOUT)
        reason = (
            f"Large test suite detected ({total_tests} tests > {cls.LARGE_SUITE_THRESHOLD}). "
            f"Scaled timeout from {base}s to {final_timeout}s (multiplier={cls.LARGE_SUITE_MULTIPLIER}, ceiling={cls.MAX_TIMEOUT}s)."
        )
        return final_timeout, reason
```

- Enforces strict upper bound (`MAX_TIMEOUT = 300s`).
- Does not scale merely because a test failed.
- Logs original timeout, adjusted timeout, scaling reason, and applied ceiling.

---

### 3.4 Adaptive Failure Classification & Workflow Routing

1. **Classification Mapping:**
   - `OOM_KILLED`
   - `RESOURCE_EXHAUSTED`
   - `EXECUTION_TIMEOUT`
   - `PROCESS_KILLED`
   - `SANDBOX_STARTUP_FAILURE`
   - `RUNNER_UNAVAILABLE`
   - `COMMAND_NOT_FOUND`
   - `COMMAND_NOT_EXECUTABLE`

2. **Graph Routing (`route_after_tester` in `graph.py`):**
   - Resource or environment failures (`OOM_KILLED`, `PROCESS_KILLED`, `EXECUTION_TIMEOUT`, `SANDBOX_STARTUP_FAILURE`, `RUNNER_UNAVAILABLE`, `COMMAND_NOT_FOUND`, `COMMAND_NOT_EXECUTABLE`) route directly to `reporter`.
   - Bypasses `retry_incrementer` and coding agent to eliminate destructive code churn on functional code when constrained by environment limits.

3. **Stage 9.2 Flaky Test Detector Interaction:**
   - In repeat runs ($N=2 \dots 5$), any run suffering an infrastructure, timeout, or OOM event is marked `is_infra_error = True` or `is_timeout = True`.
   - Excluded from `valid_executions` so non-deterministic assertions are not confounded with hardware/system resource limits.

4. **Experience Distillation (`workflow_service.py`):**
   - Resource and sandbox failures are persisted as `ENVIRONMENT_PROBLEM` in `TaskFailureRecord` with tailored lessons ("Sandbox memory or time budget exceeded; optimize memory allocation or test batching").

---

## 4. Database Schema & Migration Requirements

Alembic migration: `009_resource_telemetry.py` (down-revision: `008_flaky_test_records`).

### Columns added to `test_runs`:
- `peak_memory_rss_bytes`: `BigInteger`, nullable
- `peak_memory_rss_mb`: `Float`, nullable
- `cpu_time_seconds`: `Float`, nullable
- `wall_time_seconds`: `Float`, nullable
- `memory_limit_bytes`: `BigInteger`, nullable
- `memory_limit_mb`: `Float`, nullable
- `cpu_limit`: `Float`, nullable
- `oom_killed`: `Boolean`, default `False`, nullable=False
- `termination_reason`: `String(100)`, nullable
- `resource_telemetry_available`: `Boolean`, default `False`, nullable=False

---

## 5. Frontend UI/UX Integration

In `frontend/src/app/tasks/[id]/page.tsx` & `types/index.ts`:
1. **Telemetry Statistics Card in Test Results tab:**
   - Duration & Wall-Clock Time
   - Peak RSS Memory (MB) vs Memory Limit (MB)
   - CPU Time (s) vs CPU Cores Limit
   - Clear banner if `resource_telemetry_available === false`: "Resource Telemetry Unavailable"
2. **Explicit Badges:**
   - `OOM KILLED (CONFIRMED)` — Crimson/Destructive Badge
   - `PROCESS KILLED (SIGKILL)` — Amber Badge
   - `EXECUTION TIMEOUT` — Yellow Badge
   - `COMMAND NOT FOUND` — Amber Badge
   - `RUNNER UNAVAILABLE` — Outline Badge
   - `PASSED` — Emerald Badge

---

## 6. Files to Create and Modify

### New Files:
- `docs/PHASE_9_STAGE_3_IMPLEMENTATION_PLAN.md` (this document)
- `backend/alembic/versions/009_resource_telemetry.py`
- `backend/tests/unit/test_sandbox_resilience.py`
- `backend/tests/integration/test_sandbox_telemetry_e2e.py`
- `docs/PHASE_9_STAGE_3_IMPLEMENTATION_REPORT.md`

### Modified Files:
- `backend/app/config.py` (add suite scaling thresholds and limits)
- `backend/app/services/sandbox_service.py` (exit classification, OOM detection, resource extraction, container cleanup)
- `backend/app/agents/state.py` (telemetry fields in `TestRunOutput`)
- `backend/app/services/test_discovery_service.py` (timeout scaler, normalization)
- `backend/app/services/flaky_detector.py` (enhanced infra error filtering)
- `backend/app/agents/specialists/tester.py` (forward telemetry, scale timeouts)
- `backend/app/agents/graph.py` (anti-churn routing on resource exhaustion)
- `backend/app/models/test_run.py` (new telemetry columns)
- `backend/app/schemas/task.py` (telemetry fields in `TestRunResponse`)
- `backend/app/services/workflow_service.py` (persist telemetry and environment failure lessons)
- `frontend/src/types/index.ts` (TypeScript types for telemetry)
- `frontend/src/app/tasks/[id]/page.tsx` (Telemetry metrics card & exit badges)

---

## 7. Testing Strategy

1. **Unit Tests (`test_sandbox_resilience.py`):**
   - Exit code classifications: 0, 124, 126, 127, 137 with confirmed OOM, 137 without OOM (SIGKILL), non-zero.
   - OOM detection with mocked Docker inspect state.
   - Resource telemetry extraction (CPU, memory, wall-clock, limits).
   - Missing/unavailable telemetry handling (no fabrication of zeros).
   - Timeout scaling: $\le 50$ tests, $>50$ tests, ceiling capping at 300s.
   - Container cleanup verification in `finally` blocks.
2. **Integration Tests (`test_sandbox_telemetry_e2e.py`):**
   - Full workflow execution verifying telemetry persistence in `test_runs`.
   - Routing verification: OOM and timeouts route to `reporter` rather than retry loops.
   - Flaky detector isolation: repeat runs ignore infrastructure/resource faults.
3. **Regression Baseline:**
   - All 183 existing backend tests must continue passing.
   - Frontend Next.js production build: 15/15 routes must compile with zero errors.

---

## 8. Security & Sandbox Constraints Verification

- **Host Isolation:** Untrusted repository code is strictly forbidden from running directly on the backend host.
- **Resource Constraints Enforced:** Container limits `--memory 1500m`, `--cpus 2.0`, `--pids-limit 100`, `--network none`, `--cap-drop=ALL` are strictly maintained.
- **Cleanup Guarantee:** Deterministic container names with `docker rm -f` inside `finally` blocks guarantee zero orphaned containers after timeouts, OOMs, or process cancellations.
- **Secret Redaction:** Logs and stderr outputs are sanitized before persistence and telemetry broadcasting.
