# DEVORA AI — PHASE 9, STAGE 9.2 IMPLEMENTATION PLAN
## Flaky Test Detection & Stability Intelligence Engine

**Document Version:** 1.0.0  
**Phase:** 9 (Autonomous Engineering Reliability)  
**Stage:** 9.2 (Flaky Test Detection Engine)  
**Date:** November 19, 2026  
**Status:** Approved for Implementation  

---

### 1. Existing Architecture & Audit Findings

During the architectural audit of Devora AI for Stage 9.2, the following existing interfaces and baselines were verified:

1. **Test Execution & Output Contracts (`backend/app/agents/state.py` & `backend/app/services/test_discovery_service.py`):**
   - Stage 9.1 implemented `TestDiscoveryService` and `NormalizedTestResult`, returning structured counts (`total_tests`, `passed_tests`, `failed_tests`, `skipped_tests`), duration, exit codes, and failure details (`failure_details`).
   - When a test fails in the current system, the Tester agent immediately marks `test_results.passed = False`, triggering the LangGraph `route_after_tester` conditional edge.
   - The edge routes to `retry_incrementer` (bounded retry loop up to 3 times), causing the Coding agent (`coder_node`) to rewrite code even if the test failure was purely non-deterministic (e.g. race condition, timing glitch, port collision).

2. **Sandbox Execution Infrastructure (`backend/app/services/sandbox_service.py`):**
   - `SandboxService` supports isolated execution via `LocalIsolatedRunner` and `DockerSandboxRunner` with timeout, process, and memory constraints.
   - Re-running a command under identical sandbox conditions without modifying the workspace provides the exact controlled environment needed to measure test reproducibility.

3. **Database Architecture & Migrations (`backend/alembic/versions/`):**
   - The current migration head is `007_github_native_engineering`.
   - The next sequential migration is `008_flaky_test_records.py`.
   - PostgreSQL 16 is active on `localhost:5432`.

4. **LangGraph State & Routing (`backend/app/agents/graph.py`):**
   - `route_after_tester` evaluates `test_results`.
   - If tests are confirmed flaky and no deterministic code regressions exist, the workflow should not waste LLM repair loops.

---

### 2. Detection Algorithm & Stability Scoring Specification

#### A. Flakiness Eligibility Filter
Before repeating test executions, filter out failures that cannot be flaky:
- If `passed == True`: Test passed, not eligible for flakiness check.
- If `failure_classification == "RUNNER_UNAVAILABLE"` (exit code 127): Missing tool, not flaky.
- If `failure_classification == "MISSING_DEPENDENCY"`: Uninstalled library, not flaky.
- If `failure_classification == "TIMEOUT"` (and all runs time out): Time budget exceeded, not flaky.
- If sandbox failed to initialize: Infrastructure failure, not flaky.

#### B. Controlled Bounded Repeat Execution
- **Run Count ($N$):** Configurable between 3 and 5 runs (default: 3 runs via `settings.FLAKY_REPEAT_RUNS_DEFAULT`).
- **Execution Invariance:** Identical workspace path, identical test command, identical environment variables, zero LLM code changes between runs.
- **Budget Protection:** Per-test timeout (default: 60s) and total detection budget (default: 180s) preventing runaway processes.

#### C. Stability Scoring Formula
For a given test command across $N$ executions:
$$\text{valid\_executions} = \text{passed\_runs} + \text{failed\_runs}$$
$$\text{stability\_score} = \begin{cases} \left(\frac{\text{passed\_runs}}{\text{valid\_executions}}\right) \times 100, & \text{if } \text{valid\_executions} > 0 \\ 0.0, & \text{otherwise} \end{cases}$$

#### D. Failure Classification Matrix

| Condition | Classification | Routing Action |
|---|---|---|
| All valid runs pass ($\text{stability} = 100\%$) | `STABLE_PASS` | Proceed to Code Review |
| All valid runs fail ($\text{stability} = 0\%$) | `CONSISTENT_FAILURE` | Route to Repair Loop (`retry_incrementer`) |
| Mixed pass and fail ($0\% < \text{stability} < 100\%$) | `FLAKY` | Record Flaky Test, proceed with warning, do not trigger code rewrite |
| Infrastructure/sandbox failures prevent valid runs | `INCONCLUSIVE` | Route to Reporter / Diagnostics |
| No valid executions run | `UNVERIFIED` | Route to Reporter / Diagnostics |

---

### 3. Database Design (Migration 008)

#### Table: `flaky_test_records`
```sql
CREATE TABLE flaky_test_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    test_identifier VARCHAR(500) NOT NULL,
    test_file VARCHAR(500) NOT NULL,
    framework VARCHAR(50) NOT NULL DEFAULT 'pytest',
    language VARCHAR(50) NOT NULL DEFAULT 'python',
    test_command TEXT NOT NULL,
    classification VARCHAR(50) NOT NULL,
    stability_score FLOAT NOT NULL DEFAULT 0.0,
    total_runs INTEGER NOT NULL DEFAULT 0,
    passed_runs INTEGER NOT NULL DEFAULT 0,
    failed_runs INTEGER NOT NULL DEFAULT 0,
    infrastructure_error_runs INTEGER NOT NULL DEFAULT 0,
    timeout_runs INTEGER NOT NULL DEFAULT 0,
    execution_history JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_flaky_test_repo_ident ON flaky_test_records (repository_id, test_identifier);
CREATE INDEX ix_flaky_test_task_id ON flaky_test_records (task_id);
CREATE INDEX ix_flaky_test_classification ON flaky_test_records (classification);
```

---

### 4. Integration Points & New Modules

1. **`FlakyTestDetector` (`backend/app/services/flaky_detector.py`):**
   - Coordinates multi-run repeats, evaluates stability score, extracts test fingerprints, and persists records into PostgreSQL.
2. **`FlakyTestRecord` Model (`backend/app/models/flaky_test_record.py`):**
   - SQLAlchemy 2.0 mapped model linked to `Repository` and `Task`.
3. **Alembic Migration (`backend/alembic/versions/008_flaky_test_records.py`):**
   - Applies table and indexes cleanly to PostgreSQL database.
4. **LangGraph State & Tester Agent Integration:**
   - Update `TestRunOutput` in `backend/app/agents/state.py` with `stability_classification`, `stability_score`, `flaky_runs_summary`.
   - Update `tester_node` in `backend/app/agents/specialists/tester.py` to trigger `FlakyTestDetector` upon test failure.
   - Update `route_after_tester` in `backend/app/agents/graph.py` to bypass `retry_incrementer` if failure is confirmed `FLAKY`.
5. **REST API Endpoints (`backend/app/api/v1/flaky_tests.py`):**
   - `GET /api/v1/repositories/{id}/flaky-tests`: List flaky tests for a repo.
   - `GET /api/v1/tasks/{id}/flaky-tests`: List flaky tests detected in a task.
   - `GET /api/v1/repositories/{id}/test-stability`: Aggregated stability summary.
6. **Frontend Updates (`frontend/src/app/tasks/[id]/page.tsx` & `frontend/src/types/index.ts`):**
   - Display stability score percentage badge, flaky candidate indicator, and repeat execution distribution in the Tests tab.

---

### 5. Security & Resource Protection

1. **No Backend Host Execution:** All repeat runs execute strictly inside the isolated sandbox (`LocalIsolatedRunner` or `DockerSandboxRunner` with `--network none`).
2. **Bounded Repeat Counts:** Hard cap between 3 and 5 runs; no infinite retry loops.
3. **Total Time Budget:** Enforce maximum flaky-detection time budget (180s per task) to prevent timeout exhaustion.
4. **Credential Scrubbing:** Sanitize all tokens, passwords, and sensitive keys from execution history logs.

---

### 6. Testing Strategy

1. **Unit Tests (`backend/tests/unit/test_flaky_detector.py`):**
   - All runs pass ($\text{score} = 100\%$, `STABLE_PASS`).
   - All runs fail ($\text{score} = 0\%$, `CONSISTENT_FAILURE`).
   - Mixed pass/fail ($\text{score} = 66.7\%$, `FLAKY`).
   - Infrastructure error (exit code 127) $\rightarrow$ `INCONCLUSIVE`.
   - Timeout execution $\rightarrow$ `TIMEOUT`.
   - Fingerprint generation and sanitization.
   - Zero valid executions.
2. **Integration Tests (`backend/tests/integration/test_flaky_test_engine.py`):**
   - Real sandbox execution with deterministic pass fixture.
   - Real sandbox execution with deterministic fail fixture.
   - Real sandbox execution with non-deterministic fixture (simulating flaky behavior via file toggle or deterministic state).
   - Database persistence of `FlakyTestRecord` with task and repository relationships.
   - LangGraph routing verification (flaky test bypasses code repair loop).
   - API endpoints verification.
3. **Regression Tests:**
   - Full regression suite ($\ge 161$ passing tests).
   - Next.js production build (15/15 routes compiled with 0 errors).

---

### 7. Acceptance Criteria Checklist

- [x] Initial architecture audited and documented in plan.
- [ ] `FlakyTestDetector` implemented with bounded repeat runs and scoring.
- [ ] Database model `FlakyTestRecord` created and exported.
- [ ] Alembic migration `008_flaky_test_records.py` created and applied.
- [ ] Stability scoring algorithm handles pass, fail, flaky, and inconclusive states.
- [ ] Tester agent integrates flaky detection on eligible test failures.
- [ ] LangGraph routing bypasses code-fix retries on confirmed flaky tests.
- [ ] REST API routes exposed under `/api/v1/repositories/{id}/flaky-tests` and `/tasks/{id}/flaky-tests`.
- [ ] Frontend displays stability scores and repeat run badges.
- [ ] Unit and integration tests pass ($100\%$).
- [ ] Full backend regression suite passes ($\ge 161$ passing tests).
- [ ] Frontend Next.js build compiles cleanly (15/15 routes).
- [ ] Implementation report authored.
