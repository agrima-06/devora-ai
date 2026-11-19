# DEVORA AI — PHASE 9, STAGE 9.1 IMPLEMENTATION PLAN
## Multi-Language Test Discovery & Execution Engine

**Document Version:** 1.0.0  
**Phase:** 9 (Autonomous Engineering Reliability)  
**Stage:** 9.1 (Multi-Language Test Discovery & Execution Engine)  
**Date:** November 19, 2026  
**Status:** Approved for Implementation  

---

### 1. Existing Architecture & Audit Findings

During the preliminary repository audit of Devora AI, the following existing components, interfaces, and limitations were identified:

1. **Tester Agent (`backend/app/agents/specialists/tester.py`):**
   - Currently hardcodes Python execution: checks if `(workspace_path / "tests").exists()` and runs `pytest -v tests` or `pytest`.
   - Parses stdout using simple regex for `X passed, Y failed`.
   - Completely unaware of JavaScript/TypeScript, Go, Rust, or Java.
   - Ignores `applied_file_changes` and always attempts a full test run.
   - Treats unavailable tools or missing dependencies as standard code test failures, triggering unnecessary code revision loops.

2. **LangGraph State & Contracts (`backend/app/agents/state.py`):**
   - `TestRunOutput`: Contains `command`, `exit_code`, `passed`, `total_tests`, `passed_tests`, `failed_tests`, `duration_seconds`, `raw_stdout`, `raw_stderr`, `failure_details`.
   - `DevoraWorkflowState`: Contains `workspace_path`, `applied_file_changes`, `test_results`, `last_test_stdout`, `last_test_stderr`, `last_test_exit_code`, `retry_count`, `maximum_retries`.
   - Extensible without breaking downstream nodes (`code_reviewer_node`, `reporter_node`).

3. **Sandbox Execution Infrastructure (`backend/app/services/sandbox_service.py`):**
   - `DockerSandboxRunner`: Enforces strict container isolation (`--network none`, `--memory 1500m`, `--cpus 2.0`, `--pids-limit 100`, `--security-opt=no-new-privileges:true`, `--cap-drop=ALL`).
   - `LocalIsolatedRunner`: Enforces path confinement and command whitelist via `ALLOWED_PREFIXES`. Currently restricted to Python binaries (`pytest`, `python`, `ruff`, `mypy`). Needs expansion to support `npm`, `npx`, `yarn`, `pnpm`, `go`, `cargo`, `mvn` while maintaining strict injection prevention (`&&`, `||`, `;`, backticks, command substitutions).

4. **Workflow Execution & SSE Events (`backend/app/services/workflow_service.py`):**
   - Orchestrates the graph via `astream`.
   - Emits SSE events: `AGENT_TESTER_COMPLETED` with `node_output`.
   - Persists `TestRun` records in PostgreSQL.
   - Triggers `adaptive_service.record_task_failure` on test failures.

5. **Frontend Task Workspace (`frontend/src/app/tasks/[id]/page.tsx`):**
   - Renders `TestRun` records in the "Tests" tab: `passed`/`failed` badge, duration, exit code, total/passed/failed counts, stdout/stderr.
   - Role description in `AGENT_ROSTER` lists `Isolated Sandbox Pytest Runner`. Needs enhancement for multi-language display.

---

### 2. Integration Points & New Modules

#### A. New Module: `TestDiscoveryService`
- **Location:** `backend/app/services/test_discovery_service.py`
- **Responsibilities:**
  - **Language Detection:** Detects Python, JavaScript, TypeScript, Go, Rust, and Java based on root and subfolder manifests (`pyproject.toml`, `package.json`, `tsconfig.json`, `go.mod`, `Cargo.toml`, `pom.xml`) and source file presence.
  - **Manifest Inspection:** Parses configuration files and lockfiles to identify package managers (`pip`, `uv`, `poetry`, `npm`, `yarn`, `pnpm`, `go`, `cargo`, `mvn`).
  - **Framework Discovery:**
    - Python: `pytest` vs `unittest` (detects `[tool.pytest]`, `pytest.ini`, or unittest `TestCase` patterns).
    - JavaScript/TypeScript: `Jest` vs `Vitest` (inspects `package.json` scripts and dependencies).
    - Go: `go test`.
    - Rust: `cargo test`.
    - Java: Maven test (`pom.xml` surefire plugin or standard test layout).
  - **Test File Discovery:** Scans test files according to framework patterns while strictly ignoring `.venv`, `node_modules`, `vendor`, `target`, `dist`, `.git`, `.next`.
  - **Targeted Test Selection:** Maps modified files (`applied_file_changes`) to corresponding test files using naming conventions (`test_<name>.py`, `<name>_test.py`, `<name>.test.ts`, `<name>.spec.js`, `<name>_test.go`, `<Name>Test.java`) and directory proximity.
  - **Fallback Strategy:** If no targeted tests match modified files, falls back safely to the primary suite or full package test.
  - **Normalized Output:** Generates structured `DiscoveredSuite` and `TestExecutionPlan`.

#### B. Enhancements to `SandboxService` & `LocalIsolatedRunner`
- **Location:** `backend/app/services/sandbox_service.py`
- **Modifications:**
  - Safely extend `LocalIsolatedRunner.ALLOWED_PREFIXES` to include: `npm`, `npx`, `yarn`, `pnpm`, `go`, `cargo`, `mvn`.
  - Retain strict command injection sanitization (block `&&`, `||`, `;`, `$(`, `${`, backticks, newlines).
  - Add missing tool detection: verify if required executable exists in the runtime environment before running, returning an explicit `UNAVAILABLE` status if absent.

#### C. Enhancements to `tester_node` & Normalized Test Results
- **Location:** `backend/app/agents/specialists/tester.py`
- **Modifications:**
  - Instantiate `TestDiscoveryService`.
  - Extract `applied_file_changes` from `state`.
  - Perform test discovery and plan targeted or full test execution.
  - Run command in sandbox with appropriate timeouts.
  - Normalize stdout/stderr across all supported frameworks into `TestRunOutput`:
    - `pytest`: regex for `X passed, Y failed`.
    - `unittest`: regex for `Ran X tests in ... OK` or `FAILED (failures=Y, errors=Z)`.
    - `jest` / `vitest`: regex for `Tests: X passed, Y failed, Z total`.
    - `go test`: regex for `PASS`, `FAIL`, `ok <pkg>`, `--- FAIL: <test>`.
    - `cargo test`: regex for `test result: ok. X passed; Y failed; Z ignored`.
    - `mvn test`: regex for `Tests run: X, Failures: Y, Errors: Z, Skipped: W`.
  - Detect infrastructure/tool unavailability: if the runner is missing from the environment, classify as `UNAVAILABLE` with clear diagnostic advice, avoiding false code-failure attribution.

#### D. Enhancements to LangGraph State & Schema
- **Location:** `backend/app/agents/state.py`
- **Modifications:**
  - Add optional fields to `TestRunOutput`:
    - `detected_languages: List[str]`
    - `detected_frameworks: List[str]`
    - `package_manager: Optional[str]`
    - `discovery_status: str` (`DISCOVERED`, `UNAVAILABLE`, `TIMED_OUT`, `DISCOVERY_ERROR`)
    - `execution_status: str` (`PASSED`, `FAILED`, `SKIPPED`, `UNAVAILABLE`, `TIMED_OUT`)
    - `selected_test_files: List[str]`
    - `is_targeted: bool`
    - `skipped_tests: int`
    - `failure_classification: Optional[str]`
    - `diagnostic_warning: Optional[str]`

#### E. Frontend Updates
- **Location:** `frontend/src/app/tasks/[id]/page.tsx`, `frontend/src/types/index.ts`
- **Modifications:**
  - Update `AGENT_ROSTER` tester description to reflect multi-language capability.
  - Enhance Test Results card to display language/framework badges, targeted test tags, and missing dependency/runner warnings.

---

### 3. Security Considerations

1. **Untrusted Manifests:** Repository manifests (`package.json`, `pom.xml`, `pyproject.toml`) are untrusted inputs. Do not evaluate arbitrary scripts, install unverified dependencies, or run lifecycle scripts (`npm install`, `postinstall`).
2. **Command Injection Prevention:**
   - Use structured argument lists or strictly sanitized parameter strings.
   - Disallow shell operators (`&&`, `||`, `;`, pipes, redirection, backticks, `$()`).
3. **Sandbox Network & Filesystem Isolation:**
   - Maintain `--network none` in Docker.
   - Maintain read-only root where applicable, and confine writes strictly to `/workspace`.
   - Enforce path validation preventing directory traversal (`..`) when passing file arguments.
4. **Secret Scrubbing:**
   - Redact all tokens, API keys, and environment variables from test stdout and stderr.

---

### 4. Testing & Validation Strategy

1. **Unit Tests (`backend/tests/unit/test_test_discovery.py`):**
   - Manifest detection for Python, JS/TS, Go, Rust, Java.
   - Framework detection (pytest vs unittest, Jest vs Vitest, go test, cargo test, maven).
   - Test file discovery across standard directory structures.
   - Targeted test selection based on modified file paths.
   - Full suite fallback when no specific test file matches.
   - Output parsing for all 6 test framework stdout formats.
   - Malicious path traversal and injection prevention.
   - Missing runner handling.
2. **Integration Tests (`backend/tests/integration/test_multi_language_test_runner.py`):**
   - Real sandbox execution against fixture workspaces:
     - Python with pytest.
     - Python with unittest.
     - JavaScript with Jest (or mock runner if Node/Jest not installed).
     - TypeScript with Vitest (or mock runner).
     - Go with `go test` (if Go installed, else skip with reason).
     - Rust with `cargo test` (if Cargo installed, else skip with reason).
     - Java with Maven (if Maven installed, else skip with reason).
     - Mixed-language repository (e.g. Python backend + TypeScript frontend).
3. **Regression Tests:**
   - Full backend test suite (`DEVORA_SANDBOX_RUNNER=local .venv/bin/pytest backend/tests`).
   - Expected baseline: $\ge 129$ passing tests, 0 regressions.
4. **Frontend Verification:**
   - Production Next.js build (`npm run build --prefix frontend`).
   - Expected baseline: 15/15 routes compiled with 0 errors.

---

### 5. Acceptance Criteria Checklist

- [ ] Existing architecture inspected and documented in this plan.
- [ ] `TestDiscoveryService` implemented with support for Python, JavaScript, TypeScript, Go, Rust, and Java.
- [ ] Framework detection supports pytest, unittest, Jest, Vitest, go test, cargo test, Maven test.
- [ ] Targeted test selection correctly maps modified files to test files with full suite fallback.
- [ ] `SandboxService` and `LocalIsolatedRunner` safely support multi-language test commands without command injection vulnerabilities.
- [ ] Output parser normalizes counts (total, passed, failed, skipped), duration, exit codes, and failure details.
- [ ] `tester_node` in LangGraph uses `TestDiscoveryService` and returns normalized results.
- [ ] Missing runners or tools return structured `UNAVAILABLE` diagnostics instead of false code-failure retries.
- [ ] Frontend displays detected languages, frameworks, and targeted execution badges.
- [ ] Unit tests pass ($100\%$).
- [ ] Integration tests pass with real and skipped runtime handling.
- [ ] Zero regressions across existing 129 backend tests.
- [ ] Next.js frontend builds cleanly.
- [ ] Documentation updated and implementation report created.
