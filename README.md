# Zendesk Ticket Summarizer

A modular, multi-component monorepo designed to automatically generate AI summaries of Zendesk support tickets and conversation threads using Google Gemini AI, and seamlessly post them back as Zendesk internal notes.

---

## Architecture Overview

The system is structured as a Python 3.11+ monorepo with a single source of truth (`shared/`) consumed by multiple frontends and interfaces:

```
zendesk-ticket-summarizer/
├── backend/          # FastAPI REST service — core ticket retrieval & AI summarization
├── zendesk-app/      # Zendesk Apps Framework (ZAF v2) sidebar app (HTML/JS shell)
├── mcp-server/       # Model Context Protocol (MCP) server exposing tools to AI agents
├── shared/           # Shared Python package (zendesk_summarizer_shared) for config & clients
├── docs/             # Technical specifications and API contract documentation
├── scripts/          # Automation, smoke test, and diagnostic scripts
├── .env.example      # Environment variables template
├── .gitignore        # Monorepo gitignore rules
└── README.md
```

### Component Interaction Diagram

```
 +---------------------------------------------------------+
 |                 Zendesk Support Interface               |
 |                                                         |
 |   +-------------------------------------------------+   |
 |   |   zendesk-app/ (ZAF Sidebar Widget HTML/JS)     |   |
 |   +-------------------------------------------------+   |
 +----------------------------+----------------------------+
                              |
                     HTTP     | (e.g. POST /api/summarize)
                              v
                +----------------------------+
                |    backend/ (FastAPI)      |
                +-------------+--------------+
                              |
               imports logic  |
                              v
                +----------------------------+
                |     shared/ (Python)       |
                |  zendesk_summarizer_shared |
                +-------+------------+-------+
                        |            |
                        |            | imports logic
                        |            v
                        |     +----------------------------+
                        |     |    mcp-server/ (MCP)       |
                        |     +----------------------------+
                        |                    |
                        |                    | STDIO / SSE
                        |                    v
                        |             AI Agent Platforms
                        |             (Claude Desktop, AGY)
                        |
       +----------------+----------------+
       |                                 |
       v                                 v
+-----------------------+     +-----------------------+
|   Zendesk REST API    |     |   Google Gemini API   |
| (Tickets & Comments)  |     |   (generateContent)   |
+-----------------------+     +-----------------------+
```

### Why a Shared Package?
- **Single Source of Truth**: All Zendesk API contracts, authentication headers, error handling, rate limiting, and Gemini prompt templates live inside `shared/` (`zendesk_summarizer_shared`).
- **No Duplication**: Both the `backend` (FastAPI) and `mcp-server` import `zendesk_summarizer_shared` directly via Poetry path dependencies (`../shared`).
- **Strict Security**: Credentials (`ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN`, `GEMINI_API_KEY`) are managed strictly via environment variables or `.env` using Pydantic Settings and are never hardcoded.

---

## Getting Started

### Prerequisites
- Python 3.11+
- [Poetry](https://python-poetry.org/) 2.0+

### 1. Configure Environment Variables
Copy the template and provide your actual credentials:
```bash
cp .env.example .env
```

Edit `.env` with your Zendesk credentials and Gemini API Key:
```ini
ZENDESK_SUBDOMAIN=your_subdomain
ZENDESK_EMAIL=your_email@example.com
ZENDESK_API_TOKEN=your_zendesk_token
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
```

---

## Connectivity Smoke Test

The repository includes an end-to-end smoke test script that verifies live connectivity and authentication with both Zendesk and Google Gemini:

```bash
# Run directly from monorepo root:
python scripts/smoke_test.py
```

### What the Smoke Test Verifies:
1. **Zendesk REST API**:
   - Queries `GET https://{subdomain}.zendesk.com/api/v2/tickets.json?per_page=1`
   - Uses HTTP Basic Authentication with `{email}/token:{api_token}` per Zendesk API specifications.
   - Verifies ticket list access and displays ticket count and sample metadata.
2. **Google Gemini API**:
   - Sends a test payload to `generateContent` using `GEMINI_API_KEY`.
   - Confirms model inference and response parsing.

---

## Component Setup & Development

### 1. Shared Package (`shared/`)
```bash
cd shared
poetry install
poetry run pytest
```

### 2. Backend Service (`backend/`)
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger API Docs: `http://localhost:8000/docs`
- Health check: `GET /health`
- Metrics: `GET /metrics`
- Ticket Details: `GET /api/tickets/{ticket_id}`
- Summarize Ticket: `POST /api/tickets/{ticket_id}/summarize`
- Post Internal Note: `POST /api/tickets/{ticket_id}/notes`
- Summarize & Post: `POST /api/tickets/{ticket_id}/summarize-and-post`
- Direct Text Summarization: `POST /api/summarize-text`
- Webhook Solve Trigger: `POST /webhooks/zendesk/ticket-status-changed`

### 3. MCP Server (`mcp-server/`)
```bash
cd mcp-server
poetry install
poetry run python -m mcp_server.server
```
Exposes tools for AI Agent platforms (Claude Desktop, Cursor, Antigravity):
- `get_ticket(ticket_id)`
- `list_recent_tickets(status, limit)`
- `summarize_ticket(ticket_id, style)`
- `post_internal_note(ticket_id, note_body)`
- `summarize_text(text, subject, style)`
- `get_service_status()`

### 4. Zendesk Sidebar App (`zendesk-app/`)
The sidebar app is a ZAF v2 HTML/JS/CSS client built with Zendesk Garden styling.
```bash
cd zendesk-app
python3 package_app.py
# Package created: dist/zendesk-ticket-summarizer.zip
```
Upload the zip via Zendesk Admin Center > Apps and integrations > Zendesk Support apps > Upload private app.

---

## Production Hardening & Resilience

1. **Sliding Window Rate Limiting**: In-memory rate limiter protects public and webhook endpoints against request flooding (`RATE_LIMIT_PER_MINUTE=60`).
2. **SQLite WAL Audit Logger**: Thread-safe audit trail stored in SQLite using Write-Ahead Logging (`PRAGMA journal_mode=WAL;` and `busy_timeout=5000`) to eliminate database lock contention.
3. **Operational Metrics (`/metrics`)**: Built-in JSON metrics tracking summary generation counts (by style/provider), note postings, webhooks processed, uptime, and categorized error rates.
4. **Structured Error Handling**: Graceful exception mapping for Zendesk 401/404/429/502, Gemini/Groq rate limits, and webhook HMAC signature failures without exposing stack traces.
5. **Containerization**: Multi-stage `Dockerfile` and `docker-compose.yml` with persistent volume mount (`summarizer_data:/app/data`) and automated health checks.

---

## Production Deployment

For detailed deployment guides on Render.com, Railway, Fly.io, secrets injection, and Zendesk installation settings, refer to:
- 📖 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- 📖 [docs/zendesk-app-install.md](docs/zendesk-app-install.md)
- 📖 [docs/zendesk-trigger-setup.md](docs/zendesk-trigger-setup.md)
- 📖 [docs/mcp-server-setup.md](docs/mcp-server-setup.md)

---

## Running Automated Tests

Run the complete test suite across all monorepo components:

```bash
# 1. Shared Package Tests (55 tests)
cd shared && poetry run pytest

# 2. Backend API & Hardening Tests (22 tests)
cd backend && poetry run pytest

# 3. MCP Server Tests (8 tests)
cd mcp-server && poetry run pytest
```
**Total**: **85 automated tests passing (100% coverage)**.

---

## Known Limitations

1. **Zendesk API Rate Limits**: Zendesk enforces plan-dependent API limits (e.g. 200–700 RPM). The client implements automatic exponential backoff with `Retry-After` header parsing.
2. **Free Hosting Cold Starts**: On free tiers (e.g., Render free web services), inactivity causes the service to sleep (~50s cold start). Use Railway or paid instances for mission-critical support workflows.
3. **Human-in-the-Loop Safeguard**: Automated triggers store drafts as `pending_review` in the sidebar app rather than auto-posting to ticket threads, preventing unreviewed AI hallucinations from becoming permanent records.
4. **Massive Thread Truncation**: Extremely long ticket threads (>25 comments) are intelligently truncated, preserving the customer's initial problem description and the latest exchanges in full context.

