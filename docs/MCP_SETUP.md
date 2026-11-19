# Model Context Protocol (MCP) Server Setup Guide

## 1. Overview

The **Zendesk Support Intelligence MCP Server** allows desktop AI agents (such as Claude Desktop, Cursor, Google Antigravity, and Gemini CLI) to inspect Zendesk tickets, run diagnostic troubleshooting, draft replies, and post internal notes directly from the agent chat interface over standard I/O (stdio).

---

## 2. MCP Tools Catalog (13 Tools)

| Tool Name | Arguments | Description |
| :--- | :--- | :--- |
| **`get_service_status`** | *None* | Checks configuration and connectivity of Zendesk and LLM integrations. |
| **`get_ticket`** | `ticket_id` | Fetches ticket metadata and full conversation thread with speaker labels. |
| **`get_ticket_details`** | `ticket_id` | Returns raw JSON attributes and tags for a ticket. |
| **`get_ticket_conversation`** | `ticket_id` | Returns chronological comment thread. |
| **`list_recent_tickets`** | `status`, `limit` | Lists recent tickets matching optional status filter. |
| **`summarize_ticket`** | `ticket_id`, `style`, `custom_instructions` | Generates a structured AI summary based on conversation history. |
| **`generate_technical_summary`** | `ticket_id` | Produces an engineering troubleshooting summary. |
| **`generate_handover`** | `ticket_id` | Generates shift handover briefing notes with open items and obligations. |
| **`generate_escalation_brief`** | `ticket_id` | Generates a structured escalation brief for senior engineers. |
| **`suggest_troubleshooting`** | `ticket_id` | Generates step-by-step diagnostic procedures and escalation criteria. |
| **`draft_customer_reply`** | `ticket_id`, `tone` | Drafts a customer response grounded in conversation facts. |
| **`classify_ticket`** | `ticket_id` | Predicts category, priority, complexity, and target department. |
| **`analyze_sentiment`** | `ticket_id` | Assesses customer frustration level, unresolved concerns, and churn risk. |
| **`find_similar_tickets`** | `ticket_id` | Finds historical resolved tickets sharing symptoms and duplicates. |
| **`search_knowledge_base`** | `query` | Searches Zendesk Help Center documentation articles. |
| **`get_summary_history`** | `ticket_id` | Retrieves past AI summaries generated on the ticket. |
| **`post_internal_note`** | `ticket_id`, `note_text` | Posts private internal note to Zendesk ticket (Human confirmation required). |
| **`summarize_text`** | `text`, `subject`, `style` | Summarizes arbitrary email threads or chat transcripts directly. |

---

## 3. Configuration with Claude Desktop

Add the following to your `claude_desktop_config.json`:
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zendesk-summarizer": {
      "command": "/Users/macboookpro/Zendesk-Ticket-Summarization-Extension/.venv/bin/python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "ZENDESK_SUBDOMAIN": "yourcompany",
        "ZENDESK_EMAIL": "agent@yourcompany.com",
        "ZENDESK_API_TOKEN": "your_api_token",
        "LLM_PROVIDER": "gemini",
        "GEMINI_API_KEY": "your_gemini_key"
      }
    }
  }
}
```

---

## 4. Configuration with Cursor / Antigravity IDE

In your project root, configure `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "zendesk-support-intelligence": {
      "command": "./.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "ZENDESK_SUBDOMAIN": "yourcompany",
        "ZENDESK_EMAIL": "agent@yourcompany.com",
        "ZENDESK_API_TOKEN": "your_api_token",
        "GEMINI_API_KEY": "your_gemini_key"
      }
    }
  }
}
```
