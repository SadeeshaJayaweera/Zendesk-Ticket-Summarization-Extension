# =============================================================================
# Multi-Stage Production Container for Zendesk Support Intelligence Platform
# =============================================================================

# --- Stage 1: Build & Dependencies ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package manifests and install core build dependencies
RUN pip install --upgrade pip setuptools wheel poetry-core

# 1. Install shared library
COPY shared /build/shared
RUN pip install --no-deps -e /build/shared

# 2. Install backend dependencies
COPY backend /build/backend
RUN pip install --no-deps -e /build/backend

# 3. Install mcp-server
COPY mcp-server /build/mcp-server
RUN pip install --no-deps -e /build/mcp-server

# Install runtime dependencies
RUN pip install \
    fastapi \
    uvicorn[standard] \
    pydantic \
    pydantic-settings \
    python-dotenv \
    httpx \
    sqlalchemy[asyncio] \
    alembic \
    asyncpg \
    aiosqlite \
    greenlet \
    pyjwt \
    bcrypt \
    redis \
    celery \
    mcp \
    respx

# --- Stage 2: Minimal Distroless / Unprivileged Runtime ---
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    BACKEND_HOST="0.0.0.0" \
    BACKEND_PORT=8000

# Install runtime utilities (curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy source code and configuration files
COPY shared /app/shared
COPY backend /app/backend
COPY mcp-server /app/mcp-server
COPY alembic.ini /app/
COPY migrations /app/migrations

# Create data directories with appropriate permissions
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Health check against FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run database migrations then start Uvicorn production server
CMD ["sh", "-c", "alembic upgrade head && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
