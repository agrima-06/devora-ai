# API Contract Specification
## Devora AI: Autonomous AI Software Engineer

---

### 1. API Design Principles & Standards

* **Protocol & Architecture:** RESTful HTTP/2 APIs, OpenAPI 3.1 specification, and Server-Sent Events (SSE) for streaming agent runtime events.
* **Base URL:** `/api/v1`
* **Content Type:** `application/json` (REST), `text/event-stream` (SSE).
* **Authentication:** `Authorization: Bearer <JWT>` header for all authenticated routes.
* **Error Envelope Standard:** Consistent JSON error structure with machine-readable error codes and RFC 7807 problem details.

---

### 2. Standard Error Envelope (`ErrorResponse`)

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Task with ID '123e4567-e89b-12d3-a456-426614174000' does not exist.",
    "details": {},
    "timestamp": "2026-11-14T03:30:00Z"
  }
}
```

Standard Error Codes:
* `INVALID_CREDENTIALS` (401)
* `FORBIDDEN_ACCESS` (403)
* `RESOURCE_NOT_FOUND` (404)
* `VALIDATION_ERROR` (422)
* `SANDBOX_EXECUTION_TIMEOUT` (408)
* `INTERNAL_ERROR` (500)

---

### 3. API Endpoints Specification

#### 3.1 Health & Telemetry
* `GET /api/v1/health`
  * **Summary:** Health check endpoint verifying database and Redis connectivity.
  * **Auth:** None.
  * **Response (200 OK):**
    ```json
    {
      "status": "healthy",
      "version": "1.0.0",
      "services": {
        "database": "connected",
        "redis": "connected",
        "sandbox_runner": "available"
      }
    }
    ```

---

#### 3.2 Authentication & User Lifecycle
* `POST /api/v1/auth/register`
  * **Request Body:**
    ```json
    {
      "email": "engineer@company.com",
      "password": "StrongPassword123!",
      "full_name": "Senior Developer"
    }
    ```
  * **Response (201 Created):**
    ```json
    {
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "email": "engineer@company.com",
      "full_name": "Senior Developer",
      "access_token": "eyJhbGci...",
      "token_type": "bearer"
    }
    ```

* `POST /api/v1/auth/login`
  * **Request Body:** Form data `username` (email) & `password`.
  * **Response (200 OK):** Access token, refresh token, user profile.

---

#### 3.3 Projects & Repositories
* `POST /api/v1/projects`
  * **Summary:** Create a project boundary.
  * **Request Body:** `{"name": "Core Platform", "description": "Microservices suite", "slug": "core-platform"}`
  * **Response (201 Created):** Project object.

* `GET /api/v1/projects`
  * **Response (200 OK):** List of user projects.

* `POST /api/v1/repositories`
  * **Summary:** Connect and index a repository.
  * **Request Body:**
    ```json
    {
      "project_id": "c1f7a0b3-11b2-4d2c-9a4f-5f4a56b7c8d9",
      "name": "payment-service",
      "full_name": "org/payment-service",
      "clone_url": "https://github.com/org/payment-service.git",
      "default_branch": "main",
      "language": "python"
    }
    ```
  * **Response (201 Created):** Repository metadata with indexing status `SYNCING`.

* `POST /api/v1/repositories/{id}/sync`
  * **Summary:** Trigger repository metadata synchronization.
  * **Response (200 OK):** `{"repository_id": "...", "status": "SYNCED", "message": "Repository metadata successfully synchronized."}`

* `POST /api/v1/repositories/{id}/index`
  * **Summary:** Trigger complete repository intelligence scanning, AST parsing, symbol extraction, and vector indexing.
  * **Request Body (Optional):**
    ```json
    {
      "branch": "main",
      "force_reindex": false
    }
    ```
  * **Response (202 Accepted):** IndexingJob object (`status`, `commit_sha`, `files_count`, `symbols_count`).

* `GET /api/v1/repositories/{id}/index/status`
  * **Summary:** Retrieve latest indexing job status.
  * **Response (200 OK):** IndexingJob object.

* `GET /api/v1/repositories/{id}/architecture`
  * **Summary:** Retrieve synthesized repository architecture summary and coding conventions.
  * **Response (200 OK):**
    ```json
    {
      "repository_id": "a2b3c4d5-...",
      "primary_language": "Python",
      "current_commit_sha": "a1b2c3d4...",
      "frameworks": ["FastAPI", "Pytest"],
      "entry_points": ["app/main.py"],
      "manifests": ["requirements.txt"],
      "total_files": 42,
      "total_lines": 3500,
      "architecture_summary": "Repository Architecture Summary (Commit: a1b2c3d4)...",
      "coding_conventions": "Project Conventions & Practices..."
    }
    ```

* `GET /api/v1/repositories/{id}/files`
  * **Summary:** List tracked files with line counts, category, and summaries.
  * **Query Params:** `category` (optional, e.g. `source`, `test`, `config`, `docs`, `manifest`).
  * **Response (200 OK):** Array of RepositoryFile objects.

* `GET /api/v1/repositories/{id}/symbols`
  * **Summary:** List extracted AST symbols (functions, classes, methods).
  * **Query Params:** `symbol_type` (optional), `file_path` (optional).
  * **Response (200 OK):** Array of RepositorySymbol objects.

* `GET /api/v1/repositories/{id}/search`
  * **Summary:** Multi-modal code search across repository files, symbols, and embeddings.
  * **Query Params:**
    * `q`: Search query string (required)
    * `search_type`: `all` | `keyword` | `symbol` | `semantic` (default: `all`)
    * `limit`: Max results (default: 25)
  * **Response (200 OK):**
    ```json
    {
      "repository_id": "a2b3c4d5-...",
      "query": "compute_sum",
      "search_type": "all",
      "results": [
        {
          "file_path": "src/calculator.py",
          "match_type": "symbol",
          "line_number": 8,
          "snippet": "def compute_sum(self, a: float, b: float) -> float",
          "symbol_name": "MathEngine.compute_sum",
          "symbol_type": "method",
          "score": 1.0
        }
      ],
      "total_matches": 1
    }
    ```

---

#### 3.4 Tasks & Agent Workflow Lifecycle
* `POST /api/v1/tasks`
  * **Summary:** Create and dispatch a development task.
  * **Request Body:**
    ```json
    {
      "project_id": "c1f7a0b3-11b2-4d2c-9a4f-5f4a56b7c8d9",
      "repository_id": "a2b3c4d5-e6f7-4a5b-8c9d-0e1f2a3b4c5d",
      "title": "Fix ZeroDivisionError in invoice total calculation",
      "prompt": "When order has 0 discount items, calculate_discount_ratio throws ZeroDivisionError.",
      "error_traceback": "Traceback (most recent call last):\n  File 'invoice.py', line 45, in calc\nZeroDivisionError: division by zero",
      "task_type": "bug_fix",
      "target_branch": "main"
    }
    ```
  * **Response (201 Created):**
    ```json
    {
      "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
      "status": "PENDING",
      "title": "Fix ZeroDivisionError in invoice total calculation",
      "created_at": "2026-11-14T03:32:00Z"
    }
    ```

* `GET /api/v1/tasks/{id}`
  * **Summary:** Get complete task status, current step, and execution summary.
  * **Response (200 OK):**
    ```json
    {
      "id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
      "status": "WAITING_APPROVAL",
      "title": "Fix ZeroDivisionError in invoice total calculation",
      "iterations_count": 1,
      "plan": {
        "steps": [
          {"step_number": 1, "description": "Locate invoice.py division", "status": "COMPLETED"},
          {"step_number": 2, "description": "Apply safe guard for zero discount", "status": "COMPLETED"},
          {"step_number": 3, "description": "Execute pytest suite", "status": "COMPLETED"}
        ]
      },
      "active_agent": "ReportingAgent"
    }
    ```

* `POST /api/v1/tasks/{id}/start`
  * **Summary:** Trigger the LangGraph 9-specialist-agent state machine workflow for this task.
  * **Response (202 Accepted):**
    ```json
    {
      "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
      "status": "IN_PROGRESS",
      "message": "Workflow started. Current step: 0"
    }
    ```

* `GET /api/v1/tasks/{id}/events` (Server-Sent Events)
  * **Summary:** Real-time stream of specialist agent logs, diffs, and test terminal output.
  * **Headers:** `Accept: text/event-stream`
  * **Event Types:** `AGENT_<NODE>_COMPLETED`, `APPROVAL_REQUIRED`, `APPROVED`, `COMPLETED`, `FAILED`.

* `GET /api/v1/tasks/{id}/runs`
  * **Summary:** Retrieve full execution history of specialist agents for a task.
  * **Response (200 OK):** List of agent runs with step numbers, durations, and state transitions.

---

#### 3.5 Code Diffs, Tests & Approvals
* `GET /api/v1/tasks/{id}/diff`
  * **Summary:** Retrieve unified diffs and file modifications generated by the Coding Agent.
  * **Response (200 OK):**
    ```json
    [
      {
        "id": "e4f5a6b7-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
        "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
        "file_path": "services/invoice.py",
        "change_type": "modified",
        "diff": "--- a/services/invoice.py\n+++ b/services/invoice.py\n@@ -44,3 +44,5 @@\n-    return total / discount_count\n+    if discount_count == 0:\n+        return 0.0\n+    return total / discount_count\n",
        "created_at": "2026-11-14T03:32:45Z"
      }
    ]
    ```

* `GET /api/v1/tasks/{id}/tests`
  * **Summary:** Retrieve all isolated sandbox test run outputs, exit codes, durations, and resource telemetry.
  * **Response (200 OK):**
    ```json
    [
      {
        "id": "e4f5a6b7-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
        "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
        "iteration": 1,
        "command": "pytest",
        "exit_code": 0,
        "passed": true,
        "total_tests": 8,
        "passed_tests": 8,
        "failed_tests": 0,
        "stdout": "8 passed in 1.25s",
        "stderr": "",
        "duration_seconds": 1.25,
        "peak_memory_rss_bytes": 104857600,
        "peak_memory_rss_mb": 100.0,
        "cpu_time_seconds": 0.45,
        "wall_time_seconds": 1.25,
        "memory_limit_bytes": 1572864000,
        "memory_limit_mb": 1500.0,
        "cpu_limit": 2.0,
        "oom_killed": false,
        "termination_reason": null,
        "exit_classification": "SUCCESS",
        "resource_telemetry_available": true,
        "created_at": "2026-11-14T03:32:45Z"
      }
    ]
    ```

* `POST /api/v1/tasks/{id}/approval`
  * **Summary:** Developer action gate: Approve, Request Changes, or Reject.
  * **Request Body:**
    ```json
    {
      "action": "APPROVE",
      "notes": "Looks good. Verified all pytest tests pass."
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "id": "e4f5a6b7-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
      "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
      "requested_by": "12a9d832-8de0-438e-8fae-0fcddde23724",
      "reviewed_by": "12a9d832-8de0-438e-8fae-0fcddde23724",
      "status": "APPROVED",
      "notes": "Looks good. Verified all pytest tests pass.",
      "requested_at": "2026-11-14T03:32:50Z",
      "responded_at": "2026-11-14T03:33:00Z"
    }
    ```

---

#### 3.5.1 Workflow Recovery & Safe Task Resumption (Phase 9 Stage 9.4)
* `GET /api/v1/tasks/{id}/recovery`
  * **Summary:** Evaluate whether an interrupted task workflow can be safely resumed from its latest database checkpoint.
  * **Response (200 OK):**
    ```json
    {
      "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
      "status": "IN_PROGRESS",
      "recovery_status": "INTERRUPTED",
      "is_interrupted": true,
      "interruption_reason": "Heartbeat timeout expired (145s > 120s)",
      "is_eligible_for_recovery": true,
      "eligibility_reason": "Eligible to resume from checkpoint cp-9a1f2e (node 'coder', step 5)",
      "recovery_attempts": 0,
      "max_recovery_attempts": 3,
      "last_heartbeat_at": "2026-11-19T11:30:00Z",
      "recovery_lease_owner": null,
      "recovery_lease_expires_at": null,
      "recovery_error": null,
      "latest_checkpoint": {
        "checkpoint_id": "cp-9a1f2e",
        "node_name": "coder",
        "step_number": 5,
        "thread_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
        "created_at": "2026-11-19T11:29:45Z"
      }
    }
    ```

* `POST /api/v1/tasks/{id}/resume`
  * **Summary:** Acquire atomic recovery lease and safely resume workflow from the last verified persisted checkpoint without restarting completed work.
  * **Request Body:**
    ```json
    {
      "force": false,
      "custom_branch": null
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
      "status": "WAITING_APPROVAL",
      "recovery_status": "NOT_REQUIRED",
      "resumed_from_node": "coder",
      "step_number": 5,
      "recovery_attempts": 1,
      "message": "Workflow successfully resumed to state 'WAITING_APPROVAL'"
    }
    ```

* `POST /api/v1/tasks/recovery/scan`
  * **Summary:** Identify active tasks suffering from expired heartbeats or abnormal worker crashes, flag them as INTERRUPTED, and return recovery diagnostics.
  * **Response (200 OK):**
    ```json
    {
      "scanned_tasks_count": 2,
      "interrupted_tasks": [
        {
          "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
          "title": "Fix division by zero",
          "status": "IN_PROGRESS",
          "recovery_status": "INTERRUPTED",
          "interruption_reason": "Heartbeat timeout expired",
          "eligible": true,
          "recovery_attempts": 0,
          "last_heartbeat_at": "2026-11-19T11:20:00Z",
          "latest_node": "coder"
        }
      ]
    }
    ```

---

#### 3.6 Reports & Feedback
* `GET /api/v1/tasks/{id}/report`
  * **Summary:** Retrieve the final synthesized Engineering Report.
  * **Response (200 OK):** Markdown content and metadata.

* `POST /api/v1/tasks/{id}/feedback`
  * **Summary:** Developer scoring of Devora's engineering performance.
  * **Request Body:**
    ```json
    {
      "rating": "ACCEPTED",
      "solution_accepted": true,
      "comments": "Exact minimal fix, verified cleanly against pytest."
    }
    ```
  * **Response (201 Created):** Stored feedback ID and updated experience quality score.

---

#### 3.7 ML Bug Classification Engine (Phase 6)
* `POST /api/v1/ml/classify`
  * **Summary:** Predict canonical bug category from error traceback and description with sub-millisecond latency.
  * **Request Body:**
    ```json
    {
      "error_message": "ZeroDivisionError: division by zero",
      "traceback": "File 'invoice.py', line 45, in calc\nZeroDivisionError: division by zero",
      "task_description": "Fix discount calculator",
      "task_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a"
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "predicted_category": "runtime_logic_error",
      "confidence": 0.942,
      "top_probabilities": [
        {"category": "runtime_logic_error", "probability": 0.942},
        {"category": "index_key_error", "probability": 0.038},
        {"category": "type_error", "probability": 0.012}
      ],
      "is_low_confidence": false,
      "warning": null,
      "model_version": "v1.0.0",
      "input_hash": "a1b2c3d4...",
      "cleaned_input_preview": "ZeroDivisionError division by zero File <FILE_PATH>/invoice.py line <LINE_NUM>...",
      "inference_time_ms": 0.65,
      "timestamp": "2026-11-19T00:10:00Z"
    }
    ```

* `GET /api/v1/ml/model/status`
  * **Summary:** Retrieve runtime status, active model version, sample counts, and algorithm details.
  * **Response (200 OK):**
    ```json
    {
      "status": "ready",
      "active_version": "v1.0.0",
      "algorithm": "LogisticRegression",
      "is_promoted": true,
      "sample_counts": {"train": 111, "val": 25, "test": 24, "total": 160},
      "model_sha256": "85dd37b2...",
      "created_at": "2026-11-19T00:25:01Z"
    }
    ```

* `GET /api/v1/ml/model/metrics`
  * **Summary:** Retrieve full evaluation metrics including holdout accuracy, weighted/macro F1, per-class stats, and 8x8 confusion matrix.
  * **Response (200 OK):**
    ```json
    {
      "accuracy": 1.0,
      "macro_f1": 1.0,
      "weighted_f1": 1.0,
      "classes": ["syntax_error", "import_dependency_error", "type_error", "attribute_null_reference_error", "index_key_error", "runtime_logic_error", "database_network_error", "permission_security_error"],
      "per_class": {
        "runtime_logic_error": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 3}
      },
      "confusion_matrix": [[3, 0, 0, 0, 0, 0, 0, 0], ...]
    }
    ```

* `GET /api/v1/ml/model/versions`
  * **Summary:** List all available model artifact versions with promotion status and SHA-256 hashes.
  * **Response (200 OK):** Array of version objects.

* `POST /api/v1/ml/model/train`
  * **Summary:** Trigger controlled model retraining and promotion gate against the curated dataset.
  * **Request Body:**
    ```json
    {
      "version": "v1.1.0",
      "min_weighted_f1": 0.85,
      "min_class_precision": 0.70,
      "c_param": 5.0,
      "max_iter": 1000
    }
    ```
  * **Response (200 OK):** `ModelTrainingResult` with evaluation metrics and promotion decision.

* `GET /api/v1/ml/predictions`
  * **Summary:** Paginated history of model inference requests, confidence scores, and post-task verification accuracy.
  * **Query Parameters:** `task_id`, `page`, `page_size`.
  * **Response (200 OK):** `PredictionHistoryResponse` with list of prediction records and verification totals.

---

#### 3.8 Phase 5 Semantic Vector Memory Service
* `GET /api/v1/repositories/{id}/memories`
  * **Summary:** List repository engineering memories with category, status, and staleness filters.
  * **Query Parameters:** `category`, `verification_status`, `is_stale`, `skip`, `limit`.
  * **Response (200 OK):** Array of `MemoryResponse` objects.

* `POST /api/v1/repositories/{id}/memories`
  * **Summary:** Store an explicit convention, decision, or architectural memory.
  * **Request Body:**
    ```json
    {
      "category": "coding_conventions",
      "title": "Use Pydantic v2 BaseSettings",
      "content": "Configuration settings must inherit from pydantic_settings.BaseSettings with SettingsConfigDict.",
      "source_reference": "app/config.py",
      "verification_status": "developer_confirmed"
    }
    ```
  * **Response (201 Created):** `MemoryResponse` object with 768-dim embedding metadata.

* `POST /api/v1/repositories/{id}/memories/search`
  * **Summary:** Semantic similarity search across memories using pgvector cosine distance.
  * **Request Body:**
    ```json
    {
      "query": "How do we configure database connection pooling?",
      "limit": 5,
      "threshold": 0.20
    }
    ```
  * **Response (200 OK):** Ranked list of `MemorySearchResult` with similarity and weighted relevance scores.

* `GET /api/v1/repositories/{id}/memories/stats`
  * **Summary:** Aggregated statistics for repository memories (total, verified, stale, by category).
  * **Response (200 OK):** `MemoryStatsResponse`.

* `POST /api/v1/repositories/{id}/memories/{memory_id}/stale`
  * **Summary:** Manually mark a superseded memory as stale.
  * **Response (200 OK):** Updated `MemoryResponse` with `is_stale = true`.

* `POST /api/v1/repositories/{id}/memories/{memory_id}/feedback`
  * **Summary:** Record developer utility feedback (helpful/unhelpful). Auto-stales after 3 unhelpful ratings.
  * **Response (201 Created):** `MemoryFeedbackResponse`.

---

#### 3.9 Phase 7 Adaptive Engineering Intelligence APIs

* `GET /api/v1/adaptive/experiences`
  * **Summary:** List verified and categorized engineering experiences with filters.
  * **Query Parameters:** `task_category`, `bug_category`, `status_type`, `skip`, `limit`.
  * **Response (200 OK):** Array of `EngineeringExperienceResponse` items.

* `POST /api/v1/adaptive/experiences/search`
  * **Summary:** Semantic cosine similarity search across historical experiences with status weighting ($1.3\times$ success, $0.5\times$ failure).
  * **Request Body:**
    ```json
    {
      "query": "ZeroDivisionError in invoice calculation",
      "task_category": "bug_fix",
      "technology_stack": ["python", "pytest"],
      "limit": 5,
      "threshold": 0.15
    }
    ```
  * **Response (200 OK):** Array of `ExperienceSearchResult` with similarity, weighted score, and `is_positive_guidance`.

* `GET /api/v1/adaptive/experiences/{id}`
  * **Summary:** Retrieve full technical details and diff patch for a single experience.
  * **Response (200 OK):** `EngineeringExperienceResponse`.

* `GET /api/v1/adaptive/failures`
  * **Summary:** List structured records of previous execution failures and prevention guidance.
  * **Query Parameters:** `task_id`, `stage`, `failure_type`, `limit`.
  * **Response (200 OK):** Array of `TaskFailureRecordResponse`.

* `GET /api/v1/adaptive/agent-performance`
  * **Summary:** Retrieve empirical performance telemetry across all 9 specialist agents.
  * **Response (200 OK):** `AgentPerformanceResponse` with per-agent success rates, latency, retry frequencies, costs, and category breakdowns.

* `GET /api/v1/adaptive/benchmarks`
  * **Summary:** List the 7 canonical engineering benchmark specifications.
  * **Response (200 OK):** Array of `BenchmarkDefinitionResponse`.

* `POST /api/v1/adaptive/benchmarks/run`
  * **Summary:** Execute benchmark suite and persist verifiable execution scorecards.
  * **Request Body:**
    ```json
    {
      "benchmark_id": "BM-BUG-01",
      "system_version": "v1.0.0",
      "model_version": "gemini-1.5-pro"
    }
    ```
  * **Response (200 OK):** `BenchmarkSummaryResponse` with completion rate, test pass rate, retries, and run list.

* `GET /api/v1/adaptive/benchmarks/history`
  * **Summary:** Retrieve historical benchmark evaluations across versions.
  * **Query Parameters:** `limit`.
  * **Response (200 OK):** Array of `BenchmarkRunResponse`.

* `POST /api/v1/adaptive/feedback`
  * **Summary:** Submit developer feedback on an autonomous task to calibrate experience quality scores.
  * **Request Body:**
    ```json
    {
      "task_id": "123e4567-e89b-12d3-a456-426614174000",
      "rating": "ACCEPTED",
      "plan_accepted": true,
      "code_accepted": true,
      "solution_helpful": true,
      "comments": "High precision fix with zero regressions."
    }
    ```
  * **Response (201 Created):** `AdaptiveFeedbackResponse`.

---

### 7. GitHub Integration & Autonomous Pull Requests

#### 7.1 GitHub App & Installations
* `GET /api/v1/github/status`
  * **Summary:** Returns whether the GitHub App is configured, has private keys loaded, or is in simulation/mock mode.
  * **Response (200 OK):**
    ```json
    {
      "app_configured": true,
      "app_id": "devora-github-app",
      "has_private_key": true,
      "is_mock": false
    }
    ```

* `GET /api/v1/github/installations`
  * **Summary:** List active GitHub App installations linked to the authenticated user.
  * **Response (200 OK):** Array of `GitHubInstallationResponse`.

* `POST /api/v1/github/installations/connect`
  * **Summary:** Authorize or register a GitHub App installation for the authenticated user.
  * **Request Body:**
    ```json
    {
      "installation_id": 998877,
      "account_login": "my-org",
      "account_type": "Organization",
      "repository_selection": "selected"
    }
    ```
  * **Response (201 Created):** `GitHubInstallationResponse`.

* `GET /api/v1/github/installations/{installation_id}/repositories`
  * **Summary:** Query GitHub for authorized repositories under the specified installation.
  * **Response (200 OK):** Array of `GitHubRepositoryItem` (name, full_name, private, clone_url, default_branch, language, permissions).

* `DELETE /api/v1/github/installations/{installation_id}`
  * **Summary:** Deactivate/disconnect a GitHub App installation.
  * **Response (204 No Content)**

#### 7.2 Repository Branches
* `GET /api/v1/repositories/{id}/branches`
  * **Summary:** List remote tracking branches and autonomous Devora task branches (`devora/*`).
  * **Response (200 OK):**
    ```json
    [
      {
        "name": "main",
        "commit_sha": "4a2b1c3d...",
        "is_default": true,
        "is_task_branch": false,
        "is_pushed": true,
        "task_id": null
      },
      {
        "name": "devora/bugfix-a1b2c3d4",
        "commit_sha": "9e8d7c6b...",
        "is_default": false,
        "is_task_branch": true,
        "is_pushed": true,
        "task_id": "123e4567-e89b-12d3-a456-426614174000"
      }
    ]
    ```

#### 7.3 Autonomous Pull Requests
* `GET /api/v1/pull-requests`
  * **Summary:** List pull requests opened by Devora AI across repositories.
  * **Query Parameters:** `repository_id`, `task_id`, `skip`, `limit`.
  * **Response (200 OK):** Array of `PullRequestResponse`.

* `GET /api/v1/pull-requests/{id}`
  * **Summary:** Retrieve full Pull Request details by ID.
  * **Response (200 OK):** `PullRequestResponse`.

* `POST /api/v1/pull-requests/tasks/{task_id}`
  * **Summary:** Manually publish an approved task solution to GitHub as a Pull Request.
  * **Response (201 Created):** `PullRequestResponse`.

* `POST /api/v1/pull-requests/{id}/sync`
  * **Summary:** Synchronize Pull Request state (merged, closed, merge_commit_sha) from GitHub remote.
  * **Response (200 OK):** `SyncPullRequestResponse`.

---

### 8. Flaky Tests & Test Stability Intelligence (Phase 9 Stage 9.2)

#### 8.1 Repository Flaky Tests
* `GET /api/v1/repositories/{id}/flaky-tests`
  * **Summary:** List flaky and unstable test records for a repository.
  * **Query Parameters:** `classification` (optional, e.g. `FLAKY`, `CONSISTENT_FAILURE`).
  * **Response (200 OK):** Array of `FlakyTestRecordResponse`.

* `GET /api/v1/repositories/{id}/test-stability`
  * **Summary:** Retrieve aggregated repository test stability statistics.
  * **Response (200 OK):**
    ```json
    {
      "repository_id": "123e4567-e89b-12d3-a456-426614174000",
      "total_tests_tracked": 12,
      "flaky_tests_count": 3,
      "stable_pass_count": 8,
      "consistent_failure_count": 1,
      "average_stability_score": 85.4,
      "total_repeat_runs_executed": 36
    }
    ```

#### 8.2 Task Flaky Tests
* `GET /api/v1/tasks/{id}/flaky-tests`
  * **Summary:** List flaky tests detected during execution of a specific task.
  * **Response (200 OK):** Array of `FlakyTestRecordResponse`.

* `GET /api/v1/flaky-tests/{id}`
  * **Summary:** Retrieve full execution history and repeat run metrics for a single flaky test record.
  * **Response (200 OK):** `FlakyTestRecordResponse`.

---

### 9. Model Gateway Resilience & Circuit Breaker Health (Phase 9 Stage 9.5)

#### 9.1 Live Health & Diagnostics
* `GET /api/v1/models/health`
  * **Summary:** Retrieve Model Gateway status, active primary and fallback models, circuit breaker states, and aggregate token/retry metrics.
  * **Response (200 OK):**
    ```json
    {
      "status": "HEALTHY",
      "circuit_breaker_enabled": true,
      "active_primary_provider": "gemini",
      "active_primary_model": "gemini-1.5-pro",
      "fallback_enabled": true,
      "fallback_models": ["gemini-1.5-flash"],
      "breakers": [
        {
          "key": "gemini:gemini-1.5-pro",
          "provider_name": "gemini",
          "model_name": "gemini-1.5-pro",
          "state": "CLOSED",
          "consecutive_failures": 0,
          "consecutive_successes": 15,
          "recent_failures_in_window": 0,
          "failure_threshold": 5,
          "open_duration_seconds": 30.0,
          "time_until_probe_seconds": null,
          "total_calls": 24,
          "total_failures": 0,
          "total_probes": 0
        }
      ],
      "metrics": {
        "total_requests": 24,
        "total_prompt_tokens": 12450,
        "total_completion_tokens": 3120,
        "total_retries": 1,
        "total_fallbacks": 0,
        "last_active_at": "2026-11-19T13:30:00Z"
      },
      "timestamp": "2026-11-19T13:30:05Z"
    }
    ```

#### 9.2 Circuit Breaker Resets
* `POST /api/v1/models/breakers/{provider_name}/{model_name}/reset`
  * **Summary:** Manually reset a specific provider/model circuit breaker from OPEN or HALF_OPEN back to CLOSED state.
  * **Response (200 OK):** `ModelCircuitBreakerStatus`.

* `POST /api/v1/models/reset-all`
  * **Summary:** Manually reset all registered circuit breakers across all providers and models back to CLOSED state.
  * **Response (200 OK):** `ModelGatewayHealthResponse`.

---

### 10. Reliability Observability APIs (Phase 9 Stage 9.6)

#### 10.1 System Reliability Overview
* `GET /api/v1/reliability/overview`
  * **Summary:** Retrieve unified health states, granular metrics, and recovery summaries across workflows, sandbox executions, multi-language testing, flaky test detection, Model Gateway, and GitHub integrations.
  * **Query Parameters:**
    * `repository_id` (UUID, optional): Filter metrics and tasks to a specific repository.
  * **Response (200 OK):** `ReliabilityOverviewResponse`
    ```json
    {
      "timestamp": "2026-11-19T14:00:00Z",
      "overall_system_status": "HEALTHY",
      "subsystems": [
        {
          "name": "workflow",
          "display_name": "Workflow Engine",
          "status": "HEALTHY",
          "description": "LangGraph multi-agent workflow state machine",
          "metrics": {
            "total_tasks": 42,
            "completion_rate_pct": 95.2
          }
        },
        {
          "name": "sandbox",
          "display_name": "Sandbox Runner",
          "status": "HEALTHY",
          "description": "Docker isolated execution container with local fallback",
          "metrics": {
            "total_runs": 85,
            "oom_terminations": 0,
            "timeouts": 1
          }
        },
        {
          "name": "gateway",
          "display_name": "Model Gateway",
          "status": "HEALTHY",
          "description": "Primary: gemini-1.5-pro (Process-local with DB sync)",
          "metrics": {
            "retries": 4,
            "fallbacks": 1
          }
        }
      ],
      "workflows": {
        "total_tasks": 42,
        "running_tasks": 2,
        "completed_tasks": 38,
        "failed_tasks": 2,
        "interrupted_tasks": 0,
        "waiting_approval_tasks": 1,
        "recovering_tasks": 0,
        "recovery_success_rate": 100.0,
        "avg_duration_seconds": 64.5,
        "recovery_attempt_distribution": {"0": 40, "1": 2}
      },
      "sandbox": {
        "total_runs": 85,
        "passed_runs": 78,
        "failed_runs": 7,
        "oom_terminations": 0,
        "timeouts": 1,
        "process_killed": 0,
        "runner_unavailable": 0,
        "startup_failures": 0,
        "avg_duration_seconds": 8.4,
        "avg_peak_memory_mb": 210.5,
        "max_peak_memory_mb": 512.0,
        "memory_limit_utilization_pct": 34.1,
        "total_cpu_time_seconds": 714.0
      },
      "test_stability": {
        "total_tracked_tests": 12,
        "stable_pass_count": 10,
        "consistent_failure_count": 1,
        "flaky_count": 1,
        "inconclusive_count": 0,
        "unverified_count": 0,
        "avg_stability_score": 92.4,
        "total_repeat_runs": 48
      },
      "model_gateway": {
        "status": "HEALTHY",
        "active_primary_provider": "gemini",
        "active_primary_model": "gemini-1.5-pro",
        "fallback_enabled": true,
        "fallback_models": ["gemini-1.5-flash"],
        "circuit_states": {"gemini:gemini-1.5-pro": "CLOSED"},
        "total_retries": 4,
        "total_fallbacks": 1,
        "total_requests": 142,
        "average_latency_ms": 1150.0,
        "multi_worker_shared_state": false,
        "deployment_topology": "PROCESS_LOCAL_WITH_DB_SYNC",
        "last_active_at": "2026-11-19T13:58:20Z"
      },
      "recovery": {
        "interrupted_tasks_count": 0,
        "recovery_eligible_count": 0,
        "recovering_count": 0,
        "recovery_failures_count": 0,
        "manual_intervention_required_count": 0,
        "interrupted_tasks": []
      }
    }
    ```

#### 10.2 Unified Reliability Audit Events
* `GET /api/v1/reliability/events`
  * **Summary:** Retrieve paginated, credential-scrubbed reliability audit events across all workflows and subsystems.
  * **Query Parameters:**
    * `subsystem` (string, optional): Subsystem filter (`Workflow`, `Sandbox`, `ModelGateway`, `Recovery`, `GitHub`).
    * `severity` (string, optional): Severity level filter (`INFO`, `WARNING`, `ERROR`, `CRITICAL`).
    * `repository_id` (UUID, optional): Scoped repository filter.
    * `task_id` (UUID, optional): Scoped task filter.
    * `start_date` (datetime, optional): Start timestamp.
    * `end_date` (datetime, optional): End timestamp.
    * `limit` (int, default 50, max 100): Page limit.
    * `offset` (int, default 0): Pagination offset.
  * **Response (200 OK):** `ReliabilityEventsResponse`
    ```json
    {
      "total": 1,
      "limit": 50,
      "offset": 0,
      "events": [
        {
          "id": "e98e4f1a-b32c-4741-a1b9-399a9cfb1109",
          "timestamp": "2026-11-19T13:45:10Z",
          "task_id": "c1f2e4b3-a12b-4567-89ab-cdef01234567",
          "repository_id": "b2c3d4e5-f6a7-8901-2345-6789abcdef01",
          "repository_name": "backend-core",
          "task_title": "Fix division by zero in invoice calculation",
          "subsystem": "Sandbox",
          "event_type": "test_run_completed",
          "severity": "INFO",
          "message": "Sandbox test run completed successfully",
          "payload": {"exit_code": 0, "passed": true}
        }
      ]
    }
    ```

#### 10.3 Reliability Time-Series Trends
* `GET /api/v1/reliability/trends`
  * **Summary:** Retrieve daily time-bucketed aggregation for tasks completed/failed/interrupted, sandbox OOMs/timeouts, and recovery attempts across bounded intervals.
  * **Query Parameters:**
    * `timeframe` (string, default "7d"): Bounded interval (`24h`, `7d`, `14d`, `30d`).
    * `repository_id` (UUID, optional): Scoped repository filter.
  * **Response (200 OK):** `ReliabilityTrendsResponse`
    ```json
    {
      "timeframe": "7d",
      "trends": [
        {
          "bucket_time": "2026-11-13",
          "tasks_completed": 5,
          "tasks_failed": 0,
          "tasks_interrupted": 0,
          "sandbox_ooms": 0,
          "sandbox_timeouts": 0,
          "flaky_tests_detected": 0,
          "model_retries": 0,
          "recovery_attempts": 0
        }
      ]
    }
    ```

---

### 11. Phase 10 Cross-File Symbol & Dependency Graph APIs

#### 11.1 Graph Summary
* `GET /api/v1/repositories/{id}/graph`
  * **Summary:** Retrieve aggregated graph topology, counts by node type and edge type, external/unresolved ratios, and indexing status.
  * **Response (200 OK):** `RepositoryGraphSummaryResponse`
    ```json
    {
      "repository_id": "b2c3d4e5-f6a7-8901-2345-6789abcdef01",
      "total_nodes": 142,
      "total_edges": 318,
      "node_types_breakdown": {
        "FILE": 24,
        "CLASS": 18,
        "FUNCTION": 52,
        "METHOD": 48
      },
      "edge_types_breakdown": {
        "IMPORTS": 88,
        "DEFINES": 118,
        "DEPENDS_ON": 42,
        "CALLS": 70
      },
      "resolution_status_breakdown": {
        "RESOLVED": 290,
        "EXTERNAL": 24,
        "UNRESOLVED": 4
      },
      "external_count": 24,
      "unresolved_count": 4,
      "last_indexed_at": "2026-11-19T14:30:00Z",
      "current_commit_sha": "a1b2c3d4e5f67890"
    }
    ```

#### 11.2 Trigger Graph Indexing
* `POST /api/v1/repositories/{id}/graph/index`
  * **Summary:** Trigger full or incremental AST graph extraction with SHA-256 content-hash change detection.
  * **Request Body:** `GraphIndexRequest`
    ```json
    {
      "force_reindex": false
    }
    ```
  * **Response (200 OK):** `GraphIndexingResponse`
    ```json
    {
      "repository_id": "b2c3d4e5-f6a7-8901-2345-6789abcdef01",
      "status": "INDEXED",
      "files_indexed": 3,
      "files_skipped": 21,
      "total_files": 24,
      "nodes_created": 15,
      "edges_created": 32,
      "unresolved_references": 2,
      "commit_sha": "a1b2c3d4e5f67890",
      "duration_seconds": 0.42
    }
    ```

#### 11.3 Query Graph Nodes
* `GET /api/v1/repositories/{id}/graph/nodes`
  * **Summary:** Filter and search symbols and file nodes with pagination.
  * **Query Parameters:**
    * `node_type` (string, optional): Filter by `FILE`, `CLASS`, `FUNCTION`, `METHOD`, `VARIABLE`, etc.
    * `file_path` (string, optional): Filter by relative file path.
    * `search` (string, optional): Case-insensitive substring match on symbol or qualified name.
    * `limit` (integer, default 50, max 200).
    * `offset` (integer, default 0).
  * **Response (200 OK):** `GraphNodesListResponse` with array of `GraphNodeItem` and total count.

#### 11.4 Node Detail & Immediate Neighborhood
* `GET /api/v1/repositories/{id}/graph/nodes/{node_id}`
  * **Summary:** Retrieve a single graph node along with its immediate outgoing and incoming edges.
  * **Response (200 OK):** `GraphNodeDetailResponse`

#### 11.5 Bounded Dependency Traversal
* `GET /api/v1/repositories/{id}/graph/dependencies`
  * **Summary:** Execute bounded breadth-first traversal up to depth 5 from a root node to identify transitive dependencies or dependents.
  * **Query Parameters:**
    * `root_node_id` (UUID, required): Origin node for BFS traversal.
    * `depth` (integer, default 2, max 5): Traversal radius.
    * `direction` (string, default "OUTGOING"): `OUTGOING`, `INCOMING`, or `BOTH`.
    * `edge_types` (string, optional): Comma-delimited list of edge types to follow (e.g. `IMPORTS,DEPENDS_ON,CALLS`).
  * **Response (200 OK):** `GraphDependenciesResponse` containing `root_node`, traversed `nodes`, connected `edges`, and path chains.

#### 11.6 Unresolved & External References Audit
* `GET /api/v1/repositories/{id}/graph/unresolved`
  * **Summary:** Audit external packages, third-party imports, and unresolved symbols across the repository.
  * **Query Parameters:**
    * `resolution_status` (string, optional): Filter by `UNRESOLVED` or `EXTERNAL`.
    * `limit` (integer, default 50).
    * `offset` (integer, default 0).
  * **Response (200 OK):** `GraphUnresolvedReferencesResponse`

---

### 12. Phase 10 Blast Radius and Change Impact Analysis APIs

#### 12.1 Compute Blast Radius & Change Impact
* `POST /api/v1/repositories/{id}/impact-analysis`
  * **Summary:** Perform reverse dependency graph traversal from target files or symbols, calculating deterministic impact severity, explainable dependency paths, confidence ratings, and recommended test suites.
  * **Request Body:** `ImpactAnalysisRequest`
    ```json
    {
      "file_paths": ["src/formatter.py"],
      "symbol_ids": [],
      "qualified_names": [],
      "max_depth": 3,
      "include_tests": true,
      "max_impacted_nodes": 100
    }
    ```
  * **Response (200 OK):** `ImpactAnalysisResponse`
    ```json
    {
      "repository_id": "b2c3d4e5-f6a7-8901-2345-6789abcdef01",
      "commit_sha": "a1b2c3d4e5f67890",
      "is_stale": false,
      "staleness_reason": null,
      "targets": [
        {
          "node_id": "c1f2e4b3-a12b-4567-89ab-cdef01234567",
          "node_type": "FILE",
          "qualified_name": "src/formatter.py",
          "name": "formatter.py",
          "file_path": "src/formatter.py"
        }
      ],
      "impact_score": 68,
      "severity": "HIGH",
      "confidence": 0.94,
      "score_explanation": "High impact (score 68/100): Significant coupling across 3 files and 6 symbols with traversal depth 2.",
      "score_breakdown": {
        "files_score": 18,
        "symbols_score": 19,
        "depth_score": 12,
        "coupling_score": 10,
        "untested_penalty": 0
      },
      "summary": {
        "total_affected_files": 3,
        "total_affected_symbols": 6,
        "direct_impact_count": 2,
        "transitive_impact_count": 4,
        "recommended_tests_count": 1,
        "unresolved_warnings_count": 0
      },
      "affected_files": [
        "src/formatter.py",
        "src/calculator.py",
        "src/main.py"
      ],
      "impacted_nodes": [
        {
          "node_id": "d2e3f4a5-b6c7-8901-2345-6789abcdef02",
          "node_type": "FILE",
          "qualified_name": "src/calculator.py",
          "name": "calculator.py",
          "file_path": "src/calculator.py",
          "depth": 1,
          "is_direct": true,
          "primary_reason": "Directly imports by formatter.py",
          "confidence": 1.0,
          "resolution_status": "RESOLVED",
          "paths_count": 1
        }
      ],
      "dependency_paths": [
        {
          "target_name": "formatter.py",
          "impacted_node_id": "d2e3f4a5-b6c7-8901-2345-6789abcdef02",
          "impacted_name": "calculator.py",
          "impacted_file_path": "src/calculator.py",
          "depth": 1,
          "hops": [],
          "explanation": "calculator.py (FILE) -[IMPORTS]-> formatter.py"
        }
      ],
      "recommended_tests": [
        {
          "test_file_path": "tests/test_calculator.py",
          "test_framework": "pytest",
          "recommendation_type": "CONFIRMED",
          "confidence": 0.95,
          "reason": "Test file 'tests/test_calculator.py' directly imports affected file 'src/calculator.py'",
          "target_symbol_or_file": "src/calculator.py"
        }
      ],
      "unresolved_warnings": [],
      "execution_duration_seconds": 0.04
    }
    ```

---

#### 3.16 Phase 10 Stage 10.3 Monorepo & Workspace Intelligence APIs

* `GET /api/v1/repositories/{id}/workspaces`
  * **Summary:** Retrieve all detected monorepos, multi-project build configurations, packages, and cross-package dependency edges for a repository.
  * **Response (200 OK):**
    ```json
    {
      "repository_id": "c1d2e3f4-a5b6-7890-1234-56789abcdef0",
      "workspaces": [
        {
          "id": "e3f4a5b6-c7d8-9012-3456-789abcdef012",
          "workspace_type": "pnpm",
          "root_path": ".",
          "manifest_file": "pnpm-workspace.yaml",
          "packages_count": 3,
          "packages": [
            {
              "id": "f4a5b6c7-d8e9-0123-4567-89abcdef0123",
              "name": "@devora/core",
              "version": "1.0.0",
              "path": "packages/core",
              "manifest_path": "packages/core/package.json",
              "language": "typescript",
              "internal_dependencies": [],
              "external_dependencies": ["lodash"],
              "files_count": 12
            }
          ]
        }
      ],
      "cross_package_edges": [
        {
          "source_package": "@devora/api",
          "target_package": "@devora/core",
          "edge_type": "PACKAGE_DEPENDS_ON",
          "confidence": 1.0
        }
      ],
      "summary": {
        "total_workspaces": 1,
        "total_packages": 3,
        "ecosystems": ["pnpm"],
        "is_monorepo": true
      }
    }
    ```

* `GET /api/v1/repositories/{id}/packages`
  * **Summary:** List all packages discovered across all workspaces in the repository.
  * **Response (200 OK):** Array of `PackageInfo` objects.

* `GET /api/v1/repositories/{id}/packages/{package_id}/dependencies`
  * **Summary:** Retrieve upstream dependencies (internal workspace packages and external libraries) and downstream consumer packages (dependents) for a specific package.
  * **Response (200 OK):** `PackageDependenciesResponse`.

* `GET /api/v1/repositories/{id}/packages/{package_id}/dependents`
  * **Summary:** Retrieve downstream packages that directly depend on the target package.
  * **Response (200 OK):** Array of `PackageInfo` objects.

* `GET /api/v1/repositories/{id}/packages/{package_id}/impact`
  * **Summary:** Calculate blast radius, propagation chain, and severity if a specific package is modified.
  * **Response (200 OK):**
    ```json
    {
      "package_id": "f4a5b6c7-d8e9-0123-4567-89abcdef0123",
      "package_name": "@devora/core",
      "severity": "MEDIUM",
      "affected_packages": [
        {
          "package_name": "@devora/api",
          "package_path": "packages/api",
          "depth": 1,
          "dependency_path": ["@devora/core", "@devora/api"]
        }
      ],
      "affected_packages_count": 1,
      "affected_files_count": 8,
      "recommendations": [
        "Run integration test suites for affected consumer packages: @devora/api"
      ]
    }
    ```

* `POST /api/v1/repositories/{id}/workspaces/index`
  * **Summary:** Trigger scanning, multi-language workspace detection, and persistence of workspace/package nodes and edges.
  * **Request Body:** Optional `{ "branch": "main", "local_path": "/path/to/repo" }`.
  * **Response (200 OK):** `WorkspaceIndexResponse`.

---

### 3.17 Semantic Architecture, Pattern Inference & Hybrid Search (Phase 10 Stage 10.4)

* `POST /api/v1/repositories/{id}/search/hybrid`
  * **Summary:** Multi-modal hybrid repository search combining exact identifier/BM25 matching, 768-dimensional pgvector cosine similarity, and AST dependency graph centrality using Reciprocal Rank Fusion (RRF, k=60).
  * **Headers:** `Authorization: Bearer <token>`
  * **Request Body:**
    ```json
    {
      "query": "AuthService session verification",
      "filters": {
        "languages": ["python"],
        "symbol_types": ["class", "function"],
        "file_paths": ["backend/*"]
      },
      "limit": 15,
      "offset": 0,
      "lexical_weight": 0.35,
      "semantic_weight": 0.45,
      "structural_weight": 0.20
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "repository_id": "89cf650f-d55a-4dfa-ba09-438dafe722a9",
      "query": "AuthService session verification",
      "total_matches": 12,
      "limit": 15,
      "offset": 0,
      "search_duration_seconds": 0.045,
      "results": [
        {
          "file_path": "backend/app/services/auth_service.py",
          "line_number": 15,
          "line_end": 85,
          "symbol_name": "AuthService",
          "symbol_type": "class",
          "package_name": "backend",
          "language": "python",
          "snippet": "class AuthService:\n    async def verify_jwt_session(token: str): ...",
          "lexical_score": 0.95,
          "semantic_score": 0.88,
          "structural_score": 0.75,
          "combined_score": 0.912,
          "rank": 1,
          "provenance_explanation": "Lexical match on symbol 'AuthService' (rank #1); Semantic similarity 0.88; Structural centrality degree 6 (rank #2)"
        }
      ]
    }
    ```

* `GET /api/v1/repositories/{id}/architecture`
  * **Summary:** Retrieve unified repository architectural profile, confirmed patterns count, framework metadata, and coding conventions.
  * **Response (200 OK):** `ArchitectureSummaryResponse`.

* `POST /api/v1/repositories/{id}/architecture/analyze`
  * **Summary:** Trigger on-demand architectural pattern re-analysis and persist verified patterns to PostgreSQL.
  * **Response (200 OK):** `ArchitectureSummaryResponse`.

* `GET /api/v1/repositories/{id}/architecture/patterns`
  * **Summary:** List all detected architectural patterns with category and confidence threshold filtering.
  * **Query Parameters:** `category` (`application`, `backend`, `frontend`, `ai_agent`, `data`), `min_confidence` (0.0 - 1.0).
  * **Response (200 OK):** Array of `ArchitecturePatternItem` objects.

* `GET /api/v1/repositories/{id}/architecture/patterns/{pattern_id}`
  * **Summary:** Retrieve detailed evidence, supporting files, AST symbols, and counterexamples for a specific design pattern.
  * **Response (200 OK):** `ArchitecturePatternItem`.

* `GET /api/v1/repositories/{id}/architecture/conventions`
  * **Summary:** Retrieve discovered repository conventions across services, API routes, database sessions, and error handling.
  * **Query Parameters:** `category` (`service`, `api`, `database`, `error`, `test`).
  * **Response (200 OK):** Array of `ArchitectureConventionItem` objects.

* `POST /api/v1/repositories/{id}/architecture/ask`
  * **Summary:** Ask natural language architectural questions and receive explanations grounded directly in source code evidence and verified patterns.
  * **Request Body:**
    ```json
    {
      "question": "How are database sessions and transactions managed?",
      "context_limit": 6
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "repository_id": "89cf650f-d55a-4dfa-ba09-438dafe722a9",
      "question": "How are database sessions and transactions managed?",
      "answer": "In this codebase, database access is governed by the **Explicit Async Database Transactions** pattern and dependency injection via FastAPI `Depends(get_db)`.",
      "confidence": 0.85,
      "supporting_evidence": [...],
      "relevant_files": ["backend/app/api/deps.py", "backend/app/db/session.py"],
      "inferred_patterns_referenced": ["Explicit Async Database Transactions"]
    }
    ```

---

### 3.18. Architecture Drift and Technical Debt REST APIs (Phase 10 Stage 10.5)

* `GET /api/v1/repositories/{id}/architecture/drift`
  * **Summary:** Fetch the latest cached or computed architectural drift report comparing current repository boundaries to baseline patterns.
  * **Response (200 OK):** `ArchitectureDriftResponse`
    ```json
    {
      "repository_id": "adcdfbc3-b946-4f34-8738-e9641436dcc4",
      "commit_sha": "c0ffee1234567890",
      "baseline_commit_sha": "c0ffee1234567890",
      "drift_status": "DRIFT_DETECTED",
      "total_violations": 2,
      "critical_violations": 0,
      "high_violations": 1,
      "medium_violations": 1,
      "low_violations": 0,
      "violations": [
        {
          "id": "layering_a1b2c3d4",
          "rule_id": "layering_violation",
          "category": "layering",
          "name": "Direct Database Query in API Route",
          "severity": "HIGH",
          "confidence": 0.92,
          "source_file": "backend/app/api/v1/users.py",
          "line_number": 5,
          "explanation": "API route handler directly executes database queries without delegating to a domain Service layer.",
          "remediation_recommendation": "Encapsulate the database query inside a dedicated service in `backend/app/services/`.",
          "evidence_snippet": "res = await db.execute(select(User))"
        }
      ],
      "resolved_violations": [],
      "summary": {
        "total_violations": 2,
        "critical_count": 0,
        "high_count": 1,
        "medium_count": 1,
        "low_count": 0
      },
      "is_stale": false,
      "last_analyzed_at": "2026-11-21T01:05:00+00:00"
    }
    ```

* `POST /api/v1/repositories/{id}/architecture/drift/analyze`
  * **Summary:** Trigger an on-demand static drift scan against the repository structure and persist a new snapshot.
  * **Query Parameters:** `baseline_commit_sha` (optional string).
  * **Response (200 OK):** `ArchitectureDriftResponse`

* `GET /api/v1/repositories/{id}/technical-debt`
  * **Summary:** Retrieve latest unified repository technical debt score, dimension breakdown, and top findings.
  * **Response (200 OK):** `TechnicalDebtSummaryResponse`
    ```json
    {
      "repository_id": "adcdfbc3-b946-4f34-8738-e9641436dcc4",
      "commit_sha": "c0ffee1234567890",
      "overall_debt_score": 28.5,
      "severity": "LOW",
      "confidence": 0.92,
      "dimension_scores": {
        "complexity": 24.0,
        "duplication": 0.0,
        "dependency": 15.0,
        "architecture_drift": 15.0,
        "test_debt": 12.0,
        "maintainability": 25.0
      },
      "summary_metrics": {
        "total_findings": 3,
        "critical_count": 0,
        "high_count": 1,
        "medium_count": 1,
        "low_count": 1
      },
      "total_findings": 3,
      "critical_findings": 0,
      "high_findings": 1,
      "medium_findings": 1,
      "low_findings": 1,
      "top_findings": [...],
      "last_analyzed_at": "2026-11-21T01:05:00+00:00"
    }
    ```

* `POST /api/v1/repositories/{id}/technical-debt/analyze`
  * **Summary:** Force re-evaluation of technical debt across all 5 dimensions and persist snapshot.
  * **Response (200 OK):** `TechnicalDebtSummaryResponse`

* `GET /api/v1/repositories/{id}/technical-debt/findings`
  * **Summary:** Retrieve paginated technical debt findings with optional dimension and severity filters.
  * **Query Parameters:**
    * `category` (`complexity`, `duplication`, `dependency`, `maintainability`, `test`)
    * `severity` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
    * `limit` (default: 50)
    * `offset` (default: 0)
  * **Response (200 OK):** `TechnicalDebtFindingsResponse`
    ```json
    {
      "repository_id": "adcdfbc3-b946-4f34-8738-e9641436dcc4",
      "total_count": 14,
      "limit": 10,
      "offset": 0,
      "findings": [...]
    }
    ```

* `GET /api/v1/repositories/{id}/technical-debt/findings/{finding_id}`
  * **Summary:** Retrieve granular detail, metrics, rationale, remediation, and evidence snippet for a specific technical debt finding.
  * **Response (200 OK):** `TechnicalDebtFindingItem`

* `GET /api/v1/repositories/{id}/technical-debt/trends`
  * **Summary:** Retrieve historical technical debt progression over recent commits for trend analysis.
  * **Response (200 OK):** `TechnicalDebtTrendsResponse`
    ```json
    {
      "repository_id": "adcdfbc3-b946-4f34-8738-e9641436dcc4",
      "trends": [
        {
          "commit_sha": "c0ffee1234567890",
          "analyzed_at": "2026-11-21T01:05:00+00:00",
          "overall_debt_score": 28.5,
          "severity": "LOW",
          "critical_findings": 0,
          "total_findings": 3
        }
      ]
    }
    ```

---

### 3.19 Refactoring Intelligence REST APIs (Phase 10 Stage 10.6)

* `GET /api/v1/repositories/{id}/refactoring/recommendations`
  * **Summary:** Retrieve explainable refactoring recommendations grounded in repository drift and debt findings.
  * **Query Parameters:**
    * `category` (optional string): Filter by `layering`, `dependency`, `duplication`, `complexity`, `convention`, `testability`.
  * **Response (200 OK):** `RefactoringRecommendationsResponse`
    ```json
    {
      "repository_id": "adcdfbc3-b946-4f34-8738-e9641436dcc4",
      "total_recommendations": 4,
      "recommendations": [
        {
          "recommendation_id": "rec_layer_a1b2c3d4",
          "category": "layering",
          "title": "Extract Service Layer for Order Operations",
          "finding_ids": ["v_layer_001"],
          "target_files": ["backend/app/api/v1/orders.py", "backend/app/services/order_service.py"],
          "target_symbols": ["create_order", "OrderService"],
          "current_problem": "API route contains direct persistence queries.",
          "proposed_architecture": "Delegate persistence logic to OrderService.",
          "reason": "Preserve Router-Service-Model encapsulation and testability.",
          "expected_benefits": ["Decouples HTTP routing from database operations"],
          "potential_risks": ["Update callers"],
          "affected_packages": ["backend"],
          "dependency_path_evidence": ["orders.py -> order_service.py"],
          "recommended_tests": ["backend/tests/unit/test_order_service.py"],
          "confidence": 0.95,
          "estimated_complexity": "MEDIUM",
          "requires_human_approval": false
        }
      ]
    }
    ```

* `POST /api/v1/repositories/{id}/refactoring/plans`
  * **Summary:** Synthesize an ordered, dependency-aware refactoring plan with risk scoring and step decomposition.
  * **Request Body:** `RefactoringPlanCreateRequest`
    ```json
    {
      "recommendation_ids": ["rec_layer_a1b2c3d4"],
      "title": "Decouple Order Routing from Persistence",
      "description": "Extract OrderService and migrate route handlers"
    }
    ```
  * **Response (201 Created):** `RefactoringPlanResponse`

* `GET /api/v1/repositories/{id}/refactoring/plans`
  * **Summary:** List existing refactoring plans for a repository.
  * **Query Parameters:**
    * `category` (optional string)
    * `approval_status` (optional string: `PENDING`, `APPROVED`, `REJECTED`, `INVALIDATED`)
  * **Response (200 OK):** `RefactoringPlansListResponse`

* `GET /api/v1/repositories/{id}/refactoring/plans/{plan_id}`
  * **Summary:** Retrieve granular details of a refactoring plan including ordered DAG steps and approval state.
  * **Response (200 OK):** `RefactoringPlanResponse`

* `POST /api/v1/repositories/{id}/refactoring/plans/{plan_id}/approve`
  * **Summary:** Approve a refactoring plan, cryptographically binding approval to an exact SHA-256 diff hash.
  * **Request Body:** `RefactoringApproveRequest`
    ```json
    {
      "diff_hash": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      "notes": "Reviewed and approved by Tech Lead"
    }
    ```
  * **Response (200 OK):** `RefactoringPlanResponse`

* `POST /api/v1/repositories/{id}/refactoring/plans/{plan_id}/reject`
  * **Summary:** Reject a refactoring plan with reviewer rationale.
  * **Request Body:** `{"reason": "Declined due to concurrent release freeze"}`
  * **Response (200 OK):** `RefactoringPlanResponse`

* `POST /api/v1/repositories/{id}/refactoring/plans/{plan_id}/execute`
  * **Summary:** Execute an approved refactoring plan in an isolated workspace with behavioral preservation checks.
  * **Request Body:** `RefactoringExecuteRequest`
    ```json
    {
      "diff_hash": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      "dry_run": false
    }
    ```
  * **Response (200 OK):** `RefactoringExecutionResponse`

* `GET /api/v1/repositories/{id}/refactoring/executions/{execution_id}`
  * **Summary:** Retrieve execution record, duration, test pass outcomes, and generated diff.
  * **Response (200 OK):** `RefactoringExecutionResponse`

* `GET /api/v1/repositories/{id}/refactoring/executions/{execution_id}/comparison`
  * **Summary:** Retrieve comparative assessment between baseline repository state and post-refactor state.
  * **Response (200 OK):** `BeforeAfterComparisonResponse`
    ```json
    {
      "plan_id": "b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e",
      "execution_id": "e1f2a3b4-c5d6-7e8f-9a0b-1c2d3e4f5a6b",
      "repository_id": "adcdfbc3-b946-4f34-8738-e9641436dcc4",
      "debt_score_before": 42.0,
      "debt_score_after": 26.0,
      "debt_score_delta": -16.0,
      "drift_violations_before": 3,
      "drift_violations_after": 1,
      "drift_violations_delta": -2,
      "public_api_compatible": true,
      "tests_baseline_passed": true,
      "tests_post_passed": true,
      "new_violations": [],
      "summary_verdict": "SUCCESSFUL_REFACTOR"
    }
    ```

---

#### 3.20 Phase 10 Stage 10.7 Benchmark Evaluation REST APIs

* `GET /api/v1/benchmarks/scenarios`
  * **Summary:** List registered ground-truth benchmark scenarios with category counts.
  * **Query Parameters:** `category` (optional), `is_active` (optional).
  * **Response (200 OK):** `BenchmarkScenariosListResponse`

* `GET /api/v1/benchmarks/scenarios/{scenario_key}`
  * **Summary:** Fetch a single scenario by key with expected output assertions and criteria.
  * **Response (200 OK):** `BenchmarkScenarioResponse`

* `POST /api/v1/benchmarks/scenarios`
  * **Summary:** Register a custom benchmark evaluation scenario.
  * **Request Body:** `BenchmarkScenarioCreate`
  * **Response (201 Created):** `BenchmarkScenarioResponse`

* `POST /api/v1/benchmarks/runs`
  * **Summary:** Trigger evaluation suite run across canonical categories.
  * **Request Body:** `BenchmarkSuiteRunRequest`
    ```json
    {
      "model_name": "gemini-1.5-pro",
      "suite_name": "devora_core_intelligence_suite",
      "code_revision": "HEAD",
      "categories": ["bug_detection", "security_safety"],
      "simulate_safety_failure": false
    }
    ```
  * **Response (201 Created):** `BenchmarkSuiteRunDetailResponse`

* `GET /api/v1/benchmarks/runs`
  * **Summary:** List historical benchmark suite runs with optional filtering.
  * **Query Parameters:** `model_name` (optional), `status` (optional).
  * **Response (200 OK):** `BenchmarkSuiteRunsListResponse`

* `GET /api/v1/benchmarks/runs/{run_id}`
  * **Summary:** Get complete execution results and telemetry for a specific run.
  * **Response (200 OK):** `BenchmarkSuiteRunDetailResponse`

* `POST /api/v1/benchmarks/runs/{run_id}/cancel`
  * **Summary:** Cancel an active or pending suite run.
  * **Response (200 OK):** `BenchmarkSuiteRunResponse`

* `POST /api/v1/benchmarks/compare`
  * **Summary:** Compare baseline and target runs, computing metric deltas and regressions.
  * **Request Body:**
    ```json
    {
      "baseline_run_id": "b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e",
      "target_run_id": "e1f2a3b4-c5d6-7e8f-9a0b-1c2d3e4f5a6b",
      "regression_threshold": 5.0
    }
    ```
  * **Response (200 OK):** `BenchmarkRunComparisonResponse`

* `GET /api/v1/benchmarks/runs/{run_id}/report`
  * **Summary:** Generate audit-ready Markdown evaluation report.
  * **Response (200 OK):** `BenchmarkReportResponse`

* `GET /api/v1/benchmarks/categories`
  * **Summary:** Retrieve canonical benchmark categories, descriptions, and weighting formula.
  * **Response (200 OK):** JSON dictionary with category definitions and weights.

* `GET /api/v1/benchmarks/models`
  * **Summary:** List supported evaluation AI models.
  * **Response (200 OK):** Array of supported model configurations.

* `POST /api/v1/benchmarks/seed`
  * **Summary:** Seed canonical 31 scenarios into database.
  * **Response (200 OK):** `{"status": "SEEDED", "total_scenarios": 31}`










