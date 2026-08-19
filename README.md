# 🤖 Zendesk Ticket Summarizer

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Zendesk ZAF v2](https://img.shields.io/badge/Zendesk-ZAF_v2-03363D?style=for-the-badge&logo=zendesk&logoColor=white)](https://developer.zendesk.com/)
[![Google Gemini AI](https://img.shields.io/badge/Google_Gemini-1.5_Flash-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![Groq LLaMA](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Stdio_Protocol-0A84FF?style=for-the-badge)](https://modelcontextprotocol.io/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-85%2F85_Passing_(100%25)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

An enterprise-grade, multi-component monorepo that automatically analyzes complex Zendesk customer conversation threads using **Google Gemini AI** and **Groq LLaMA 3.3**, generating structured summaries and enabling support agents to review, edit, and post internal notes in a single click.

---

## 📌 Relevant Topics & Tags

`zendesk` • `zendesk-app` • `zendesk-ticket-summarizer` • `ai-summarization` • `google-gemini` • `gemini-1.5-flash` • `groq` • `llama-3.3-70b` • `fastapi` • `model-context-protocol` • `mcp-server` • `customer-support` • `llm-agent` • `claude-desktop` • `cursor` • `docker` • `sqlite-wal` • `python` • `rate-limiting` • `zaf-v2` • `human-in-the-loop`

---

## 🎯 The Problem

Customer support teams at scale face severe operational bottlenecks:
1. **Information Overload**: Multi-day ticket threads often contain 20+ back-and-forth messages between customers, tier-1 agents, and specialized engineers.
2. **Context Loss on Handoffs**: When tickets are reassigned, new agents must spend 5–15 minutes reading raw transcripts to understand the root cause and prior troubleshooting steps.
3. **Elevated Mean Time to Resolution (MTTR)**: Repetitive reading and drafting handover notes slows down resolution times and increases customer wait times.
4. **Shift Handover Gaps**: Inconsistent or missing internal notes leave oncoming shifts guessing what actions were promised to the customer.

---

## 💡 The Solution

**Zendesk Ticket Summarizer** provides a unified AI operational layer for Zendesk:

* **⚡ Instant Context Extraction**: Automatically parses the entire conversation history (public replies & private notes) and synthesizes the customer's core issue, steps taken, current status, and sentiment in seconds.
* **🛡️ Human-in-the-Loop Safety**: AI summaries are presented as editable drafts in the sidebar UI or staging queue; they are **never auto-posted without agent review**, preventing AI hallucinations from becoming permanent records.
* **🧩 Native Zendesk Agent Workspace App**: A lightweight ZAF v2 sidebar widget styled with **Zendesk Garden** design tokens that fits seamlessly into the agent workspace.
* **🤖 Model Context Protocol (MCP) Server**: Exposes ticket inspection, summarization, and note-posting tools to desktop AI agents (e.g. Claude Desktop, Cursor, Antigravity) via stdio.
* **🔄 Automated Webhook on Ticket Solve**: Automatically drafts an AI summary when a ticket status changes to `Solved`, pre-filling the sidebar widget when the agent opens the ticket.
* **🔒 Production Hardening**: Sliding-window rate limiting, HMAC-SHA256 signature verification, and SQLite Write-Ahead Logging (WAL) for lock-free audit logging.

---

## 🏛️ System Architecture

```
                                    +-------------------------------------------------------------+
                                    |                 Zendesk Support Platform                    |
                                    |                                                             |
                                    |  +-------------------------------------------------------+  |
                                    |  |   zendesk-app/ (ZAF v2 Sidebar Widget HTML/JS/CSS)    |  |
                                    |  +---------------------------+---------------------------+  |
                                    +------------------------------|------------------------------+
                                                                   | HTTP / JSON
                                                                   v
                                    +-------------------------------------------------------------+
                                    |           FastAPI Production Backend (backend/)             |
                                    |                                                             |
                                    |  +-------------------------------------------------------+  |
                                    |  |  • In-Memory Sliding Window Rate Limiter              |  |
                                    |  |  • HMAC-SHA256 Webhook Signature Verification         |  |
                                    |  |  • Resilient Exception Handlers (401/404/429/502)     |  |
                                    |  |  • Prometheus-style /metrics Observability Endpoint   |  |
                                    |  |  • SQLite Audit Logger (WAL Mode, zero contention)    |  |
                                    |  +---------------------------+---------------------------+  |
                                    +------------------------------|------------------------------+
                                                                   |
                                                      Imports Logic| (Single Source of Truth)
                                                                   v
+-----------------------------+     +-------------------------------------------------------------+
|     AI Desktop Clients      |     |             Shared Core Package (shared/)                   |
|  (Claude Desktop, Cursor)   |     |               zendesk_summarizer_shared                     |
+--------------+--------------+     |                                                             |
               |                    |  • ZendeskClient (Async httpx, Pagination, 429 Backoff)     |
               | Stdio / MCP        |  • GeminiClient & GroqSummarizer (JSON Regex Extraction)    |
               v                    |  • TicketContextBuilder & InternalNoteFormatter             |
+-----------------------------+     |  • DraftStore (In-memory & persistent pending reviews)      |
|  mcp-server/ (Python MCP)   |---->+------------------------------+------------------------------+
+-----------------------------+                                    |
                                                                   |
                                    +------------------------------+------------------------------+
                                    |                                                             |
                                    v                                                             v
                     +-----------------------------+                               +-----------------------------+
                     |      Zendesk REST API       |                               |      Google Gemini API      |
                     | (Tickets, Comments, Users)  |                               |    (1.5 Flash / Groq LLaMA) |
                     +-----------------------------+                               +-----------------------------+
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose & Details |
| :--- | :--- | :--- |
| **Language & Runtime** | Python 3.11+ | Type-annotated, modern async/await runtime across monorepo |
| **Package Management** | Poetry 2.0+ | Monorepo dependency management with local path resolution |
| **Backend REST API** | FastAPI, Uvicorn | High-performance asynchronous REST service |
| **Data Validation** | Pydantic v2 Settings | Strict schema validation, type safety, and `.env` parsing |
| **Primary AI Engine** | Google Gemini 1.5 Flash | Fast, high-accuracy structured summary generation via REST API |
| **Fallback AI Engine** | Groq Cloud (LLaMA 3.3 70B) | High-speed open-weights fallback provider |
| **Zendesk UI Client** | ZAF v2, HTML5, Vanilla JS/CSS | Native iframe sidebar widget built with Zendesk Garden tokens |
| **AI Agent Interface** | Model Context Protocol (MCP) | Official Python MCP SDK exposing tools over `stdio` |
| **HTTP Client** | HTTPX (Async) | Async client with exponential backoff & connection pooling |
| **Audit & Storage** | SQLite 3 (WAL Mode) | Thread-safe, lock-free operational audit log and pending draft queue |
| **Security & Auth** | HMAC-SHA256, HTTP Basic Auth | Webhook signature verification and constant-time token comparison |
| **Containerization** | Docker, Docker Compose | Multi-stage slim container with persistent volumes & health check |
| **Testing Suite** | Pytest, Respx, AsyncIO | 85 comprehensive unit, integration, and mock tests (100% pass rate) |

---

## 📁 Repository Structure

```
zendesk-ticket-summarizer/
├── shared/                         # Core shared Python library (zendesk_summarizer_shared)
│   ├── zendesk_summarizer_shared/
│   │   ├── config.py               # Pydantic Settings & environment loader
│   │   ├── models.py               # Zendesk & AI Domain Pydantic models
│   │   ├── zendesk_client.py       # Async Zendesk REST API client with 429 backoff
│   │   ├── gemini_client.py        # Async Google Gemini API client
│   │   ├── summarizer.py           # Gemini/Groq summarizers, context builder & formatter
│   │   ├── service.py              # Orchestration service combining Zendesk + AI
│   │   ├── security.py             # HMAC-SHA256 webhook signature verification
│   │   ├── draft_store.py          # State store for pending_review automated drafts
│   │   ├── rate_limiter.py         # Sliding-window in-memory rate limiter
│   │   ├── audit_logger.py         # SQLite WAL-mode persistent audit logger
│   │   └── metrics.py              # Operational metrics tracker
│   ├── tests/                      # Unit tests for shared library (55 tests)
│   └── pyproject.toml
│
├── backend/                        # FastAPI REST API Microservice
│   ├── app/
│   │   └── main.py                 # FastAPI application routes, rate limiting & error handlers
│   ├── tests/                      # Integration and API test suite (22 tests)
│   └── pyproject.toml
│
├── zendesk-app/                    # Zendesk Apps Framework (ZAF v2) Sidebar App
│   ├── manifest.json               # ZAF App manifest with ticket_sidebar location
│   ├── package_app.py              # Schema validator and zip packager script
│   ├── dist/                       # Output zip package for Zendesk upload
│   ├── assets/
│   │   ├── index.html              # Garden-themed responsive sidebar UI
│   │   ├── style.css               # Styling, animations, skeleton loader & themes
│   │   └── main.js                 # ZAF SDK integration, dev preview & API caller
│   └── translations/en.json        # Localization strings
│
├── mcp-server/                     # Model Context Protocol (MCP) Server
│   ├── mcp_server/
│   │   └── server.py               # MCP Server exposing stdio tools for Claude/Cursor
│   ├── tests/                      # MCP Server test suite (8 tests)
│   └── pyproject.toml
│
├── docs/                           # Technical Specifications & Documentation
│   ├── zendesk-api-notes.md        # Zendesk REST endpoint contracts & auth specs
│   ├── zendesk-app-install.md      # Sidebar app upload & configuration guide
│   ├── zendesk-trigger-setup.md    # Zendesk Trigger & Webhook setup guide
│   ├── mcp-server-setup.md         # Claude Desktop & IDE integration guide
│   └── DEPLOYMENT.md               # Cloud deployment guide (Render, Railway, Fly.io)
│
├── scripts/                        # Diagnostic & verification scripts
│   ├── smoke_test.py               # Live Zendesk & Gemini connectivity test
│   ├── test_summarize_pipeline.py  # Simulated pipeline across all summary styles
│   ├── test_webhook_flow.py        # Webhook signature & pending draft simulation
│   └── test_mcp_client.py          # Interactive MCP client emulator
│
├── Dockerfile                      # Production multi-stage Docker container
├── docker-compose.yml              # Local container orchestration with SQLite volume
├── .dockerignore                   # Docker context exclusions
├── .gitignore                      # Git tracking exclusions
├── .env.example                    # Environment template
└── README.md
```

---

## ⚡ Quickstart & Setup

### 1. Prerequisites
* Python 3.11+
* [Poetry](https://python-poetry.org/) 2.0+
* A Zendesk account with Admin/Agent API access
* A Google Gemini API Key ([Get one here](https://aistudio.google.com/)) or Groq Cloud API Key

### 2. Configure Environment Variables
Copy `.env.example` to `.env` in the repository root:
```bash
cp .env.example .env
```

Fill in your actual credentials:
```ini
ZENDESK_SUBDOMAIN=your_company_subdomain
ZENDESK_EMAIL=agent@yourcompany.com
ZENDESK_API_TOKEN=your_zendesk_api_token
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash

# Optional Groq Fallback
GROQ_API_KEY=your_groq_key
LLM_PROVIDER=gemini

# Webhook Automation Secret (Optional)
ZENDESK_WEBHOOK_SECRET=your_zendesk_webhook_signing_secret
```

### 3. Run Connectivity Smoke Test
Validate live connectivity with both Zendesk and Google Gemini:
```bash
python scripts/smoke_test.py
```

---

## 🚀 Running the Components

### 1. Run the FastAPI Backend
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```
* Interactive API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
* Health Check: `GET http://localhost:8000/health`
* Live Metrics: `GET http://localhost:8000/metrics`

### 2. Run with Docker Compose
```bash
docker-compose up --build
```
Spins up the containerized backend with SQLite persistent volume mount at `summarizer_data:/app/data`.

### 3. Package & Install Zendesk Sidebar App
```bash
cd zendesk-app
python3 package_app.py
```
1. Open **Zendesk Admin Center** > **Apps and integrations** > **Zendesk Support apps**.
2. Click **Upload private app** and select `dist/zendesk-ticket-summarizer.zip`.
3. Set the `backendUrl` setting to your deployed backend URL (or `http://localhost:8000` for testing).

### 4. Connect to Claude Desktop via MCP Server
Add the server definition to your `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "zendesk-summarizer": {
      "command": "poetry",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "/path/to/zendesk-ticket-summarizer/mcp-server",
      "env": {
        "ZENDESK_SUBDOMAIN": "your_subdomain",
        "ZENDESK_EMAIL": "agent@example.com",
        "ZENDESK_API_TOKEN": "your_token",
        "GEMINI_API_KEY": "your_gemini_key"
      }
    }
  }
}
```

---

## 📊 REST API Endpoints & Observability

| Method | Endpoint | Description | Rate Limited |
| :--- | :--- | :--- | :---: |
| `GET` | `/` | Root service status and version | ❌ |
| `GET` | `/health` | Service health and configuration checks | ❌ |
| `GET` | `/metrics` | Operational counters, error breakdown & uptime | ❌ |
| `GET` | `/api/tickets/{id}` | Get ticket metadata and chronological comments | ❌ |
| `GET` | `/api/tickets/{id}/history` | Get historical AI summaries posted to ticket | ❌ |
| `GET` | `/api/tickets/{id}/pending-draft` | Check for automated pre-draft on ticket solve | ❌ |
| `POST` | `/api/tickets/{id}/summarize` | Generate AI summary for ticket (supports 4 styles) | ✅ |
| `POST` | `/api/tickets/{id}/notes` | Post private internal note to ticket | ✅ |
| `POST` | `/api/tickets/{id}/summarize-and-post` | All-in-one generate and post workflow | ✅ |
| `POST` | `/api/summarize-text` | Direct text / chat transcript summarization | ✅ |
| `POST` | `/webhooks/zendesk/ticket-status-changed` | HMAC-signed Zendesk trigger webhook endpoint | ✅ |

---

## 🧪 Comprehensive Test Suite

The monorepo includes **85 automated tests** across all components:

```bash
# 1. Run Shared Package Tests (55 tests)
cd shared && poetry run pytest -v

# 2. Run Backend API Tests (22 tests)
cd backend && poetry run pytest -v

# 3. Run MCP Server Tests (8 tests)
cd mcp-server && poetry run pytest -v
```

**Result**: `85 passed in ~3.8s (100% passing)`.

---

## 📚 Technical Documentation

* 📖 [docs/zendesk-api-notes.md](docs/zendesk-api-notes.md) — Zendesk REST contracts, authentication, sideloading, pagination.
* 📖 [docs/zendesk-app-install.md](docs/zendesk-app-install.md) — Packaging and installing the ZAF sidebar app.
* 📖 [docs/zendesk-trigger-setup.md](docs/zendesk-trigger-setup.md) — Zendesk Trigger & HMAC Webhook configuration.
* 📖 [docs/mcp-server-setup.md](docs/mcp-server-setup.md) — Claude Desktop, Cursor, and Antigravity MCP integration.
* 📖 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Production cloud deployment on Render, Railway, Fly.io.

---

## ⚠️ Known Limitations

1. **Zendesk API Plan Quotas**: Zendesk imposes plan-based rate limits (e.g. 200–700 RPM). The client handles this via automatic exponential backoff with `Retry-After` header parsing.
2. **Free Hosting Cold Starts**: On free tiers (e.g., Render free web service), inactivity spins down the instance (~50s cold start). Use Railway or paid plans for zero-latency production workloads.
3. **Massive Thread Context**: Extreme conversation threads (>25 comments) are intelligently truncated, prioritizing the initial customer problem statement and the latest replies.
4. **Human Review Principle**: Automated solve webhooks store drafts as `pending_review` in the sidebar app rather than auto-posting to ticket comments to ensure human oversight.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
