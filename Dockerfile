# Multi-stage production container for Zendesk Ticket Summarizer Backend
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.0.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# 1. Copy shared package and pyproject files
COPY shared/pyproject.toml shared/poetry.lock* /app/shared/
COPY shared/zendesk_summarizer_shared /app/shared/zendesk_summarizer_shared/
COPY shared/README.md /app/shared/

# Install shared package
WORKDIR /app/shared
RUN poetry install --no-root && poetry build && pip install dist/*.whl

# 2. Copy and install backend
WORKDIR /app/backend
COPY backend/pyproject.toml backend/poetry.lock* /app/backend/
RUN poetry install --no-root --without dev

COPY backend/app /app/backend/app/
COPY backend/README.md /app/backend/

# 3. Create persistent data volume directory
RUN mkdir -p /app/data && chmod 777 /app/data

# Environment configuration
ENV SQLITE_DB_PATH="/app/data/audit.db"
ENV BACKEND_HOST="0.0.0.0"
ENV BACKEND_PORT=8000

EXPOSE 8000

# Health check against FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI production server via Uvicorn
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
