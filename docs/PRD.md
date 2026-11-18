# Product Requirements Document (PRD)
## Devora AI: Autonomous AI Software Engineer

---

### 1. Executive Summary & Vision

**Devora AI** is an autonomous AI Software Engineer designed to operate alongside human developers as a capable, rigorous, and trusted junior engineer. Unlike passive autocomplete or conversational code assistants, Devora actively understands code repositories, plans multi-step development tasks, detects and classifies bugs using both classical machine learning and LLM reasoning, modifies code within isolated sandboxes, executes automated test suites, iteratively debugs failures, reviews its own changes for quality and security, and learns from every verified engineering outcome.

The core guiding principle is: **"Never claim success without execution evidence."** Devora operates under strict human-in-the-loop governance for security-critical actions (dependency changes, publishing pull requests, arbitrary shell executions), providing auditable, transparent engineering reports for every task.

---

### 2. Target Persona & Use Cases

#### 2.1 Target Persona
* **Primary Persona:** Software Engineers, Tech Leads, and Engineering Managers working in modern agile software teams (Python, TypeScript, Go, etc.).
* **Characteristics:** Value test coverage, clean architecture, auditability, and deterministic validation over hallucinated quick fixes.
* **Working Model:** The developer delegates self-contained bug tickets, feature spikes, refactorings, or architectural explorations to Devora, reviews Devora's plan and execution evidence, and approves final PRs.

#### 2.2 Core Use Cases
1. **Automated Bug Fixing:** Ingest an issue description or traceback, classify the bug type, localize the faulty file/function, reproduce via test, write a patch, verify all tests pass, and present a pull request.
2. **Small Feature Implementation:** Implement an incremental feature or API endpoint against existing code conventions and tests, maintaining backwards compatibility.
3. **Repository Architecture Exploration & Ingestion:** Ingest unfamiliar codebases, generate semantic dependency maps, explain architectural flows, and provide actionable engineering summaries.
4. **Iterative Test-Driven Repair:** When existing tests fail, iterate up to 3 times in an isolated sandbox, modifying source code until tests pass without introducing regressions.
5. **Continuous Quality & Security Guardrails:** Scan generated code with Semgrep, Ruff, and Mypy before human review, enforcing zero introduction of CWE Top 25 vulnerabilities.

---

### 3. Core Capabilities (11 Pillars)

| # | Capability | Description |
|---|---|---|
| **1** | **Repository Understanding** | Multi-language parsing (Tree-sitter & AST), dependency graphing, symbol extraction, and semantic code search. |
| **2** | **Bug Detection & Root-Cause Analysis** | Traceback extraction, static analysis, and causal hypothesis formulation. |
| **3** | **Autonomous Task Planning** | Decomposition of high-level natural language prompts into directed acyclic graph (DAG) task steps with verification checkpoints. |
| **4** | **Code Generation & Modification** | Generation of clean, minimal, convention-conforming patches targeting specific AST nodes or line ranges. |
| **5** | **Automated Test Execution** | Headless execution of `pytest`, unit, and integration tests inside an isolated sandbox container. |
| **6** | **Iterative Debugging** | Bounded feedback loop (max 3 cycles) analyzing test failure outputs and adjusting patches until green. |
| **7** | **Code Quality & Security Review** | Independent static analysis (Ruff, Mypy) and security scanning (Semgrep) prior to human handoff. |
| **8** | **GitHub Integration** | Branch creation, commit generation, diff visualization, and PR creation via GitHub REST/GraphQL APIs. |
| **9** | **Engineering Reports** | Synthesized audit-ready markdown reports documenting problem formulation, root cause, diffs, test outputs, and limitations. |
| **10** | **Project Memory & Learning** | PostgreSQL + pgvector persistence of architectural patterns, verified fix strategies, and human feedback scoring. |
| **11** | **ML Bug Classification** | Scikit-learn TF-IDF + Logistic Regression/Random Forest model predicting 8 discrete bug categories to route agent strategies. |

---

### 4. Functional Requirements & Epics

#### Epic 1: Repository Onboarding & Ingestion
* **FR-1.1:** System shall authenticate with GitHub via GitHub App or Personal Access Token (PAT).
* **FR-1.2:** System shall clone repositories into an isolated volume, prune `.git` binaries from LLM context, and respect `.gitignore`.
* **FR-1.3:** System shall parse repository structure into an abstract syntax tree (AST) and generate symbol maps (classes, functions, imports) using Tree-sitter.
* **FR-1.4:** System shall chunk and embed code symbols into `pgvector` for semantic search with metadata (file_path, language, commit_sha, symbol_type).
* **FR-1.5:** Multi-tenant separation: Under no circumstances shall Repository A's embeddings or code be accessible or queryable by unauthorized User B.

#### Epic 2: Task Ingestion & Planning
* **FR-2.1:** Developers can submit tasks via Web UI or API containing natural language requirements, optional error tracebacks, and target repository.
* **FR-2.2:** System routes incoming errors through the ML Bug Classifier to tag the bug category (e.g., `NullPointer/AttributeError`, `SyntaxError`, `TypeMismatch`, `DatabaseError`).
* **FR-2.3:** Planning Agent creates a structured `TaskPlan` with discrete, numbered steps, required tools, and test verification criteria.
* **FR-2.4:** Tasks are persisted in the database with status: `PENDING`, `PLANNING`, `IN_PROGRESS`, `TESTING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`.

#### Epic 3: Multi-Agent Orchestration (LangGraph)
* **FR-3.1:** Workflow must be modeled as a deterministic LangGraph `StateGraph` with a typed shared state (`DevoraWorkflowState`).
* **FR-3.2:** Explicit handoffs between 9 specialist agents: Orchestrator, Codebase Analyst, Bug Investigator, Planner, Coder, Tester, Code Reviewer, Security Reviewer, Reporter.
* **FR-3.3:** Bounded loop: If testing fails, execution loops back to Coder with test failure diagnostic context. Max iteration count = 3.
* **FR-3.4:** LangGraph checkpointer must record step-by-step state in PostgreSQL, supporting resumption and time-travel replay.

#### Epic 4: Isolated Code Modification & Execution Sandbox
* **FR-4.1:** Code changes must execute exclusively inside an isolated container (Docker/gVisor) with network disabled (`--network none`) by default.
* **FR-4.2:** Ephemeral file system: Each task gets a dedicated workspace cloned from the baseline commit.
* **FR-4.3:** Resource limits enforced per execution: CPU quota (max 2 cores), Memory (max 1.5GB), Timeout (max 60 seconds per test command).
* **FR-4.4:** Real-time stdout/stderr capture with exit code determination.
* **FR-4.5:** Rollback capability: Rollback workspace to baseline commit if an iteration introduces destructive or irrecoverable errors.

#### Epic 5: Quality, Security & Verification
* **FR-5.1:** Automated execution of Ruff for Python linting and code style.
* **FR-5.2:** Automated execution of Mypy for static type validation.
* **FR-5.3:** Execution of Semgrep with rulesets (`p/default`, `p/owasp-top-ten`, `p/cwe-top-25`) against modified files.
* **FR-5.4:** Any high-severity security finding must trigger a block and flag the task as requiring remediation.

#### Epic 6: Human Approval & GitHub Publication
* **FR-6.1:** When all tests pass and reviews complete, task enters `WAITING_APPROVAL` status.
* **FR-6.2:** The developer is presented with an interactive unified diff viewer, test logs, Semgrep security summary, and the final Engineering Report.
* **FR-6.3:** Developer can:
  * **Approve & Create PR:** Devora pushes a new branch `devora/task-<id>` and opens a GitHub Pull Request with the structured report.
  * **Reject with Feedback:** Developer provides feedback; task is marked `REJECTED` or loops back to replan.
  * **Request Changes:** Developer adds specific guidance to iterate.

#### Epic 7: Memory & Experience Learning
* **FR-7.1:** Project Memory: Store verified repository facts, conventions, and architectural notes in `repository_knowledge`.
* **FR-7.2:** Experience Memory: Capture verified task resolutions (problem + root cause + diff + test outcome + feedback).
* **FR-7.3:** Vector retrieval: Query relevant prior experiences during the Planning and Bug Investigation phases via `pgvector` cosine similarity.
* **FR-7.4:** Tenant isolation: Only authorized, scrubbed, anonymized experiences can be considered for cross-project memory when explicitly permitted by repository owner.

---

### 5. Non-Functional Requirements (NFRs)

| Dimension | Specification | Verification Method |
|---|---|---|
| **Security** | Zero host filesystem escape; no sandbox network access; secrets redacted from logs. | Pentesting, automated Semgrep, Docker rootless checks. |
| **Performance** | API response time for CRUD < 150ms; Live agent events streamed over SSE with < 300ms latency. | K6 load testing, latency telemetry. |
| **Reliability** | Task state preserved across worker restarts; idempotent agent actions; checkpoint recovery. | Worker kill tests during active LangGraph runs. |
| **Scalability** | Asynchronous queue-based task execution (Celery/AsyncIO workers); stateless backend API. | Horizontal scaling test on FastAPI workers. |
| **Usability** | Next.js dark-themed UI; responsive down to mobile viewports; zero ambiguous loading states. | Playwright E2E tests, Lighthouse score > 90. |
| **Maintainability**| Strict typing (TypeScript strict mode, Python Mypy strict); 100% docstrings on API contracts. | CI pipeline enforcement. |

---

### 6. User Journey & Interaction Flow

```
[Developer] -> Submits Bug / Feature Request in Web UI
      |
      v
[Backend API] -> Creates Task record (PENDING) -> Dispatches to LangGraph Engine
      |
      v
[ML Bug Classifier] -> Categorizes error (e.g., Logic Error / Null Pointer)
      |
      v
[Codebase Analyst] -> Queries pgvector & Tree-sitter for symbol localization
      |
      v
[Planning Agent] -> Generates 4-step DAG plan with test assertions
      |
      v
[Coding Agent] -> Modifies isolated workspace files (ephemeral container)
      |
      v
[Testing Agent] -> Runs Pytest inside sandbox (network=none, 60s timeout)
      |
      +---> [Tests Fail? (Iteration < 3)] -> Feeds stderr back to Coding Agent
      |
      +---> [Tests Pass?] -> Proceeds to Review
      |
      v
[Code & Security Review] -> Ruff, Mypy, Semgrep audit
      |
      v
[Reporting Agent] -> Synthesizes Markdown Engineering Report
      |
      v
[Human-in-the-Loop] -> Web UI Diff & Report Review -> [Approve / Reject]
      |
      v (If Approved)
[GitHub Publisher] -> Pushes branch & opens Pull Request
      |
      v
[Experience Memory] -> Embeds approved resolution into pgvector for future recall
```

---

### 7. Success Metrics & KPIs

1. **Patch Verification Rate:** > 80% of generated patches pass all existing and newly generated regression tests on initial or 2nd iteration.
2. **Zero False Claims:** 100% of reported test results must match actual sandbox container stdout and exit codes.
3. **Security Invariant:** 0 hardcoded credentials or critical Semgrep vulnerabilities introduced in generated code.
4. **Developer Acceptance Rate:** > 75% of PRs generated by Devora accepted without manual patch re-authoring.
5. **MTTR Reduction:** Average time to diagnose and propose a verified fix reduced by > 50% compared to baseline manual triage.
