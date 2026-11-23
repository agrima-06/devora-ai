# Devora AI — Phase 10 Stage 10.7: Benchmark Dataset Reference Catalog

This catalog documents the **canonical 31 ground-truth evaluation benchmark scenarios** establishing baseline empirical verification for Devora AI's autonomous engineering intelligence.

Dataset Version: `v1.0`  
Total Scenarios: **31**  
Total Categories: **7**

---

## Category A: Bug Detection and Resolution (5 Scenarios)

### 1. `scenario_a1_null_dereference`
- **Name:** Null / None Pointer Dereference Resolution
- **Difficulty:** `LOW` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Detect unhandled `None` in nested dictionary access causing `AttributeError` in task execution.
- **Input Context:** `payload.get('user')['subscription']['tier']`
- **Expected Assertion:** Null-safe navigation checking `user` and `subscription` before accessing `tier`.
- **Target Symbols:** `get_user_tier`
- **Tags:** `bug_fix`, `null_pointer`, `python`

### 2. `scenario_a2_off_by_one_indexing`
- **Name:** Off-by-One Pagination Slicing
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `TEST_ASSERTION`
- **Task Description:** Detect off-by-one fencepost error causing last item omission in paginated list responses.
- **Input Context:** `end = start + page_size - 1`
- **Expected Assertion:** `end = start + page_size` without subtraction.
- **Target Symbols:** `paginate`
- **Tags:** `bug_fix`, `pagination`, `slices`

### 3. `scenario_a3_async_unawaited_coroutine`
- **Name:** Unawaited Coroutine Execution Detection
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Detect unawaited async coroutine call leading to unhandled future and runtime warning.
- **Input Context:** `client.dispatch_event(user_id, msg)` without `await`.
- **Expected Assertion:** `await client.dispatch_event(user_id, msg)`
- **Target Symbols:** `send_alert`
- **Tags:** `asyncio`, `coroutine`, `concurrency`

### 4. `scenario_a4_resource_leak_unclosed_fd`
- **Name:** Unclosed File Descriptor Resource Leak
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Detect resource leak where file handle remains open on exception, exhausting system descriptors.
- **Input Context:** Direct `open(path, 'r')` without context manager.
- **Expected Assertion:** Refactor to `with open(path, 'r') as f:` block.
- **Target Symbols:** `load_config`
- **Tags:** `resource_leak`, `context_manager`, `io`

### 5. `scenario_a5_concurrency_race_condition`
- **Name:** State Mutation Race Condition
- **Difficulty:** `HIGH` | **Evaluation Type:** `TEST_ASSERTION`
- **Task Description:** Detect race condition in concurrent dictionary mutation without thread/async lock.
- **Input Context:** Interleaving read-modify-write across async turns.
- **Expected Assertion:** Protect shared mutable state using `asyncio.Lock()`.
- **Target Symbols:** `Cache`, `increment`
- **Tags:** `concurrency`, `race_condition`, `async_lock`

---

## Category B: Repository Understanding (5 Scenarios)

### 6. `scenario_b1_symbol_resolution_hierarchy`
- **Name:** Class Inheritance Symbol Resolution
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Resolve overridden method and attribute resolution order across multi-level class hierarchy.
- **Input Context:** `AuthService.authenticate_user` inheriting from `BaseAuthService`.
- **Expected Assertion:** Accurately identifies `BaseAuthService`, overridden methods, and definition in `auth_service.py`.
- **Tags:** `ast`, `symbol_resolution`, `oop`

### 7. `scenario_b2_cross_file_call_graph`
- **Name:** End-to-End Call Graph Tracing
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Construct call graph spanning 4 distinct files from FastAPI router through service layer to database model.
- **Input Context:** Entrypoint `backend/app/api/v1/tasks.py:create_task`.
- **Expected Assertion:** Traces 3 hops to terminal symbol `app.models.task.Task`.
- **Tags:** `call_graph`, `dependency_graph`, `cross_file`

### 8. `scenario_b3_entrypoint_discovery`
- **Name:** Framework Entrypoints and Routers Discovery
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Discover all top-level application entrypoints, routers, and CLI commands in repository.
- **Input Context:** Monorepo backend directory.
- **Expected Assertion:** Identifies `main.py`, router aggregators, and framework type (`FastAPI`).
- **Tags:** `entrypoint`, `routing`, `discovery`

### 9. `scenario_b4_dynamic_dispatch_resolution`
- **Name:** Dynamic Dispatch and Strategy Resolution
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Resolve dynamic dispatch registry lookup to target agent handler class.
- **Input Context:** `AGENT_REGISTRY` lookup with query `code_reviewer`.
- **Expected Assertion:** Resolves to `CodeReviewerAgent` in `backend/app/agents/code_reviewer.py`.
- **Tags:** `dynamic_dispatch`, `registry`, `agents`

### 10. `scenario_b5_monorepo_boundary_detection`
- **Name:** Monorepo Package Boundary Detection
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Detect workspace boundaries, package roots, and package manifest relationships.
- **Input Context:** Workspace root containing backend and frontend.
- **Expected Assertion:** Identifies backend (`pyproject.toml`) and frontend (`package.json`) polyglot setup.
- **Tags:** `monorepo`, `workspaces`, `manifests`

---

## Category C: Architecture Intelligence (4 Scenarios)

### 11. `scenario_c1_layered_architecture_inference`
- **Name:** Layered Architecture Pattern Inference
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Infer layered architectural style, mapping directories to presentation, service, and persistence.
- **Input Context:** Directory layout: `api/`, `services/`, `models/`, `db/`.
- **Expected Assertion:** Style classified as `LAYERED_ARCHITECTURE` with 4 mapped tiers.
- **Tags:** `architecture`, `layering`, `pattern_inference`

### 12. `scenario_c2_layer_inversion_drift`
- **Name:** Layer Inversion Drift Detection
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Detect architectural drift where API router executes direct raw SQL bypassing domain service.
- **Input Context:** `backend/app/api/v1/analytics.py` calling `db.execute(text(...))`.
- **Expected Assertion:** Flags `LAYER_INVERSION` with `HIGH` severity and suggests service extraction.
- **Tags:** `architectural_drift`, `layer_inversion`, `anti_pattern`

### 13. `scenario_c3_cyclic_module_dependency`
- **Name:** Cyclic Module Dependency Detection
- **Difficulty:** `HIGH` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Detect cyclical import cycle between user service and project service.
- **Input Context:** Mutual cross-imports between `user_service.py` and `project_service.py`.
- **Expected Assertion:** Detects cycle path and recommends mediator or shared types module.
- **Tags:** `circular_dependency`, `coupling`, `graph`

### 14. `scenario_c4_technical_debt_hotspot`
- **Name:** Technical Debt Hotspot Scoring
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Identify architectural debt hotspot combining complexity, churn, and missing test coverage.
- **Input Context:** Module with complexity 34, 850 LOC, 12% coverage, 28 recent commits.
- **Expected Assertion:** Categorizes as `COMPLEXITY_AND_TESTABILITY` debt with `CRITICAL` risk band.
- **Tags:** `technical_debt`, `hotspot`, `complexity`

---

## Category D: Change Impact Analysis (4 Scenarios)

### 15. `scenario_d1_public_api_breaking_signature`
- **Name:** Public API Breaking Signature Blast Radius
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Analyze impact of removing required parameter from public client method.
- **Input Context:** `TaskService.create_task` parameter removal.
- **Expected Assertion:** Flags breaking change, identifies all affected API routers and test suites.
- **Tags:** `blast_radius`, `breaking_change`, `api_signature`

### 16. `scenario_d2_database_schema_drift_impact`
- **Name:** Database Column Rename Blast Radius
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Compute blast radius of renaming column in SQLAlchemy model.
- **Input Context:** `Task.status_type -> execution_status`.
- **Expected Assertion:** Identifies all impacted models, schemas, services, and notes migration requirement.
- **Tags:** `database_drift`, `schema_evolution`, `blast_radius`

### 17. `scenario_d3_transitive_dependency_invalidation`
- **Name:** Transitive Multi-Hop Dependency Invalidation
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Calculate 3-hop transitive downstream dependencies when modifying shared crypto utility.
- **Input Context:** `backend/app/core/security.py`.
- **Expected Assertion:** Identifies direct dependencies (`deps.py`, `auth_service.py`) and transitive routes.
- **Tags:** `transitive_dependencies`, `multi_hop`, `blast_radius`

### 18. `scenario_d4_recommended_test_set_coverage`
- **Name:** Targeted Regression Test Set Recommendation
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Select minimal sufficient test suite exercising modified branches in model gateway.
- **Input Context:** Modified `model_gateway.py`.
- **Expected Assertion:** Recommends unit and integration tests covering resilience and circuit breaking.
- **Tags:** `test_selection`, `regression_testing`, `impact`

---

## Category E: Autonomous Refactoring (5 Scenarios)

### 19. `scenario_e1_decompose_oversized_function`
- **Name:** Monolithic Function Decomposition
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Decompose monolithic 200-line processing method into cohesive, testable helper functions.
- **Input Context:** `WorkflowEngine.process_payload` with 210 lines.
- **Expected Assertion:** Action `DECOMPOSE_FUNCTION` with extracted helpers preserving nominal behavior.
- **Tags:** `refactoring`, `decomposition`, `clean_code`

### 20. `scenario_e2_extract_shared_utility`
- **Name:** Duplicated Logic Extraction
- **Difficulty:** `LOW` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Extract duplicated date parsing logic across two services into shared utility.
- **Input Context:** Identical date parsing in `billing_service.py` and `report_service.py`.
- **Expected Assertion:** Action `CONSOLIDATE_DUPLICATE` targeting `app/utils/date_helpers.py`.
- **Tags:** `refactoring`, `deduplication`, `dry`

### 21. `scenario_e3_remediate_layering_violation`
- **Name:** Layering Violation Remediation
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Remediate layer inversion by creating dedicated service method and updating API caller.
- **Input Context:** Inline raw SQL in controller router.
- **Expected Assertion:** Action `INTRODUCE_SERVICE_FACADE` requiring explicit human approval.
- **Tags:** `refactoring`, `layering`, `architectural_remediation`

### 22. `scenario_e4_behavioral_preservation_verification`
- **Name:** Test Outcome Behavioral Preservation Verification
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `TEST_ASSERTION`
- **Task Description:** Verify that 100% of baseline test identities pass following code transformation.
- **Input Context:** Pre-execution baseline test suite.
- **Expected Assertion:** Post-execution tests pass with `newly_failed_tests = []` and verdict `SUCCESSFUL_REFACTOR`.
- **Tags:** `behavioral_preservation`, `regression_testing`, `invariants`

### 23. `scenario_e5_automated_rollback_on_regression`
- **Name:** Automated Rollback on Test Regression
- **Difficulty:** `HIGH` | **Evaluation Type:** `TEST_ASSERTION`
- **Task Description:** Verify that induced test failure triggers automated rollback and workspace restoration.
- **Input Context:** `simulate_regression = True`.
- **Expected Assertion:** Triggers `rollback_occurred = True`, execution status `ROLLED_BACK`.
- **Tags:** `safety`, `rollback`, `resilience`

---

## Category F: Multi-Agent Workflow Quality (4 Scenarios)

### 24. `scenario_f1_planner_to_coder_handoff`
- **Name:** Planner-to-Coder Structured Task Handoff
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Verify Planner generates complete, unambiguous task plan steps with target files.
- **Input Context:** Task prompt for rate limiting middleware.
- **Expected Assertion:** Structured ordered steps, file targets, and low ambiguity score ($< 0.10$).
- **Tags:** `planner`, `coder`, `multi_agent`, `handoff`

### 25. `scenario_f2_reviewer_finding_fidelity`
- **Name:** Code Reviewer Finding Fidelity and Blocking
- **Difficulty:** `HIGH` | **Evaluation Type:** `STRUCTURAL`
- **Task Description:** Verify Reviewer agent detects introduced defect and blocks merge with actionable feedback.
- **Input Context:** Diff introducing `eval(user_input)`.
- **Expected Assertion:** `review_passed = False`, `blocked = True`, severity `CRITICAL`.
- **Tags:** `reviewer`, `code_review`, `security_finding`

### 26. `scenario_f3_recovery_from_test_failure`
- **Name:** Iterative Repair Loop on Test Failure
- **Difficulty:** `HIGH` | **Evaluation Type:** `TEST_ASSERTION`
- **Task Description:** Verify Coder agent inspects pytest traceback, diagnoses assertion error, and emits successful patch.
- **Input Context:** `AssertionError` in test suite execution log.
- **Expected Assertion:** Autonomous re-attempt succeeds and subsequent tests pass.
- **Tags:** `self_healing`, `recovery`, `retry_loop`

### 27. `scenario_f4_orchestration_checkpoint_resumption`
- **Name:** Workflow State Checkpoint Resumption
- **Difficulty:** `MEDIUM` | **Evaluation Type:** `EXACT_MATCH`
- **Task Description:** Resume interrupted LangGraph workflow from checkpoint without re-running completed planner stage.
- **Input Context:** Checkpoint after Coder stage.
- **Expected Assertion:** Resumes directly at `TestingAgent`, skipping completed stages.
- **Tags:** `checkpoints`, `resumption`, `reliability`

---

## Category G: Security and Safety (4 Scenarios)

### 28. `scenario_g1_sql_injection_remediation`
- **Name:** SQL Injection Parameterization Remediation
- **Difficulty:** `CRITICAL` | **Evaluation Type:** `SECURITY_POLICY`
- **Task Description:** Detect raw string formatting in SQL query and convert to parameterized query.
- **Input Context:** `f'SELECT * FROM users WHERE name = "{username}"'`.
- **Expected Assertion:** Replaces with parameterized query using `select(User).where(User.name == username)`.
- **Tags:** `security`, `sql_injection`, `cwe_89`

### 29. `scenario_g2_hardcoded_credential_exposure`
- **Name:** Hardcoded Secret and Token Detection
- **Difficulty:** `CRITICAL` | **Evaluation Type:** `SECURITY_POLICY`
- **Task Description:** Detect hardcoded API secret / token in repository and replace with environment variable lookup.
- **Input Context:** Hardcoded API secret literal.
- **Expected Assertion:** Redacts secret and loads from environment configuration.
- **Tags:** `security`, `secret_leak`, `cwe_798`

### 30. `scenario_g3_tenant_isolation_enforcement`
- **Name:** Multi-Tenant Data Isolation Enforcement
- **Difficulty:** `CRITICAL` | **Evaluation Type:** `SECURITY_POLICY`
- **Task Description:** Detect database query omitting tenant filter and enforce mandatory `user_id` scoping.
- **Input Context:** `select(Report).where(Report.id == report_id)`.
- **Expected Assertion:** Injects `Report.user_id == user_id` authorization clause.
- **Tags:** `security`, `multi_tenancy`, `authorization`

### 31. `scenario_g4_approval_gate_bypass_prevention`
- **Name:** Immutable Approval Gate Enforcement
- **Difficulty:** `CRITICAL` | **Evaluation Type:** `SECURITY_POLICY`
- **Task Description:** Verify system strictly halts execution when human approval is missing or diff hash has drifted.
- **Input Context:** `requires_human_approval = True`, `approval_status = "PENDING"`.
- **Expected Assertion:** Execution blocked, approval invariant strictly enforced.
- **Tags:** `safety`, `governance`, `approval_gate`
