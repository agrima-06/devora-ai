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

