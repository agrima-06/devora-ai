# Devora AI — Phase 10 Stage 10.7 Implementation Plan
## Autonomous Engineering Intelligence Evaluation & Benchmarking Engine

**Document Date:** November 23, 2026  
**Implementation Phase:** Phase 10 (Advanced Repository Intelligence)  
**Stage:** 10.7 (Evaluation & Benchmarking Engine — Final Phase 10 Closure)  
**Status:** APPROVED FOR EXECUTION  

---

## 1. Baseline Architecture & Repository Audit

### 1.1 Existing Architecture
- **Backend:** FastAPI, Python 3.14.6, SQLAlchemy 2.0 (async), PostgreSQL 16 + pgvector.
- **Frontend:** Next.js 14 (App Router), React 18, TailwindCSS, React Query.
- **Repository Intelligence:**
  - Stage 10.1: Cross-File Symbol and Dependency Graph Engine (`RepositoryGraphNode`, `RepositoryGraphEdge`).
  - Stage 10.2: Blast Radius and Change Impact Analysis Engine (`ImpactAnalysisService`).
  - Stage 10.3: Monorepo & Workspace Intelligence Engine (`WorkspaceService`).
  - Stage 10.4: Semantic Architecture & Pattern Inference Engine (`ArchitectureInferenceService`, `search_hybrid`).
  - Stage 10.5: Architectural Drift & Technical Debt Engine (`ArchitectureDriftService`, `TechnicalDebtService`).
  - Stage 10.6: Architecture-Aware Refactoring & Safe Remediation Engine (`ArchitectureAwareRefactoringService`).
- **Baseline Verification:**
  - Backend: **323 passed, 0 failed, 3 skipped**.
  - Frontend: **16/16 routes compiled cleanly**.
  - Current Alembic Revision: `015_refactoring_engine`.
  - Security Working Tree: **100% clean (0 secrets detected)**.

---

## 2. Stage 10.6 Audit Remediations (Pre-Implementation Hardening)

Before introducing Stage 10.7 code, the following three items identified during the Stage 10.6 final audit will be hardened:
1. **Automated Rollback on Verification Failure:**
   - Extend `ArchitectureAwareRefactoringService.execute_plan()` to evaluate test outcomes and induced regressions.
   - When a regression is detected (`post_tests_passed=False` or `newly_failed_tests > 0`), automatically mark `execution.status = "ROLLED_BACK"`, set `execution.rollback_occurred = True` with `rollback_reason`, and revert `plan.execution_status = "ROLLED_BACK"`.
2. **Test-Outcome Preservation (Identity Deltas):**
   - Update `RefactoringExecutionResponse` and `BeforeAfterComparisonResponse` schemas in `backend/app/schemas/refactoring.py` to include:
     - `passed_test_ids_before: List[str]`
     - `passed_test_ids_after: List[str]`
     - `newly_failed_tests: List[str]`
     - `removed_tests: List[str]`
     - `test_coverage_delta: float`
   - Enforce that a refactoring with any newly failing test is classified as `REGRESSION_DETECTED` and rolled back, regardless of aggregate pass counts.
3. **Immutable Approval Binding Snapshot Hash:**
   - Update `approve_plan()` and `execute_plan()` to bind repository `source_revision`, target file hashes, and planned transformations into the cryptographic diff hash.

---

## 3. Database Architecture & Alembic Migration (Revision 016)

### 3.1 Tables to Deploy
- **Table 34: `benchmark_scenarios`**
  - Columns: `id` (VARCHAR PK), `category` (VARCHAR), `name` (VARCHAR), `description` (TEXT), `difficulty` (VARCHAR: BASIC/INTERMEDIATE/ADVANCED/EXPERT), `language` (VARCHAR), `framework` (VARCHAR), `initial_state` (TEXT), `task_prompt` (TEXT), `expected_outcomes` (JSONB), `evaluation_criteria` (JSONB), `dataset_version` (VARCHAR), `is_deterministic` (BOOLEAN), `created_at`, `updated_at`.
- **Table 35: `benchmark_suite_runs`**
  - Columns: `id` (UUID PK), `suite_id` (VARCHAR), `dataset_version` (VARCHAR), `system_version` (VARCHAR), `model_version` (VARCHAR), `status` (VARCHAR: PENDING/RUNNING/COMPLETED/FAILED/CANCELLED), `overall_score` (FLOAT), `category_scores` (JSONB), `critical_safety_failure` (BOOLEAN), `critical_failure_reason` (TEXT), `scenarios_total` (INTEGER), `scenarios_passed` (INTEGER), `scenarios_failed` (INTEGER), `total_tokens` (INTEGER), `estimated_cost_usd` (FLOAT), `duration_ms` (INTEGER), `created_by` (UUID REFERENCES users), `created_at`, `updated_at`.
- **Table 36: `benchmark_scenario_results`**
  - Columns: `id` (UUID PK), `run_id` (UUID REFERENCES benchmark_suite_runs), `scenario_id` (VARCHAR REFERENCES benchmark_scenarios), `category` (VARCHAR), `passed` (BOOLEAN), `score` (FLOAT), `evaluation_method` (VARCHAR), `actual_outcome` (JSONB), `evidence` (JSONB), `failure_category` (VARCHAR), `duration_ms` (INTEGER), `tokens_used` (INTEGER), `test_deltas` (JSONB), `created_at`.
- **Table 37: `benchmark_regressions`**
  - Columns: `id` (UUID PK), `current_run_id` (UUID), `baseline_run_id` (UUID), `metric_name` (VARCHAR), `previous_value` (FLOAT), `current_value` (FLOAT), `delta` (FLOAT), `percentage_change` (FLOAT), `severity` (VARCHAR: LOW/MEDIUM/HIGH/CRITICAL), `affected_scenarios` (JSONB), `evidence` (TEXT), `created_at`.

### 3.2 Alembic Migration
- **Revision String:** `016_benchmark_engine` (22 characters, strictly compliant with PostgreSQL `VARCHAR(32)` constraint for `alembic_version.version_num`).

---

## 4. Benchmark Taxonomy & Initial Suite (31 Scenarios Across 7 Categories)

| Category | Target Count | Scenarios Included |
| :--- | :--- | :--- |
| **Category A: Bug Detection & Resolution** | 5 | `BM-BUG-SYNTAX-01` (Unclosed bracket in router)<br>`BM-BUG-RUNTIME-02` (ZeroDivision in billing)<br>`BM-BUG-ASYNC-03` (Unawaited coroutine in loop)<br>`BM-BUG-CONTRACT-04` (Pydantic schema field mismatch)<br>`BM-BUG-DEP-05` (Incompatible version conflict) |
| **Category B: Repository Understanding** | 5 | `BM-REPO-MONO-01` (Monorepo workspace discovery)<br>`BM-REPO-SYM-02` (AST symbol completeness)<br>`BM-REPO-GRAPH-03` (Cross-file dependency classification)<br>`BM-REPO-CIRCULAR-04` (Unresolved cyclic imports)<br>`BM-REPO-CALLGRAPH-05` (API-to-DB call graph hops) |
| **Category C: Architecture Intelligence** | 4 | `BM-ARCH-PATTERN-01` (Confirmation of Layered Architecture)<br>`BM-ARCH-DRIFT-02` (Route DB query layering drift)<br>`BM-ARCH-CONV-03` (Discovered naming conventions)<br>`BM-ARCH-DEBT-04` (Deterministic debt score calibration) |
| **Category D: Change Impact Analysis** | 4 | `BM-IMPACT-DIRECT-01` (Direct model modification blast radius)<br>`BM-IMPACT-TRANS-02` (Transitive utility blast radius)<br>`BM-IMPACT-FALSEPOS-03` (Sibling module pruning)<br>`BM-IMPACT-TESTREC-04` (Targeted test recommendation accuracy) |
| **Category E: Autonomous Refactoring** | 5 | `BM-REFACT-SERVICE-01` (Extract domain service cleanly)<br>`BM-REFACT-CYCLE-02` (Break circular dependency via interface)<br>`BM-REFACT-DIFFHASH-03` (Invalidation on working tree drift)<br>`BM-REFACT-REGRESS-04` (Automatic rollback on test regression)<br>`BM-REFACT-API-05` (Public API signature parity check) |
| **Category F: Multi-Agent Workflow Quality** | 4 | `BM-AGENT-HANDOFF-01` (Investigator to Planner handoff)<br>`BM-AGENT-REVIEW-02` (Scope boundary enforcement in review)<br>`BM-AGENT-RECOVERY-03` (Checkpoint recovery after failure)<br>`BM-AGENT-REPORT-04` (Evidence-grounded final reporting) |
| **Category G: Security and Safety** | 4 | `BM-SEC-SECRET-01` (Synthetic API key blocking)<br>`BM-SEC-APPROVAL-02` (Approval gating on security files)<br>`BM-SEC-TENANT-03` (Tenant isolation 404 enforcement)<br>`BM-SEC-INJECTION-04` (Commit prompt injection resistance) |
| **Total Suite** | **31** | **Comprehensive coverage of all Devora AI capabilities** |

---

## 5. Evaluation & Scoring Engine

### 5.1 Weighted Composite Formula
$$\text{OverallScore} = 0.30 F_{\text{correct}} + 0.15 R_{\text{under}} + 0.15 A_{\text{intel}} + 0.15 S_{\text{refact}} + 0.15 S_{\text{sec}} + 0.05 O_{\text{rel}} + 0.05 E_{\text{eff}}$$

### 5.2 Critical Safety Override Guarantee
If any scenario in Category G (Security/Safety) fails, or if an approval bypass, tenant-isolation breach, or unsafe code execution is detected:
- `critical_safety_failure = True`
- `status = "CRITICAL_SAFETY_FAILURE"`
- The run is permanently flagged as unsafe, preventing high aggregate scores from masking security vulnerabilities.

---

## 6. REST API Endpoints (`/api/v1/benchmarks`)

1. `GET /overview` — High-level benchmark health, latest run score, pass rates, and cost telemetry.
2. `GET /suites` — List available benchmark suites and metadata.
3. `GET /scenarios` — Query versioned benchmark scenarios with category/difficulty filters.
4. `GET /scenarios/{id}` — Retrieve detailed benchmark scenario definition and ground-truth criteria.
5. `POST /runs` — Trigger an asynchronous or synchronous benchmark execution run.
6. `GET /runs` — List historical benchmark runs with pagination.
7. `GET /runs/{id}` — Retrieve run summary, score breakdown, and critical safety status.
8. `POST /runs/{id}/cancel` — Safely terminate an in-progress benchmark execution.
9. `GET /runs/{id}/results` — List scenario-level execution results with test deltas and evidence.
10. `GET /runs/{id}/report` — Generate an audit-ready Markdown evaluation report.
11. `POST /compare` — Compare two benchmark runs and compute metric deltas.
12. `GET /regressions` — Retrieve historical regressions identified across system revisions.

---

## 7. Frontend Benchmark Intelligence Console (`/benchmarks`)

- **Route:** `frontend/src/app/benchmarks/page.tsx`
- **Navigation:** Added to sidebar navigation.
- **Console Views:**
  1. **Overview Hero:** Displays overall intelligence score (0-100), latest run status, critical failure alerts, pass rates, token cost, and execution duration.
  2. **Category Performance Grid:** 7 progress cards detailing category scores and pass ratios.
  3. **Suite Execution Launcher:** Modal/controls to select suite, model version, and trigger/cancel executions.
  4. **Results Explorer:** Scenario results table with expandable detail view showing expected vs actual outcomes, test deltas, and evidence logs.
  5. **Historical Comparison & Regression Alerts:** Side-by-side run comparison with red/green metric delta badges.
  6. **Security & Safety Audit Tab:** Highlights critical safety gates, credential protection, and tenant isolation metrics.
  7. **Exportable Report Generator:** Instant download or preview of audit-ready Markdown report.

---

## 8. Testing Strategy

1. **Unit Tests (`test_benchmark_engine.py`):**
   - Registry seeding and scenario taxonomy completeness (31 scenarios across 7 categories).
   - Scoring engine formula and weighting calculation.
   - Critical safety failure override.
   - Evaluator accuracy (exact match, structural, dependency graph, test outcome deltas).
   - Regression detector calculation and severity classification.
2. **Integration Tests (`test_benchmark_api.py`):**
   - Complete API lifecycle (overview $\to$ scenarios $\to$ execute run $\to$ fetch results $\to$ compare $\to$ generate report).
   - Tenant isolation on benchmark runs and results.
   - Cancellation endpoint handling.
3. **End-to-End Tests (`test_benchmark_e2e.py`):**
   - All 10 required demonstration workflows covering bug resolution, architecture, impact, refactoring rollback, security blocking, and regression alerts.
4. **Full Regression Suite:**
   - Run complete suite ($\ge 330+$ backend tests).
   - Frontend production build verification (`npm run build`, 17/17 routes).
   - Security scanner verification (0 secrets in working tree).

---

## 9. Boundary Enforcement

- Strictly execute Stage 10.7 only.
- Do not begin Phase 11 or any subsequent stage.
- Produce consolidated Phase 10 completion report upon verification.
