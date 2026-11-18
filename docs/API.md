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
  * **Summary:** Retrieve all isolated sandbox test run outputs, exit codes, and durations.
  * **Response (200 OK):** List of test executions, exit codes, test counts, and stdout/stderr.

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

#### 3.7 ML Bug Classification Service
* `POST /api/v1/ml/classify-bug`
  * **Summary:** Predict bug category from error traceback and description.
  * **Request Body:**
    ```json
    {
      "error_message": "ZeroDivisionError: division by zero",
      "traceback": "File 'invoice.py', line 45, in calc\nZeroDivisionError: division by zero"
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "predicted_category": "Logic errors",
      "confidence": 0.942,
      "model_version": "v1.0.0",
      "top_probabilities": {
        "Logic errors": 0.942,
        "Runtime errors": 0.041,
        "Null or missing-value errors": 0.012
      }
    }
    ```
