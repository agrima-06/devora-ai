# ==============================================================================
# Devora AI — Production Root Dockerfile (Defaults to Backend Service)
# ==============================================================================

# --- Stage 1: Build Dependencies ---
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- Stage 2: Final Minimal Runtime ---
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN groupadd -g 1001 devora && \
    useradd -u 1001 -g devora -s /bin/bash -m devora

RUN mkdir -p /tmp/devora/repos /tmp/devora/tasks && \
    chown -R devora:devora /tmp/devora /app

COPY --chown=devora:devora backend /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    ENVIRONMENT=production \
    DEVORA_WORKSPACE_DIR=/tmp/devora/repos \
    DEVORA_TASKS_DIR=/tmp/devora/tasks

USER devora

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --access-log"]
