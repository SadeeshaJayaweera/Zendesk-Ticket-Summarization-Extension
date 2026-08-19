# Model Context Protocol (MCP) Server Setup & User Guide

This guide explains how to configure and run the **Zendesk Ticket Summarizer MCP Server** (`mcp-server/`) with AI agent platforms like **Claude Desktop**, **Google Antigravity**, **Cursor**, or the **MCP Inspector**.

---

## 1. Architecture Overview

The MCP server exposes the core Zendesk Client and AI Summarization Engine as standardized Model Context Protocol (MCP) tools via `stdio` communication:

```
┌─────────────────────────────────────────────────────────────┐
│ AI Client (Claude Desktop / Antigravity / Cursor / Inspector)│
│                                                             │
│  User: "Summarize ticket #1234 and prepare an internal note"│
└───────────────────────────┬─────────────────────────────────┘
                            │ stdio (JSON-RPC)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Zendesk Ticket Summarizer MCP Server (mcp_server/server.py) │
│                                                             │
│  • Tools: get_ticket, summarize_ticket, post_internal_note, │
│           list_recent_tickets, summarize_text               │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌───────────────────────────┐ ┌───────────────────────────────┐
│ Zendesk REST API Client   │ │ Gemini / Groq AI Engine       │
│ • Fetch tickets & thread  │ │ • TicketContextBuilder        │
│ • Post internal notes     │ │ • Structured JSON summary     │
│   (public: false)         │ │ • InternalNoteFormatter       │
└───────────────────────────┘ └───────────────────────────────┘
```

---

## 2. Available Tools Reference

| Tool Name | Arguments | Description |
| :--- | :--- | :--- |
| `get_service_status` | *None* | Checks connectivity and configuration state (Zendesk credentials, Gemini/Groq keys). |
| `list_recent_tickets` | `status: Optional[str]`, `limit: int = 10` | Lists recent tickets (optionally filtered by `open`, `pending`, `solved`, `new`) to discover ticket IDs. |
| `get_ticket` | `ticket_id: str` | Fetches ticket metadata and the full conversation comment thread in chronological order. |
| `summarize_ticket` | `ticket_id: str`, `style: str = "standard"` | Generates a structured AI summary covering core issue, troubleshooting actions, status, commitments, sentiment, and action items. **Does NOT post to Zendesk.** |
| `post_internal_note` | `ticket_id: str`, `note_text: str` | **⚠️ CAUTION:** Posts the reviewed text directly to the Zendesk ticket as a **private internal note** (`public: false`). Only execute after user review. |
| `summarize_text` | `text: str`, `subject: str = ""`, `style: str = "standard"` | Summarizes arbitrary support transcripts or conversation text without contacting Zendesk. |

---

## 3. Configuration & Registration

### 3.1 Claude Desktop Configuration

Edit your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the `zendesk-ticket-summarizer` server entry:

```json
{
  "mcpServers": {
    "zendesk-ticket-summarizer": {
      "command": "/Users/macboookpro/Library/Caches/pypoetry/virtualenvs/zendesk-summarizer-mcp-zQ3zJqmg-py3.11/bin/python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "cwd": "/Users/macboookpro/.gemini/antigravity-ide/scratch/zendesk-ticket-summarizer/mcp-server",
      "env": {
        "ZENDESK_SUBDOMAIN": "your-subdomain",
        "ZENDESK_EMAIL": "agent@yourcompany.com",
        "ZENDESK_API_TOKEN": "your-zendesk-api-token",
        "LLM_PROVIDER": "gemini",
        "GEMINI_API_KEY": "your-gemini-api-key",
        "GEMINI_MODEL": "gemini-1.5-flash",
        "GROQ_API_KEY": "",
        "GROQ_MODEL": "llama-3.3-70b-versatile"
      }
    }
  }
}
```

> [!TIP]
> You can also use `poetry run python -m mcp_server.server` if `poetry` is globally available in your environment path.

---

### 3.2 Antigravity / Cursor Configuration (`mcp_config.json`)

To register the MCP server in Antigravity or Cursor:

```json
{
  "mcpServers": {
    "zendesk-ticket-summarizer": {
      "command": "poetry",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "/Users/macboookpro/.gemini/antigravity-ide/scratch/zendesk-ticket-summarizer/mcp-server",
      "env": {
        "ZENDESK_SUBDOMAIN": "your-subdomain",
        "ZENDESK_EMAIL": "agent@yourcompany.com",
        "ZENDESK_API_TOKEN": "your-zendesk-api-token",
        "GEMINI_API_KEY": "your-gemini-api-key"
      }
    }
  }
}
```

---

## 4. Human-in-the-Loop Safety Model

To prevent accidental posting or unverified automated messages on live customer tickets, the MCP server enforces a strict two-step workflow mirroring the sidebar UI:

1. **Step 1 — Draft Generation**: The agent calls `summarize_ticket(ticket_id="1234")`. The AI returns the draft markdown summary in the conversation.
2. **Step 2 — Human Review & Approval**: The user/support agent reviews the draft summary, checks that action items and commitments are accurate, and requests any desired tweaks.
3. **Step 3 — Explicit Posting**: Only upon explicit user confirmation (e.g. *"Looks good, post it"*), the agent calls `post_internal_note(ticket_id="1234", note_text=...)`.

The tool description for `post_internal_note` explicitly highlights this expectation so that LLMs will not automatically post notes without user consent.

---

## 5. Testing with the MCP Inspector

You can test the MCP server interactively using the official MCP Inspector web interface:

```bash
cd mcp-server
npx @modelcontextprotocol/inspector poetry run python -m mcp_server.server
```

1. Open the inspector URL in your browser (typically `http://localhost:5173`).
2. Click **List Tools** to verify all 6 tools are registered.
3. Test `get_service_status` to verify credentials.
4. Test `list_recent_tickets` and `summarize_ticket` with a ticket ID.
