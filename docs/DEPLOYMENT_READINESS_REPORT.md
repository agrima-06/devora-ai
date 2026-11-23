# Devora AI — Deployment Readiness Report
**Audit Identifier:** `STAGE_H1_DEPLOYMENT_READINESS`  
**Date:** November 2026  
**System:** Devora AI Autonomous AI Software Engineering Platform  
**Scope:** Frontend (Next.js 14), Backend (FastAPI / LangGraph), Database (PostgreSQL 16 + pgvector), Containerization, Cloud Providers (Vercel, Render, Managed PostgreSQL)

---

## 1. Executive Summary

This deployment readiness audit evaluates Devora AI for its first public showcase deployment. The codebase includes 10 fully implemented and verified architectural phases, 16 Alembic migrations, 9 specialist engineering agents, pgvector semantic vector memory, an adaptive engineering engine, circuit breaker resilience, and a comprehensive benchmarking suite.

The system is architecturally sound and functionally complete. However, transitioning from local development to public multi-cloud hosting (Vercel frontend + Render Docker backend + Managed PostgreSQL) requires addressing key configuration gaps, URL routing assumptions, and public execution safety boundaries.

---

## 2. Component-by-Component Readiness Audit

| Component / Subsystem | Current State | Classification | Action Required |
|---|---|---|---|
| **Backend Entry Point** | `app.main:app` running via Uvicorn on port 8000. Lifespan context initializes DB check and structured logging. | **READY** | Configure production startup command with `--host 0.0.0.0 --port ${PORT:-8000}`. |
| **Frontend Entry Point** | Next.js 14 App Router with 17 compiled routes. | **READY** | Standard `next build` and `next start -p ${PORT:-3000}`. |
| **Docker Configuration** | No existing Dockerfiles or Docker Compose definitions in repository. | **NEEDS_CONFIGURATION** | Create multi-stage production `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`. |
| **Backend Dependencies** | `requirements.txt` contains pinned/bounded production dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `asyncpg`, `pgvector`, `langgraph`, `google-genai`). | **READY** | Verified clean installation in Python 3.11-slim. |
| **Frontend Dependencies** | `package.json` contains Next.js 14.2.5, React 18, React Query 5, Tailwind CSS, Lucide. | **READY** | Verified production build with zero errors. |
| **Database Migrations** | 16 migrations (`001_initial_schema` through `016_benchmark_engine`) in `backend/alembic/versions/`. | **READY** | Sequential chain verified via dry-run SQL generation. |
| **PostgreSQL 16 & pgvector** | PostgreSQL 16 dialect, `Vector(768)`, `uuid-ossp`, and `vector` extensions configured in `alembic/env.py`. | **READY** | Ensure target managed database has `pgvector` enabled (e.g., Neon, Supabase, Render PostgreSQL). |
| **Database URL Parsing** | `DATABASE_URL` requires `postgresql+asyncpg://`. Cloud providers often output `postgres://` or `postgresql://`. | **NEEDS_CODE_CHANGE** | Add URL normalizer in `config.py` and `db/session.py` to convert `postgres://` to `postgresql+asyncpg://` and handle SSL parameters. |
| **CORS Origins Configuration** | `BACKEND_CORS_ORIGINS: List[str]` defaults to localhost. If provided as comma-separated string in env, Pydantic might fail parsing. | **NEEDS_CODE_CHANGE** | Add Pydantic `field_validator` to parse comma-separated strings or JSON arrays for `BACKEND_CORS_ORIGINS`. |
| **Frontend API Client Routing** | `api-client.ts` uses relative `/api/v1` and `next.config.mjs` has hardcoded rewrite to `http://127.0.0.1:8000`. | **NEEDS_CODE_CHANGE** | Support `NEXT_PUBLIC_API_URL` for direct browser-to-backend CORS communication, and make `next.config.mjs` rewrite target configurable via `BACKEND_URL`. |
| **SSE Streaming & Buffering** | `/{task_id}/events` emits SSE with `X-Accel-Buffering: no`, `Cache-Control: no-cache`. Client uses `fetch` with `ReadableStream`. | **READY** | Direct client connection to Render avoids Vercel 10s serverless proxy timeout. |
| **Health Check Endpoints** | `/api/v1/health` exists and checks DB. Cloud providers check root `/health` or `/healthz`. | **NEEDS_CODE_CHANGE** | Add root `/health` and `/healthz` alias endpoints directly on the FastAPI application. |
| **File Storage Assumptions** | Workspaces write to `/tmp/devora/repos` and `/tmp/devora/tasks`. | **READY** | Container `/tmp` is isolated and ephemeral. Sufficient for demonstration runs. |
| **GitHub App Integration** | `GitHubAppService` supports App ID + PEM key, PAT fallback, and mock fallback (`DEVORA_MOCK_GITHUB=true`). | **READY** | Gracefully handles missing keys without crashing. |
| **Gemini Model Gateway** | `ModelGateway` supports `GEMINI_API_KEY`, circuit breaker, retries, and fallback to `MockLLMProvider`. | **READY** | Operates in live or mock mode safely. |
| **Public Showcase Safety** | Arbitrary code execution and local runner could be exploited if public visitors create tasks against arbitrary repos. | **SECURITY_RISK** | Implement `SHOWCASE_MODE` restricting task execution to approved demo repositories, disabling arbitrary shell execution. |
| **Environment Variables Docs** | No `.env.example` in repository. | **NEEDS_CONFIGURATION** | Create `.env.example` with documented variables and safe placeholders. |

---

## 3. Findings Classification Summary

### A. READY (No changes needed)
1. **Backend Entrypoint:** `app.main:app` handles lifespan, logging, exceptions, and router mounting.
2. **Frontend Entrypoint:** Next.js 14 App Router with all 17 routes compiling cleanly.
3. **Dependency Integrity:** All dependencies pinned and resolvable in isolated environments.
4. **Database Schema & Migrations:** All 16 migrations are sequential, non-destructive, and verified via static DDL generation.
5. **SSE Protocol:** `StreamingResponse` with `X-Accel-Buffering: no` and authorization headers.
6. **Graceful Fallbacks:** Mock LLM and mock GitHub modes ensure resilience when credentials are not supplied.

### B. NEEDS_CODE_CHANGE (Minor code adjustments required)
1. **`DATABASE_URL` Normalization:** Convert `postgres://` or `postgresql://` to `postgresql+asyncpg://` automatically in `backend/app/config.py` and `backend/alembic/env.py`.
2. **`BACKEND_CORS_ORIGINS` Validator:** Allow comma-separated strings (`https://app.devora.ai,https://devora.vercel.app`) in addition to JSON arrays.
3. **Root Healthcheck Aliases:** Add `@app.get("/healthz")` and `@app.get("/health")` on `app` in `main.py` for cloud load balancers.
4. **Frontend `NEXT_PUBLIC_API_URL`:** Allow frontend to point directly to hosted backend API URL.
5. **Showcase Safety Mode (Stage H6):** Add `SHOWCASE_MODE` setting in `config.py` to prevent public visitors from triggering arbitrary shell commands on unvetted repositories.

### C. NEEDS_CONFIGURATION (Deployment files to author)
1. **`backend/Dockerfile`:** Multi-stage production container for FastAPI backend.
2. **`frontend/Dockerfile`:** Multi-stage container for self-hosted or containerized Next.js frontend.
3. **`docker-compose.yml` & `docker-compose.prod.yml`:** Multi-container configuration for PostgreSQL 16 + pgvector, Redis, Backend, Frontend.
4. **`render.yaml`:** Render Blueprint specification for managed backend and PostgreSQL deployment.
5. **`vercel.json`:** Vercel deployment configuration for frontend.
6. **`.env.example`:** Safe, comprehensive environment variable template for backend and frontend.

### D. SECURITY_RISK (Addressed in Stage H6)
1. **Unrestricted Code Execution in Public Web Service:** If the backend is publicly accessible, arbitrary users could trigger tasks that execute shell commands via `LocalIsolatedRunner`. In `SHOWCASE_MODE=True`, task execution is restricted to safe analysis or approved demo repositories.

---

## 4. Conclusion & Next Steps
Devora AI is in high readiness for deployment. The identified `NEEDS_CODE_CHANGE` items are targeted, low-risk, and backward-compatible. Once these fixes and the deployment configuration artifacts are created, Devora AI can be deployed to Vercel, Render, or any standard container platform.
