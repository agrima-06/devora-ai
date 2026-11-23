# Phase 9, Stage 9.6: Reliability Observability Console Implementation Plan

## 1. Architectural Context & Current Baseline

Devora AI has completed Stages 9.1 through 9.5 of Phase 9 (Autonomous Engineering Reliability):
- **Stage 9.1:** Multi-Language Test Discovery & Execution Engine (Python, JS, TS, Go, Rust, Java; targeted test selection, standardized test results).
- **Stage 9.2:** Flaky Test Detection & Stability Intelligence Engine (repeat sandbox executions, deterministic stability scoring, historical persistence in `flaky_test_records`, code-revision bypass).
- **Stage 9.3:** Sandbox Resilience, OOM Classification & Resource Telemetry (`SandboxExitClassifier`, empirical peak RSS and CPU/wall-time tracking, SIGKILL vs OOM differentiation, dynamic timeout scaling).
- **Stage 9.4:** Workflow Recovery Manager & Safe Autonomous Task Resumption (granular checkpoints in `workflow_checkpoints`, heartbeat interruption detection, distributed atomic leases, resume endpoint `POST /tasks/{id}/resume`, approval gate protection).
- **Stage 9.5:** Model Gateway Circuit Breakers & Fallback Resilience (per-model circuit breaker FSM, full-jitter exponential backoff retries, HTTP 429 `retry_after`, capability-aware fallback cascade, `model_gateway_health` table).

**Current Verification Baseline:**
- Backend: **249 passed, 0 failed, 0 skipped** across all unit and integration tests.
- Frontend: **15/15 Next.js 14 routes** compiled cleanly with 0 TypeScript/lint errors.
- Alembic Head Revision: `011_model_gateway_resilience`.

---

## 2. Missing Operational Visibility & Problem Statement

While each reliability subsystem is functional and persisted, operational visibility is currently fragmented across disparate pages:
1. **No Single-Pane System Health Overview:** An operator cannot see at a glance whether the Sandbox runner, Model Gateway, Test Discovery, or Recovery Manager are operating nominally or degraded.
2. **Disconnected Telemetry:** Sandbox resource usage (peak RSS, OOMs, timeouts) lives in `test_runs`; stability intelligence lives in `flaky_test_records`; recovery leases live in `tasks`; gateway health lives in `model_gateway_health`; and event streams live in `workflow_events`.
3. **Recovery Friction:** Finding interrupted or recovery-eligible tasks currently requires checking individual task pages or running a manual scan endpoint.
4. **No Unified Event Timeline:** Operational events (circuit breaker trips, OOM kills, flaky test detections, recovery events) cannot be filtered by subsystem or severity in one chronological audit stream.
5. **Deployment Topology Transparency:** The in-memory vs database-persisted nature of the Model Gateway circuit breaker must be clearly surfaced so operators understand multi-worker isolation characteristics.

---

## 3. Architecture of the Reliability Observability Console

### 3.1 Backend Aggregation Architecture

We will create a specialized, read-optimized backend aggregation service:
- **`backend/app/services/reliability_service.py` (`ReliabilityService`):**
  - Single-query SQL aggregations using SQLAlchemy `func.count()`, `func.avg()`, `func.sum()`, and `CASE WHEN` constructs to prevent $N+1$ queries.
  - Subsystem Health Evaluation:
    - **Workflow Engine:** Evaluates running task heartbeats and recent failure ratios.
    - **Agent Execution:** Evaluates specialist agent run failure rates.
    - **Sandbox Runner:** Evaluates container execution success rates, startup failure rates, and runner availability.
    - **Test Stability:** Evaluates ratio of stable vs flaky tests in `flaky_test_records`.
    - **Workflow Recovery:** Evaluates active leases, interrupted tasks count, and recovery attempt success rate.
    - **Model Gateway:** Queries `ModelHealthService` and `model_gateway_health` for open breakers, degraded models, and average latency.
    - **GitHub Integration:** Inspects GitHub App installation status and recent sync activity.
  - Subsystem status levels: `HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `UNKNOWN`. (Never falsely marks a system healthy without verified activity).
  - Secret scrubbing (`scrub_credentials`) on all diagnostic messages and event payloads.

### 3.2 REST API Endpoints (`/api/v1/reliability/`)

- **`GET /api/v1/reliability/overview`:**
  - Authenticated endpoint returning:
    - Subsystem health indicators with timestamps and failure reasons.
    - Workflow reliability metrics (total, running, completed, failed, interrupted, awaiting approval, recovery success rate, average duration).
    - Sandbox reliability metrics (passed, failed, OOMs, timeouts, SIGKILLs, runner unavailable, avg RSS, max memory limit utilization, CPU times).
    - Test stability summary (stable, flaky, consistent failures, inconclusive, average stability score).
    - Model Gateway metrics (active models, fallbacks, breaker states, retry counts, latency, deployment topology disclosure).
    - Recovery operations summary (interrupted count, eligible count, in-progress count, manual intervention required count).
- **`GET /api/v1/reliability/events`:**
  - Paginated audit stream queried from `workflow_events` joined with `tasks`.
  - Filters: `subsystem` (e.g., `model_gateway`, `sandbox`, `workflow`, `tester`, `recovery`), `severity` (`INFO`, `WARNING`, `ERROR`, `CRITICAL`), `task_id`, `repository_id`, `start_date`, `end_date`, `limit`, `offset`.
  - Enforces tenant isolation (scoped to authenticated user's projects/repositories).
- **`GET /api/v1/reliability/trends`:**
  - Bounded time-series aggregation (e.g. 24 hours, 7 days, 30 days) of task completions, failures, recovery operations, sandbox OOMs, and flaky test counts.

### 3.3 Model Gateway Distributed-State Topology Audit & Disclosure

- **Findings:**
  - `CircuitBreakerRegistry` holds in-memory `CircuitBreaker` instances on the active FastAPI application process.
  - State changes and metrics are synchronized asynchronously to the PostgreSQL `model_gateway_health` table.
  - In a single-process deployment (default local and containerized single-replica), the in-memory breaker acts as an authoritative, zero-latency circuit breaker.
  - In a multi-worker deployment (e.g., multiple Uvicorn workers), each worker maintains its local in-memory failure count and probe limits, while database reads reflect the latest synchronized metrics.
- **Observability Action:**
  - Surface this explicitly in the Model Gateway health telemetry schema (`multi_worker_shared_state: False`, `deployment_model: "PROCESS_LOCAL_WITH_DB_SYNC"`).
  - Display an informational indicator in the UI: *"Process-Local Breaker with DB Telemetry Sync — Worker instances independently enforce trip thresholds"*.
  - No false claims of distributed coordination will be made.

### 3.4 Workflow State Consistency Invariants

The reliability aggregation service will strictly enforce Devora's canonical state machine:
1. **Interrupted:** Task has `status == "FAILED"` or has an expired heartbeat ($>120\text{s}$) with `recovery_status == "INTERRUPTED"`.
2. **Terminal Completed:** Task has `status == "COMPLETED"`. Must **never** be classified as interrupted or eligible for resumption.
3. **Terminal Cancelled:** Task has `status == "CANCELLED"`. Must **never** be eligible for resumption.
4. **Approval Gate Protected:** Task has `status == "WAITING_APPROVAL"`. Must **never** be resumed via standard recovery; must only proceed through explicit human approval (`/tasks/{id}/approval`).
5. **Recovery In-Progress:** Task has active, unexpired lease (`recovery_lease_expires_at > now()`). Distinguished from normal execution and displayed with lease owner.
6. **Manual Intervention Required:** Task has `recovery_attempts >= 3` or `recovery_status == "MANUAL_INTERVENTION_REQUIRED"`. UI must explain that maximum automated recovery attempts were exhausted rather than displaying a standard resume button.

---

## 4. Frontend Reliability Console (`/reliability`)

- **Route:** `frontend/src/app/reliability/page.tsx`
- **Navigation:** Added to `Sidebar` in `frontend/src/components/layout/sidebar.tsx` with `ShieldCheck` icon.
- **Console Layout & Sections:**
  1. **Header & Global Status Bar:**
     - High-level system resilience banner.
     - Global SSE connectivity pill (`Live SSE` / `Polling Fallback`).
     - Quick filter by repository and date range.
  2. **Subsystem Health Grid:**
     - 8 health cards: Workflow Engine, Agent Roster, Sandbox Runner, Test Discovery, Flaky Detector, Workflow Recovery, Model Gateway, GitHub App.
     - Indicators: `HEALTHY` (emerald), `DEGRADED` (amber), `UNAVAILABLE` (rose), `UNKNOWN` (slate).
     - Timestamps of last activity and diagnostic failure reasons.
  3. **Workflow & Sandbox Reliability Metric Panels (2-column grid):**
     - Left: Workflow task breakdown (running, completed, failed, interrupted, recovery success rate, attempt distribution).
     - Right: Sandbox execution telemetry (OOM kills, timeouts, generic kills, runner unavailable, average RSS, memory quota utilization).
  4. **Test Stability & Model Gateway Resilience (2-column grid):**
     - Left: Test stability statistics, flaky tests breakdown, average stability score.
     - Right: Model Gateway telemetry, active/fallback models, breaker status pills, latency, retry counts, process-local disclosure pill.
  5. **Recovery Operations Command Panel:**
     - Table of currently interrupted, recovering, or recovery-eligible tasks.
     - Shows checkpoint node, step number, heartbeat age, and lease status.
     - One-click **Resume Task** action button for eligible tasks (with loading state and confirmation).
     - Explanation badge for tasks requiring manual intervention (e.g. max attempts exceeded).
  6. **Unified Event Timeline:**
     - Paginated audit log of reliability events.
     - Filterable by subsystem (`Workflow`, `Sandbox`, `Tester`, `ModelGateway`, `Recovery`) and severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`).
     - Timestamp, task link, repository link, diagnostic message, and expandable payload.
- **Real-Time Integration:**
  - Listens to SSE broadcast stream from active tasks.
  - Event-specific query invalidations:
    - `MODEL_*` invalidates model health and events.
    - `SANDBOX_*` or `TEST_*` invalidates sandbox and stability telemetry.
    - `RECOVERY_*` invalidates recovery panel and workflow metrics.
  - Fallback polling every 30 seconds if SSE disconnects.

---

## 5. Security, Authorization & Privacy

1. **Authentication:** All reliability endpoints require a valid JWT bearer token (`Depends(get_current_user)`).
2. **Tenant Scoping:** All aggregations filter against `tasks.created_by == user.id` or user-owned repositories/projects.
3. **Secret Redaction:** `scrub_credentials` ensures zero API keys, GitHub tokens, or bearer headers are returned in diagnostic payloads.
4. **Approval Gate Invariance:** Resuming a task from the console can never bypass human approval; if an interrupted task is past code generation, it strictly lands at `WAITING_APPROVAL`.

---

## 6. Files to Create and Modify

### Backend
- **Create:** `backend/app/schemas/reliability.py` (Pydantic models for overview, events, trends).
- **Create:** `backend/app/services/reliability_service.py` (SQL aggregation logic and health evaluation).
- **Create:** `backend/app/api/v1/reliability.py` (REST endpoints).
- **Modify:** `backend/app/schemas/__init__.py` (export reliability schemas).
- **Modify:** `backend/app/api/v1/router.py` (include `reliability_router`).
- **Create:** `backend/tests/unit/test_reliability_service.py` (unit tests for aggregation and health checks).
- **Create:** `backend/tests/integration/test_reliability_api.py` (integration tests for `/reliability/*` endpoints).

### Frontend
- **Create:** `frontend/src/services/reliability-service.ts` (API client methods).
- **Modify:** `frontend/src/types/index.ts` (TypeScript interfaces for reliability overview, events, metrics).
- **Modify:** `frontend/src/components/layout/sidebar.tsx` (add `/reliability` navigation item).
- **Create:** `frontend/src/app/reliability/page.tsx` (Unified Reliability Observability Console).

### Documentation
- **Modify:** `docs/ARCHITECTURE.md` (add Section 15: Reliability Observability Console).
- **Modify:** `docs/API.md` (add Section 10: Reliability Observability APIs).
- **Modify:** `docs/IMPLEMENTATION_PLAN.md` (mark Stage 9.6 completed).
- **Create:** `docs/PHASE_9_STAGE_6_IMPLEMENTATION_REPORT.md` (comprehensive final report).

---

## 7. Testing & Verification Strategy

1. **Unit Tests:**
   - Verify health evaluation logic handles zero records, nominal records, degraded records, and failure states without false `HEALTHY` attribution.
   - Verify state consistency checks: completed/cancelled tasks cannot be marked eligible, lease conflicts are detected.
2. **Integration Tests:**
   - Test `GET /api/v1/reliability/overview` returns valid aggregated data matching PostgreSQL records.
   - Test `GET /api/v1/reliability/events` with subsystem, severity, and pagination filters.
   - Test `GET /api/v1/reliability/trends` across bounded date ranges.
   - Test resumption triggering from the recovery panel.
3. **Regression Suite:**
   - Execute full backend test suite (`pytest backend/tests/ -v`). Target: $\ge 265$ passing, 0 failed, 0 skipped.
   - Execute frontend production build (`npm run build` in `frontend/`). Target: 16/16 routes compiled cleanly.
