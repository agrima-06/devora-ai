# Devora AI — Deployment Architecture
**Architecture Specification:** `STAGE_H2_DEPLOYMENT_ARCHITECTURE`  
**System:** Devora AI Autonomous Software Engineering Platform  
**Target Environments:** Public Showcase, Staging, and Production Multi-Cloud

---

## 1. System Topology Overview

Devora AI uses a decoupled, cloud-native architecture separating client presentation, API/agent orchestration, vector-enabled persistent storage, and code execution sandboxing:

```mermaid
flowchart TD
    subgraph ClientLayer["Client & Edge Layer (Vercel)"]
        UserBrowser["Developer Browser / User"]
        VercelEdge["Vercel Global Edge CDN\n(Next.js 14 App Router)"]
    end

    subgraph APILayer["Backend & Orchestration Layer (Render / Docker)"]
        FastAPI["FastAPI Production Service\n(Uvicorn, Port 8000)"]
        ModelGateway["Model Gateway\n(Gemini 2.5 Flash / Circuit Breaker)"]
        LangGraphEngine["LangGraph Multi-Agent Engine\n(9 Specialist Agents)"]
        WorkerProcess["Background Task Worker\n(Workflow Recovery / Polling)"]
    end

    subgraph DataLayer["Storage & Vector Memory Layer (Managed PostgreSQL)"]
        PGDatabase[("PostgreSQL 16 Database\n(SQLAlchemy 2.0 / Alembic)")]
        PGVectorExt["pgvector Extension\n(768-dim Vector Memory)"]
        RedisCache[("Redis 7 (Optional)\n(Rate Limiting / Task Queue)")]
    end

    subgraph ExecutionLayer["Code Execution & Sandbox Layer"]
        ShowcaseSafety["Showcase Safety Gate\n(Demo Repository Whitelist)"]
        IsolatedRunner["Local Isolated Runner\n(Stripped Env, Path Confinement)"]
        DockerSandbox["Dedicated Docker Sandbox\n(Resource Limits, Network None)"]
    end

    UserBrowser -->|"HTTPS (Next.js Pages)"| VercelEdge
    UserBrowser -->|"Direct HTTPS REST / SSE (Bearer JWT)"| FastAPI
    FastAPI --> LangGraphEngine
    FastAPI --> ModelGateway
    FastAPI --> PGDatabase
    FastAPI --> RedisCache
    WorkerProcess --> PGDatabase
    WorkerProcess --> LangGraphEngine
    LangGraphEngine --> ShowcaseSafety
    ShowcaseSafety -->|"If Showcase Mode"| IsolatedRunner
    ShowcaseSafety -->|"If Dedicated Docker"| DockerSandbox
    PGDatabase --- PGVectorExt
```

---

## 2. Multi-Cloud Hosting Strategy

### Primary Hosting Topology (Recommended Initial Deployment)

| Tier | Provider | Service Type | Sizing / Plan | Key Characteristics |
|---|---|---|---|---|
| **Frontend** | **Vercel** | Managed Next.js Hosting | Hobby (Free) / Pro ($20/mo) | Global Edge CDN, zero-config Next.js 14 support, instant preview deployments, automatic SSL. |
| **Backend API** | **Render** | Web Service (Docker) | Starter ($7/mo) / Standard ($25/mo) | Persistent container runtime, native HTTP/1.1 for long-lived SSE streaming, automatic HTTPS, Git webhook auto-deploy. |
| **Database** | **Render Postgres / Neon / Supabase** | Managed PostgreSQL 16 | Free Tier / Starter ($7–$19/mo) | Native `pgvector` support, automated point-in-time recovery, connection pooling, SSL encryption in transit. |
| **Background Worker** | **Render** | Background Worker | Starter ($7/mo) | Dedicated process for decoupled long-running agent workflows and recovery manager sweeps. |
| **Cache (Optional)** | **Upstash / Render Redis** | Redis 7 | Free Tier / $7/mo | Distributed session state and rate limiting. |

### Alternative Topology A: Self-Hosted Single-Node Docker Compose
For unified on-premises or single-cloud VM deployment (e.g. AWS EC2 `t4g.large`, Hetzner CX31, or DigitalOcean 8GB Droplet):
- Reverse Proxy: Caddy v2 (automatic Let's Encrypt HTTPS).
- Services: `frontend`, `backend`, `worker`, `postgres` (with `pgvector/pgvector:pg16`), `redis`.
- Total Cost: ~$15–$30/month.

### Alternative Topology B: Enterprise Managed AWS / GCP
- Frontend: AWS Amplify or S3 + CloudFront.
- Backend: AWS ECS Fargate or GCP Cloud Run.
- Database: AWS RDS PostgreSQL 16 with `pgvector` or GCP Cloud SQL.
- Sandbox: AWS ECS task with Docker-in-Docker or dedicated EC2 runner pool.

---

## 3. Communication & Networking Architecture

### Direct Cross-Origin API & SSE Architecture
In production, the frontend browser client connects **directly** to the backend API domain (`https://api.devora.ai`) rather than proxying through Next.js edge rewrites.

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant Vercel as Vercel (Frontend)
    participant Backend as Render (FastAPI Backend)
    participant DB as Managed PostgreSQL

    User->>Vercel: GET /tasks/123
    Vercel-->>User: Next.js HTML/JS Bundle (pre-rendered)
    User->>Backend: OPTIONS /api/v1/tasks/123/events (CORS Preflight)
    Backend-->>User: 200 OK (Access-Control-Allow-Origin: https://app.devora.ai)
    User->>Backend: GET /api/v1/tasks/123/events (Authorization: Bearer <jwt>)
    Backend->>DB: Verify Task Ownership
    Backend-->>User: HTTP 200 text/event-stream (Keep-Alive, No-Buffering)
    loop Workflow Execution
        Backend-->>User: data: {"event": "AGENT_CODER_COMPLETED", ...}\n\n
    end
```

**Why Direct Cross-Origin is Required:**
1. **Serverless Timeout Avoidance:** Vercel serverless edge functions enforce strict execution limits (10 seconds on Hobby, 60 seconds on Pro). Multi-agent LangGraph workflows run between 15 seconds and 5 minutes. Direct browser connection to Render maintains persistent SSE connections indefinitely.
2. **Reverse Proxy Buffering Bypass:** Direct connection with `X-Accel-Buffering: no` ensures real-time chunk delivery without intermediary caching.

---

## 4. Database & pgvector Connectivity

### Connection Pool Configuration
- **Driver:** `asyncpg` via SQLAlchemy 2.0 `create_async_engine`.
- **Pool Size:** `DB_POOL_SIZE=10` with `DB_MAX_OVERFLOW=20` per container instance.
- **Connection Lifetime:** Recycle connections periodically to prevent stale cloud sockets: `pool_recycle=1800` (30 minutes).
- **SSL Enforcement:** Cloud PostgreSQL requires SSL (`ssl=require`). The backend automatically normalizes incoming connection strings (`postgres://` $\to$ `postgresql+asyncpg://`) and applies SSL arguments.

### pgvector Extension Initialization
Managed databases must support and activate:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
```
All vector operations index 768-dimensional embeddings using cosine distance (`<=>` operator) with HNSW indexes where appropriate for sub-10ms similarity searches.

---

## 5. Public Showcase Safety Architecture (Stage H6)

When deployed publicly for demonstrations, unauthenticated or untrusted users must not have access to arbitrary code execution environments.

```mermaid
flowchart TD
    TaskReq["Incoming Task Execution Request"] --> AuthCheck{"Authenticated User?"}
    AuthCheck -- No --> Reject401["Reject 401 Unauthorized"]
    AuthCheck -- Yes --> ShowcaseCheck{"SHOWCASE_MODE Enabled?"}
    ShowcaseCheck -- Yes --> RepoCheck{"Repository in DEMO_REPOSITORIES whitelist?"}
    RepoCheck -- Yes --> SafeExecution["Execute with Confined Local Runner\n(Whitelisted Commands, Resource Bounds)"]
    RepoCheck -- No --> ShowcaseBlock["Block Execution (403 Forbidden: Demo Repository Required)"]
    ShowcaseCheck -- No --> DedicatedSandbox["Execute in Dedicated Docker Container\n(Network: None, Strict ulimits)"]
```

### Safety Policies Enforced in Showcase Deployment:
1. **Arbitrary Shell Execution Disabled:** Direct Docker daemon sockets (`/var/run/docker.sock`) are **never** mounted or exposed to public web containers.
2. **Whitelisted Demonstration Repositories:** Autonomous tasks can only be run against approved, pre-indexed demo repositories (e.g. `devora-ai/demo-calc`, `devora-ai/showcase-service`).
3. **Approval Gates Preserved:** Automated Git commits, pushes, and GitHub pull requests require explicit human confirmation. Autonomous force pushes and merges are hard-blocked.
4. **Credential Redaction Invariant:** All command outputs, tracebacks, and logs are scrubbed via `sanitize_output` and `scrub_credentials` before broadcasting over SSE or saving to database records.

---

## 6. Environment Variable Inventory & Management

| Category | Variable Name | Purpose | Example / Format |
|---|---|---|---|
| **Core** | `ENVIRONMENT` | Runtime mode | `production` / `staging` |
| **Core** | `PROJECT_NAME` | Service branding | `Devora AI` |
| **Core** | `SHOWCASE_MODE` | Public showcase safety gate | `true` |
| **Security** | `SECRET_KEY` | JWT signing secret | 64-char hex string (`openssl rand -hex 32`) |
| **Security** | `ACCESS_TOKEN_EXPIRE_MINUTES`| Session duration | `1440` (24 hours) |
| **Networking** | `BACKEND_CORS_ORIGINS` | Allowed frontend domains | `https://app.devora.ai,https://devora.vercel.app` |
| **Database** | `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://user:pass@host:5432/db?ssl=require` |
| **AI Gateway** | `GEMINI_API_KEY` | Model provider key | Google Gemini API key |
| **AI Gateway** | `GEMINI_MODEL` | Primary LLM | `gemini-2.5-flash` |
| **AI Gateway** | `GEMINI_EMBEDDING_MODEL`| Embedding model | `text-embedding-004` |
| **AI Gateway** | `USE_MOCK_LLM` | Offline demonstration fallback | `false` (or `true` if no key provided) |
| **GitHub App** | `GITHUB_APP_ID` | GitHub App numeric ID | `123456` |
| **GitHub App** | `GITHUB_APP_PRIVATE_KEY`| PEM private key | `[PEM-encoded-key-or-file-path]` |
| **GitHub App** | `DEVORA_MOCK_GITHUB` | Mock GitHub API fallback | `false` |
| **Frontend** | `NEXT_PUBLIC_API_URL` | Backend URL for browser | `https://api.devora.ai` |

---

## 7. Backup, Disaster Recovery & High Availability

1. **Database Automated Backups:** Managed PostgreSQL provider configured for automated daily snapshots with 7-day retention.
2. **Pre-Deployment Migration Snapshots:** Prior to running `alembic upgrade head`, a point-in-time backup is captured.
3. **Task Resumption on Restart:** If the container process restarts during an active task, `WorkflowRecoveryManager` scans for leases where `last_heartbeat_at > 120s`, marks them as `INTERRUPTED`, and enables 1-click resumption from the last recorded PostgreSQL checkpoint without data loss.

---

## 8. Expected Infrastructure Costs & Sizing

| Component | Provider & Tier | Monthly Cost (USD) | Scaling Threshold |
|---|---|---|---|
| **Frontend** | Vercel Hobby / Pro | \$0 – \$20 | 100 GB bandwidth / 1M requests |
| **Backend API** | Render Web Service (Starter, 512MB RAM, 0.5 CPU) | \$7 | ~50 concurrent active users |
| **Managed DB** | Render PostgreSQL (Starter, 1GB RAM, 10GB SSD) | \$7 | ~100,000 entities / vectors |
| **Gemini AI** | Google Cloud / Gemini API Pay-as-you-go | \$5 – \$25 | ~500–2,000 multi-agent task runs |
| **Total Estimated Initial Showcase Cost** | | **\$19 – \$52 / month** | |
