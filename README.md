# Devora AI

> **Autonomous AI Software Engineer operating under the foundational axiom: *"Never claim success without execution evidence"***

Devora AI is an autonomous, multi-agent software engineering system that ingests codebases, investigates issues, authors minimal verified patches, runs automated tests in an isolated sandbox, performs code quality and security reviews, and seeks human approval before publishing.

---

## Key Capabilities

1. **Repository Intelligence Engine**: Multi-language AST (Python) and Tree-sitter parsing (TypeScript, JavaScript, Go, Java), file system scanning, symbol extraction, and semantic search.
2. **LangGraph 9-Specialist-Agent Pipeline**: Directed, stateful computational graph with conditional routing:
   - **Orchestrator**: Task classification and strategic branching.
   - **Codebase Analyst**: Structural code understanding, symbol graph resolution, and entrypoint identification.
   - **Bug Investigator**: Stack trace analysis, failing frame isolation, and root-cause hypothesis generation.
   - **Planning Agent**: Acyclic task decomposition (DAG) with test criteria.
   - **Coding Agent**: Minimal, surgical code modifications with unified diffs.
   - **Testing Agent**: Isolated sandbox test execution and evidence validation.
   - **Code Reviewer**: Static code quality audit, Ruff/Mypy compliance, and quality scoring.
   - **Security Reviewer**: Semgrep OWASP vulnerability detection and security scanning.
   - **Reporting Agent**: Synthesis of audit-ready Markdown engineering reports.
3. **Execution Sandbox**:
   - Production Docker sandbox (`--network none`, 1.5GB RAM, 2 vCPUs, `--pids-limit 100`, `--security-opt=no-new-privileges:true`, `--cap-drop=ALL`).
   - Hardened isolated process runner with path traversal and command injection prevention.
4. **Human Approval Gate**: Interrupted state machine requiring explicit developer review and sign-off before changes or reports can be published.
5. **Real-time Event Streaming**: Server-Sent Events (SSE) broadcasting agent transitions and terminal output to the client.
6. **State Persistence & Recovery**: Checkpointed state in PostgreSQL with pgvector, enabling seamless workflow resumption across backend restarts.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 (Async), Alembic, Pydantic v2
- **Multi-Agent Orchestration**: LangGraph, Google GenAI SDK (Gemini 2.5 Flash)
- **Database & Vector Storage**: PostgreSQL 16 with pgvector, asyncpg
- **Code Parsing**: Tree-sitter, Python `ast`
- **Execution & Security**: Docker, Pytest, Ruff, Mypy, Semgrep
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, TanStack Query, Lucide Icons

---

## Project Structure

```
devora-ai/
├── backend/
│   ├── alembic/              # Database migration versions (001, 002, 003)
│   ├── app/
│   │   ├── agents/           # LangGraph state, 9 specialist nodes, and model gateway
│   │   │   ├── gateway/      # Centralized Gemini & Mock provider abstractions
│   │   │   ├── specialists/  # The 9 autonomous engineering agents
│   │   │   ├── events.py     # SSE pub/sub event broadcaster
│   │   │   ├── graph.py      # Directed state graph with bounded retry loop
│   │   │   └── state.py      # Strongly-typed workflow state & Pydantic contracts
│   │   ├── api/              # FastAPI v1 REST routes & SSE streaming
│   │   ├── core/             # Security, logging, and centralized exception handling
│   │   ├── db/               # Async engine and base models
│   │   ├── models/           # 18 SQLAlchemy 2.0 database entities
│   │   ├── schemas/          # Pydantic request & response schemas
│   │   ├── services/         # Sandbox, GitHub, Repo Intelligence, & Workflow services
│   │   └── main.py           # FastAPI entrypoint
│   └── tests/                # 74 unit and integration tests (100% pass rate)
├── docs/                     # Architectural documentation (PRD, Architecture, Agents, Database, etc.)
└── frontend/                 # Next.js developer workspace & real-time monitoring dashboard
```

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (for sandboxed test execution & PostgreSQL)

### 1. Database Setup

Start PostgreSQL 16 with pgvector:

```bash
docker run -d --name devora-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=devora -p 5432:5432 pgvector/pgvector:pg16
```

Apply database migrations:

```bash
cd backend
alembic upgrade head
```

### 2. Backend Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run backend development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run test suite:

```bash
pytest backend/tests -v
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to open the Devora AI Engineering Workspace.

---

## License

Apache 2.0
