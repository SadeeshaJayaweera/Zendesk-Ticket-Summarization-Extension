# Production Deployment Guide: Zendesk Ticket Summarizer

This guide outlines how to deploy the **FastAPI Backend**, configure **Zendesk Sidebar App** in production, manage secrets securely, and set up the **Model Context Protocol (MCP)** server.

---

## 1. Architecture & Hosting Strategy

The monorepo components are deployed as follows:

| Component | Target Environment | Hosting Model |
| :--- | :--- | :--- |
| **Backend Service** (`backend/`) | Cloud Container Host | Dockerized FastAPI Web Service (e.g. Render, Railway, Fly.io) |
| **Zendesk Sidebar App** (`zendesk-app/`) | Zendesk Agent Workspace | Hosted inside Zendesk via Private App Package (`.zip`) |
| **MCP Server** (`mcp-server/`) | Agent Workstation / Local Machine | Runs over `stdio` alongside Claude Desktop or Cursor |

---

## 2. Free & Affordable Cloud Hosting Options for Backend

Here is a comparison of free / cost-effective hosting platforms for the FastAPI backend:

### Option A: Render.com (Recommended for Free Tier)
- **Plan**: Free Web Service tier (750 hours/month).
- **Pros**: Direct Git repo / Docker integration, automatic TLS certificates, built-in Environment Variables & Secrets management.
- **Limitations**:
  - Web service spins down after 15 minutes of inactivity. First request on cold start takes ~50 seconds.
  - Ephemeral disk on free tier (persistent disks require Paid Starter plan at $7/mo).

### Option B: Railway.app (Recommended for Low-Latency & SQLite Persistence)
- **Plan**: Hobby / Trial ($5 free credit / $5/mo base).
- **Pros**: Fast container builds, persistent volumes for SQLite audit log, zero cold starts, instant deployment.
- **Limitations**:
  - Requires card verification; $5 credit covers moderate usage before billable tier.

### Option C: Fly.io
- **Plan**: Free allowance (up to 3 shared-cpu-1x 256MB VMs + 3GB persistent storage).
- **Pros**: Global edge deployment, fast responses, persistent volumes.
- **Limitations**:
  - Requires CLI (`flyctl`) for deployment; 256MB memory cap requires optimized Python runtime.

---

## 3. Environment Variables & Production Secrets Management

> [!CAUTION]
> **Never commit `.env` files or API keys into source control.**
> In production, inject all secrets via your hosting provider's **Secrets Manager** or **Environment Variables Dashboard** (e.g., Render Dashboard > Environment, Railway Variables, or Fly.io `fly secrets set`).

### Required Production Environment Variables:

| Variable | Type | Example / Description |
| :--- | :--- | :--- |
| `ZENDESK_SUBDOMAIN` | String | `acme` (for `https://acme.zendesk.com`) |
| `ZENDESK_EMAIL` | String | `support-admin@acme.com` (Agent email) |
| `ZENDESK_API_TOKEN` | Secret | Zendesk API Token generated from Admin Center |
| `ZENDESK_WEBHOOK_SECRET` | Secret | Signing secret from Zendesk Webhooks |
| `LLM_PROVIDER` | String | `gemini` (default) or `groq` |
| `GEMINI_API_KEY` | Secret | Google AI Studio API Key |
| `GEMINI_MODEL` | String | `gemini-1.5-flash` |
| `GROQ_API_KEY` | Secret | Groq Cloud API Key (if using Groq fallback) |
| `RATE_LIMIT_PER_MINUTE` | Integer | `60` (sliding window limit per client) |
| `SQLITE_DB_PATH` | Path | `/app/data/audit.db` |
| `BACKEND_PORT` | Integer | `8000` (or `$PORT` assigned by host) |
| `LOG_LEVEL` | String | `INFO` |

---

## 4. Deploying the Backend Container

### Deploy with Docker on Render.com:
1. Fork or push the repository to GitHub.
2. In Render Dashboard, click **New +** > **Web Service**.
3. Select your repository and choose **Docker** runtime (or specify `Dockerfile`).
4. Under **Environment Variables**, add the production secrets listed above.
5. Click **Deploy Web Service**.
6. Copy your public service URL (e.g. `https://zendesk-summarizer.onrender.com`).

---

## 5. Packaging & Uploading the Zendesk Sidebar App

### Step 1: Package the ZAF App
From the repository root, run the packaging utility:
```bash
cd zendesk-app
python3 package_app.py
```
This generates the validated package `dist/zendesk-ticket-summarizer.zip`.

### Step 2: Upload to Zendesk
1. Log into your Zendesk instance as an admin (`https://<subdomain>.zendesk.com/admin`).
2. Go to **Apps and integrations** > **Apps** > **Zendesk Support apps**.
3. Click **Upload private app** in the top right.
4. Set **App Name**: `AI Ticket Summarizer`.
5. Upload `dist/zendesk-ticket-summarizer.zip`.

### Step 3: Configure the Production Backend URL
In the installation modal:
1. Locate the **Backend API URL (`backendUrl`)** installation parameter.
2. Enter your production backend URL (e.g., `https://zendesk-summarizer.onrender.com`).
3. Click **Install**.

> [!NOTE]
> The sidebar app reads `backendUrl` dynamically via `client.metadata()`, allowing you to point to different environments (staging, production) without re-zipping or changing code!

---

## 6. Model Context Protocol (MCP) Server Note

The **MCP server** (`mcp-server/`) is designed to run **locally on each support engineer's or AI agent's workstation** (e.g., inside Claude Desktop, Cursor, or Antigravity), rather than as a hosted web service.

- **How it connects**: Claude Desktop launches `python -m mcp_server.server` over standard input/output (`stdio`).
- **Configuration**: The user configures their local `claude_desktop_config.json` with the path to their Python virtualenv and their Zendesk/Gemini credentials.
- See [docs/mcp-server-setup.md](mcp-server-setup.md) for full Claude Desktop and IDE setup instructions.

---

## 7. Operational Health & Metrics Monitoring

- **Health Check**: `GET https://<your-backend-domain>/health`
- **Metrics Snapshot**: `GET https://<your-backend-domain>/metrics`
  Returns JSON:
  ```json
  {
    "service": "zendesk-ticket-summarizer",
    "uptime_seconds": 3600,
    "summaries_generated": { "total": 142, "by_style": { "standard": 120, "brief": 22 } },
    "notes_posted": { "total": 138 },
    "webhooks": { "total_received": 145, "by_status": { "pending_review": 145 } },
    "errors": { "total": 0, "by_category": { "zendesk": 0, "llm": 0, "rate_limit": 0 } }
  }
  ```
