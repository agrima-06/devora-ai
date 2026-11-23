# Devora AI — Deployment Environment Variables Reference
**Specification:** `STAGE_H3_ENVIRONMENT_VARIABLES`  
**System:** Devora AI  
**Scope:** Backend (FastAPI), Frontend (Next.js), Background Workers, and Sandbox Runners

---

## 1. Overview

Devora AI uses Pydantic's `BaseSettings` (`backend/app/config.py`) to manage configuration via system environment variables, local `.env` files, or cloud secrets managers (e.g. Render Environment, Vercel Project Settings, AWS Secrets Manager).

---

## 2. Master Environment Variables Matrix

| Variable Name | Required | Default Value | Valid Options / Format | Scope | Description & Security Best Practices |
|---|---|---|---|---|---|
| `ENVIRONMENT` | No | `development` | `development`, `staging`, `production` | Backend / Worker | Controls logging verbosity, Swagger docs exposure, and environment indicators. |
| `PROJECT_NAME` | No | `Devora AI` | String | Backend | Brand and service identity string. |
| `SHOWCASE_MODE` | **Recommended in Public Showcase** | `false` | `true`, `false` | Backend / Worker | **Critical Security Gate:** Disables arbitrary shell execution by unauthenticated visitors; restricts live workflows to approved demo repositories. |
| `SECRET_KEY` | **Yes (Production)** | Insecure dev key | 64-char Hex String | Backend / Worker | **High Security:** Secret key for signing and verifying JWT tokens. Must be generated using `openssl rand -hex 32`. Never commit to Git. |
| `ALGORITHM` | No | `HS256` | `HS256`, `RS256` | Backend | JWT cryptographic signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `1440` (24h) | Integer (Minutes) | Backend | Duration before authentication token expires. |
| `DATABASE_URL` | **Yes (Production)** | `postgresql+asyncpg://...` | Connection URI | Backend / Worker | **High Security:** PostgreSQL connection string. Must point to PostgreSQL 16 with `pgvector`. `postgres://` or `postgresql://` are automatically normalized to `postgresql+asyncpg://`. |
| `DB_ECHO` | No | `false` | `true`, `false` | Backend | If `true`, logs raw SQL statements. Must be `false` in production to prevent credential leakage. |
| `DB_POOL_SIZE` | No | `10` | Integer | Backend | Base persistent database connection pool size per process. |
| `DB_MAX_OVERFLOW` | No | `20` | Integer | Backend | Maximum burst connections beyond `DB_POOL_SIZE`. |
| `REDIS_URL` | No | `redis://localhost:6379/0` | URI | Backend / Worker | Redis instance URI for distributed caching, session tracking, and rate limiting. |
| `BACKEND_CORS_ORIGINS` | **Yes (Production)** | Localhost origins | Comma-separated or JSON list | Backend | Allowed CORS origins for the frontend browser. Example: `https://app.devora.ai,https://devora.vercel.app`. |
| `GEMINI_API_KEY` | Conditional | `None` | `AIzaSy...` | Backend / Worker | **High Security:** Google Gemini API Key. Required for live LLM reasoning and pgvector text embeddings. If omitted or invalid, the backend automatically uses `MockLLMProvider`. |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | `gemini-2.5-flash`, `gemini-1.5-pro` | Backend / Worker | Primary LLM model identifier for multi-agent reasoning. |
| `GEMINI_EMBEDDING_MODEL` | No | `text-embedding-004` | Model ID | Backend / Worker | Model used for generating 768-dim semantic vectors. |
| `USE_MOCK_LLM` | No | `false` | `true`, `false` | Backend / Worker | If `true`, forces mock LLM responses for offline or cost-free demonstration deployments. |
| `GITHUB_TOKEN` | No | `None` | `ghp_...` | Backend / Worker | **High Security:** GitHub Personal Access Token (PAT) used for interacting with repositories if GitHub App is not configured. |
| `GITHUB_APP_ID` | No | `None` | Numeric string | Backend / Worker | Numeric ID of the registered GitHub App. |
| `GITHUB_APP_PRIVATE_KEY` | No | `None` | PEM string or File Path | Backend / Worker | **High Security:** RSA private key for the GitHub App. |
| `DEVORA_MOCK_GITHUB` | No | `false` | `true`, `false` | Backend / Worker | Simulates GitHub App interactions without network calls. |
| `WORKSPACE_BASE_DIR` | No | `/tmp/devora/repos` | Filesystem Path | Backend / Worker | Directory where repository snapshots are cloned and analyzed. |
| `DEVORA_TASKS_DIR` | No | `/tmp/devora/tasks` | Filesystem Path | Backend / Worker | Ephemeral directory for task execution workspaces. |
| `DEVORA_SANDBOX_RUNNER` | No | `docker` | `docker`, `local`, `isolated_process` | Backend / Worker | Execution engine. In public container PaaS without Docker-in-Docker, set to `local` with `SHOWCASE_MODE=true`. |
| `SANDBOX_CONTAINER_MEMORY_LIMIT`| No | `1500m` | Memory string | Backend / Worker | Memory limit enforced on Docker execution containers. |
| `SANDBOX_CONTAINER_CPU_LIMIT` | No | `2.0` | CPU fraction | Backend / Worker | CPU cores limit enforced on Docker containers. |
| `RECOVERY_ENABLED` | No | `true` | `true`, `false` | Backend / Worker | Enables automatic detection and recovery of interrupted agent tasks. |
| `NEXT_PUBLIC_API_URL` | **Yes (Frontend)** | `http://localhost:8000` | URL | Frontend (Browser) | Publicly accessible URL of the backend API (e.g. `https://api.devora.ai`). Exposed to the browser bundle. |
| `BACKEND_URL` | No | `http://127.0.0.1:8000`| URL | Frontend (Server) | Internal backend URL used by Next.js server-side rewrites if proxying. |

---

## 3. Secret Generation & Security Checklist

1. **Generate Production Secret Key:**
   ```bash
   openssl rand -hex 32
   ```
2. **Never expose `NEXT_PUBLIC_` prefixes to private secrets:**
   Only public endpoints (like `NEXT_PUBLIC_API_URL`) should carry the `NEXT_PUBLIC_` prefix in Next.js. Any database credentials or API keys must remain strictly private to the backend.
3. **Validate Database Connection Strings:**
   Ensure connection strings use SSL:
   ```
   postgresql+asyncpg://user:password@host:port/dbname?ssl=require
   ```
