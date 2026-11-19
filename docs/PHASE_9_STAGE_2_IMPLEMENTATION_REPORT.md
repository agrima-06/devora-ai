# DEVORA AI — PHASE 9, STAGE 9.2 IMPLEMENTATION REPORT
## Flaky Test Detection & Stability Intelligence Engine

**Document Version:** 1.0.0  
**Phase:** 9 (Autonomous Engineering Reliability)  
**Stage:** 9.2 (Flaky Test Detection Engine)  
**Completion Date:** November 19, 2026  
**Final Verification Status:** `COMPLETE AND VERIFIED`  

---

### 1. Initial Architecture Audit

Prior to implementation, an audit of the testing and retry architecture revealed:
- **Flaky Vulnerability:** When tests failed due to non-deterministic conditions (concurrency race conditions, timing jitter, socket/port collisions), the system assumed an implementation defect and routed directly to the Coding Agent (`coder_node`) via `retry_incrementer`.
- **Destructive Code Modification:** The LLM repeatedly modified functional code attempting to fix non-existent syntax/logic errors, causing codebase regressions and wasting LLM token budgets.
- **No Historical Stability:** Devora had no memory of historical test flakiness across runs or tasks within a repository.
- **Aggregate Conflation:** Transient timeouts and infrastructure errors were counted identically to deterministic assertion failures.

---

### 2. Detection Algorithm & Workflow

When a test failure occurs during `tester_node`:
1. **Eligibility Evaluation:**
   - Filters out non-eligible outcomes (passing tests, missing test runners with exit code 127, missing project dependencies `ModuleNotFoundError`, zero tests executed).
2. **Fingerprint & Test Identification:**
   - Derives a stable, canonical test identifier across frameworks (e.g. `tests/test_auth.py::test_login`, `TestLogout`, `Button renders`).
3. **Controlled Repeat Execution:**
   - Clamps repeat execution count $N$ between 3 and 5 runs (default: 3 via `settings.FLAKY_REPEAT_RUNS_DEFAULT`).
   - Executes identical command under identical sandbox conditions with zero code modification.
   - Enforces a per-task total flaky detection budget (`settings.FLAKY_TOTAL_TIMEOUT_SECONDS = 180`).
4. **Outcome Aggregation & Stability Scoring:**
   - Categorizes each run into `passed`, `failed`, `is_infra_error`, or `is_timeout`.
   - Computes deterministic stability score and assigns final classification.
5. **Persistence & Adaptive Learning Protection:**
   - Upserts record in `flaky_test_records`.
   - Protects Adaptive Engineering Intelligence by classifying flaky failures as `ENVIRONMENT_PROBLEM` rather than `IMPLEMENTATION_DEFECT`.

---

### 3. Stability-Scoring Explanation & Formula

Let $N$ be the number of repeat executions performed.

$$\text{valid\_executions} = \text{passed\_runs} + \text{failed\_runs}$$

$$\text{stability\_score} = \begin{cases} \left(\frac{\text{passed\_runs}}{\text{valid\_executions}}\right) \times 100, & \text{if } \text{valid\_executions} > 0 \\ 0.0, & \text{otherwise} \end{cases}$$

- Infrastructure errors (exit code 127, missing binary) and timeouts are strictly isolated and not counted as valid pass/fail executions.
- If $\text{valid\_executions} = 0$, the stability score defaults to $0.0\%$ and the classification becomes `INCONCLUSIVE` or `UNVERIFIED`.

---

### 4. Classification Rules

| Classification | Criteria | Action Taken |
|---|---|---|
| `STABLE_PASS` | $\text{passed\_runs} == \text{valid\_executions} > 0$ ($\text{score} = 100\%$) | Proceeds to Code Review |
| `CONSISTENT_FAILURE` | $\text{failed\_runs} == \text{valid\_executions} > 0$ ($\text{score} = 0\%$) | Confirmed defect; routes to repair loop (`retry_incrementer`) |
| `FLAKY` | $\text{passed\_runs} > 0$ and $\text{failed\_runs} > 0$ ($0\% < \text{score} < 100\%$) | Non-deterministic; bypasses code-fix retries to prevent code churn |
| `INCONCLUSIVE` | $\text{infra\_runs} > 0$ or $\text{timeout\_runs} == N$ or $\text{valid\_executions} == 0$ | Routes to environment diagnostics |
| `UNVERIFIED` | $N == 0$ (no runs executed) | Recorded as unverified |

---

### 5. Database Schema

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
    classification VARCHAR(50) NOT NULL DEFAULT 'FLAKY',
    stability_score FLOAT NOT NULL DEFAULT 0.0,
    total_runs INTEGER NOT NULL DEFAULT 0,
    passed_runs INTEGER NOT NULL DEFAULT 0,
    failed_runs INTEGER NOT NULL DEFAULT 0,
    infrastructure_error_runs INTEGER NOT NULL DEFAULT 0,
    timeout_runs INTEGER NOT NULL DEFAULT 0,
    execution_history JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_flaky_test_repo_ident ON flaky_test_records(repository_id, test_identifier);
CREATE INDEX idx_flaky_test_task_id ON flaky_test_records(task_id);
CREATE INDEX idx_flaky_test_classification ON flaky_test_records(classification);
```

---

### 6. Migration Details

- **Migration File:** `backend/alembic/versions/008_flaky_test_records.py`
- **Revision ID:** `008_flaky_test_records`
- **Revises:** `007_github_native_engineering`
- **Execution Evidence:** Applied cleanly via `alembic upgrade head` on PostgreSQL 16.

---

### 7. Services Created

1. **`backend/app/services/flaky_detector.py`**:
   - `FlakyTestDetector`: Core detection engine with `is_eligible_for_flaky_detection`, `extract_test_identifier`, `calculate_stability`, `detect_flakiness`, `record_flaky_test`, `get_repository_flaky_tests`, `get_task_flaky_tests`, and `get_repository_stability_summary`.
   - `FlakyDetectionReport`: Normalized result structure with classification, score, and execution timeline.
   - `SingleExecutionRecord`: Individual run metrics.

---

### 8. Existing Modules Modified

1. **`backend/app/config.py`**: Added `FLAKY_DETECTION_ENABLED`, `FLAKY_REPEAT_RUNS_DEFAULT` (3), `FLAKY_REPEAT_RUNS_MIN` (3), `FLAKY_REPEAT_RUNS_MAX` (5), `FLAKY_TOTAL_TIMEOUT_SECONDS` (180).
2. **`backend/app/models/flaky_test_record.py`**: New SQLAlchemy model linked to `Repository` and `Task`.
3. **`backend/app/models/repository.py` & `backend/app/models/task.py`**: Added `flaky_tests` cascade relationships.
4. **`backend/app/models/__init__.py`**: Exported `FlakyTestRecord`.
5. **`backend/app/agents/state.py`**: Enriched `TestRunOutput` with `stability_classification`, `stability_score`, `is_flaky`, `flaky_repeat_runs`. Added `flaky_test_report` to `DevoraWorkflowState`.
6. **`backend/app/agents/specialists/tester.py`**: Integrated flaky detection into `tester_node`.
7. **`backend/app/agents/graph.py`**: Updated `route_after_tester` to bypass `retry_incrementer` on confirmed flaky tests.
8. **`backend/app/services/workflow_service.py`**: Persists `FlakyTestRecord` on completion; prevents memory contamination.
9. **`frontend/src/types/index.ts`**: Added `FlakyTestRecord` and `RepositoryStabilitySummary` types; enriched `TestRun`.
10. **`frontend/src/services/flaky-service.ts`**: Client service for stability APIs.
11. **`frontend/src/app/tasks/[id]/page.tsx`**: Added Flaky Test Intelligence card and repeat execution breakdown in Tests tab.

---

### 9. LangGraph Integration & Repair Loop Bypass

In `backend/app/agents/graph.py` (`route_after_tester`):
- If `passed == True`: Routes to `code_reviewer`.
- If `failure_classification == "RUNNER_UNAVAILABLE"`: Routes to `reporter`.
- If `is_flaky == True` or `stability_classification == "FLAKY"`:
  - **Bypasses `retry_incrementer`** and routes directly to `code_reviewer`.
  - Prevents the Coding Agent from rewriting working code when the failure was non-deterministic.
- If `CONSISTENT_FAILURE`:
  - Routes to `retry_incrementer` for standard bounded repair loops (up to 3 retries).

---

### 10. API Changes

New endpoints registered under `/api/v1`:
- `GET /api/v1/repositories/{id}/flaky-tests`: List flaky tests for a repository.
- `GET /api/v1/repositories/{id}/test-stability`: Aggregate stability statistics for a repository.
- `GET /api/v1/tasks/{id}/flaky-tests`: List flaky tests detected during a specific task.
- `GET /api/v1/flaky-tests/{id}`: Detailed history for an individual flaky test record.

---

### 11. Frontend Changes

1. **Flaky Test Intelligence Card:** Surfaces an amber alert banner in the Tests tab when flaky tests are detected. Displays test identifier, stability score percentage, pass/fail run counts, and an explanation of the repair loop bypass.
2. **Individual Run Badges:** Displays `FLAKY TEST` badge with exact stability score percentage (e.g. `66.7% Stability`).
3. **SSE Query Invalidation:** Automatically refreshes flaky test queries upon node completion.

---

### 12. Security Controls

- **Zero Host Execution:** All repeat executions run inside isolated containers or path-confined local sandboxes (`LocalIsolatedRunner`).
- **Bounded Repeat Limits:** Hard capped between 3 and 5 runs.
- **Total Time Budget:** Enforces 180s total timeout budget for flakiness detection to prevent denial of service.
- **Log Sanitization:** All tokens (GitHub `ghp_`, Google `AIza`, JWT `Bearer`) are scrubbed before persistence.

---

### 13. Unit Test Results

- **File:** `backend/tests/unit/test_flaky_detector.py`
- **Tests Executed:** **16 passed in 0.03s** (100% pass rate).
- **Coverage:** Eligibility filters, all pass, all fail, mixed pass/fail, infrastructure errors, timeouts, zero executions, fingerprint extraction across Pytest/Unittest/Jest/Go/Cargo, credential sanitization.

---

### 14. Integration Test Results

- **File:** `backend/tests/integration/test_flaky_test_engine.py`
- **Tests Executed:** **5 passed in 7.08s** (100% pass rate).
- **Coverage:**
  1. Real sandbox execution of a consistent failure fixture (`CONSISTENT_FAILURE`, 0.0% stability).
  2. Real sandbox execution of a controlled non-deterministic fixture (`FLAKY`, 66.7% stability).
  3. LangGraph routing bypass verification (`route_after_tester` routes to `code_reviewer` instead of `retry_incrementer`).
  4. Database persistence and repository summary calculation.
  5. REST API routes integration (`/flaky-tests`, `/repositories/{id}/flaky-tests`, etc.).

---

### 15. Backend Regression Results

- **Command:** `DEVORA_SANDBOX_RUNNER=local .venv/bin/pytest backend/tests -q`
- **Result:** **183 passed, 3 skipped in 64.07s** (100% success rate).
- **Regression Analysis:** 0 regressions across all 161 previously established tests. Total passing test count increased from 161 to 183 (+22 tests).

---

### 16. Frontend Build Results

- **Command:** `npm run build --prefix frontend`
- **Result:** **15 of 15 static and dynamic routes compiled cleanly** with zero TypeScript or ESLint errors.

---

### 17. Known Limitations

1. **Test Runner Concurrency:** Repeat runs execute sequentially within the sandbox. Parallel execution of repeat runs inside isolated worker sub-processes is scheduled for Stage 9.3.
2. **Dynamic Flakiness Healing:** Tracking whether a previously flaky test has become permanently stable over time across multiple git commits will be extended in Stage 9.6 (Reliability Observability Console).

---

### 18. Commands Required to Reproduce Verification

```bash
# 1. Run unit and integration tests for Stage 9.2
DEVORA_SANDBOX_RUNNER=local .venv/bin/pytest backend/tests/unit/test_flaky_detector.py backend/tests/integration/test_flaky_test_engine.py -v

# 2. Run complete backend regression suite
DEVORA_SANDBOX_RUNNER=local .venv/bin/pytest backend/tests -q

# 3. Build Next.js frontend
npm run build --prefix frontend
```

---

### 19. Acceptance Checklist

- [x] Existing architecture audited and documented in plan.
- [x] `FlakyTestDetector` implemented with bounded repeat runs and scoring.
- [x] Database model `FlakyTestRecord` created and exported.
- [x] Alembic migration `008_flaky_test_records.py` created and applied.
- [x] Stability scoring algorithm handles pass, fail, flaky, and inconclusive states.
- [x] Tester agent integrates flaky detection on eligible test failures.
- [x] LangGraph retry routing bypasses code-fix retries on confirmed flaky tests.
- [x] REST API routes exposed under `/api/v1/repositories/{id}/flaky-tests` and `/tasks/{id}/flaky-tests`.
- [x] Frontend displays stability scores and repeat run badges.
- [x] Unit tests pass ($100\%$).
- [x] Available integration tests pass ($100\%$).
- [x] Existing backend regressions resolved (183 passed).
- [x] Frontend production build succeeds (15/15 routes).
- [x] Documentation updated (`ARCHITECTURE.md`, `DATABASE.md`, `API.md`, `IMPLEMENTATION_PLAN.md`).
- [x] Implementation report generated.

---

### 20. Explicit Completion Status

**Status:** `COMPLETE AND VERIFIED`
