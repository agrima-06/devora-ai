# ==============================================================================
# Devora AI — Production Backend Dockerfile
# Multi-stage, non-root, security-hardened container for FastAPI & LangGraph
# ==============================================================================

# --- Stage 1: Build Dependencies ---
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build tools needed for compiled C extensions (e.g. tree-sitter, greenlet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a localized wheel/prefix directory
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- Stage 2: Final Minimal Runtime ---
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Install runtime utilities: curl (for healthchecks), git (for GitWorkspaceManager)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root user and group
RUN groupadd -g 1001 devora && \
    useradd -u 1001 -g devora -s /bin/bash -m devora

# Create ephemeral directories for repos and task workspaces
RUN mkdir -p /tmp/devora/repos /tmp/devora/tasks && \
    chown -R devora:devora /tmp/devora /app

# Copy application source code
COPY --chown=devora:devora . /app

# Configure environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    ENVIRONMENT=production \
    DEVORA_WORKSPACE_DIR=/tmp/devora/repos \
    DEVORA_TASKS_DIR=/tmp/devora/tasks

# Switch to non-root user
USER devora

EXPOSE 8000

# Docker healthcheck querying the root health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start production ASGI server with uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --access-log"]
