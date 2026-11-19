# Development Setup Guide

## 1. Prerequisites

Before setting up the project locally, ensure you have the following installed:
* **Python**: 3.11.x or higher
* **Node.js**: 18+ (optional, for Zendesk CLI / `zcli`)
* **Docker & Docker Compose**: (For running local PostgreSQL 16 and Redis 7)
* **Git**

---

## 2. Clone & Environment Setup

```bash
# Clone the repository
git clone https://github.com/SadeeshaJayaweera/Zendesk-Ticket-Summarization-Extension.git
cd Zendesk-Ticket-Summarization-Extension

# Create a local virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install build tools
pip install --upgrade pip poetry-core wheel

# Install monorepo components in editable mode
pip install -e ./shared -e ./backend -e ./mcp-server --no-deps

# Install full runtime and development dependencies
pip install \
  fastapi uvicorn[standard] pydantic pydantic-settings python-dotenv \
  httpx sqlalchemy[asyncio] alembic asyncpg aiosqlite greenlet \
  pyjwt bcrypt redis celery mcp respx pytest pytest-asyncio pytest-cov
```

---

## 3. Configuration

Copy the example environment configuration:
```bash
cp .env.example .env
```
Edit `.env` and provide your credentials:
```env
# Zendesk Credentials
ZENDESK_SUBDOMAIN=your-subdomain
ZENDESK_EMAIL=agent@yourcompany.com
ZENDESK_API_TOKEN=your_zendesk_token

# AI Provider API Keys
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

---

## 4. Database Setup & Migrations

### Option A: Local SQLite (Fastest for Development)
```bash
# Apply migrations to local SQLite database
alembic upgrade head
```

### Option B: Docker PostgreSQL & Redis
```bash
# Start PostgreSQL and Redis containers
docker compose up -d postgres redis

# Run migrations against PostgreSQL
DATABASE_URL=postgresql+asyncpg://zendesk_app:zendesk_secure_pass_2026@localhost:5432/zendesk_intelligence alembic upgrade head
```

---

## 5. Running the Services

### Start the FastAPI Backend
```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API is now running at `http://localhost:8000`. You can inspect the Swagger documentation at `http://localhost:8000/docs`.

### Start the Background Worker (Optional)
```bash
source .venv/bin/activate
cd backend
celery -A app.worker.celery_app worker --loglevel=info
```

---

## 6. Running Tests & Validation

```bash
# Run the complete test suite
./.venv/bin/pytest backend/ shared/ mcp-server/

# Run tests with coverage report
./.venv/bin/pytest --cov=shared --cov=backend --cov=mcp_server backend/ shared/ mcp-server/

# Validate and package the Zendesk app
python zendesk-app/package_app.py
```
