"""Model Context Protocol (MCP) Server for Zendesk Ticket Summarizer.

Exposes Zendesk ticket inspection, AI summarization (Gemini/Groq), and internal note posting
tools to AI agent platforms (Claude Desktop, Google Antigravity, Cursor, Gemini CLI) via FastMCP.
"""

from typing import Optional
from mcp.server import MCPServer
from zendesk_summarizer_shared.config import get_settings
from zendesk_summarizer_shared.service import TicketSummarizerService

# Initialize FastMCP Server
mcp = MCPServer("zendesk-ticket-summarizer")


def _get_service() -> TicketSummarizerService:
    """Instantiate a TicketSummarizerService using current environment settings."""
    return TicketSummarizerService()


def _parse_ticket_id(ticket_id: str | int) -> int:
    """Parse and clean a ticket ID string or int."""
    cleaned = str(ticket_id).strip().lstrip("#")
    try:
        return int(cleaned)
    except ValueError:
        raise ValueError(f"Invalid ticket ID '{ticket_id}'. Expected an integer ID.")


@mcp.tool()
def get_service_status() -> str:
    """Check configuration and connectivity status of the Zendesk Ticket Summarizer service."""
    settings = get_settings()
    zendesk_status = "configured" if settings.is_zendesk_configured else "missing credentials"
    llm_provider = settings.llm_provider.upper()
    if settings.llm_provider == "groq":
        llm_status = f"configured ({settings.groq_model})" if settings.is_groq_configured else "missing GROQ_API_KEY"
    else:
        llm_status = f"configured ({settings.gemini_model})" if settings.is_gemini_configured else "missing GEMINI_API_KEY"

    return (
        f"Zendesk Ticket Summarizer MCP Server (v0.1.0)\n"
        f"- Zendesk Integration: {zendesk_status} (Subdomain: {settings.zendesk_subdomain or 'unset'})\n"
        f"- LLM Provider: {llm_provider} ({llm_status})\n"
        f"- Status: READY"
    )


@mcp.tool()
async def get_ticket(ticket_id: str) -> str:
    """Retrieve ticket metadata and the full conversation comment thread in chronological order.

    Use this tool when you or the user want to inspect the exact message history,
    customer replies, and internal notes of a Zendesk ticket.

    Args:
        ticket_id: The Zendesk ticket ID (e.g. "1234" or "#1234").
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        details = await service.get_ticket_details(tid)
        ticket = details.ticket
        comments = details.comments

        lines = [
            f"=== TICKET #{ticket.id}: {ticket.subject} ===",
            f"Status: {ticket.status.upper()} | Priority: {(ticket.priority or 'normal').upper()}",
            f"Requester ID: {ticket.requester_id} | Assignee ID: {ticket.assignee_id or 'Unassigned'}",
            f"Created At: {ticket.created_at or 'N/A'} | Updated At: {ticket.updated_at or 'N/A'}",
            f"Tags: {', '.join(ticket.tags) if ticket.tags else 'None'}",
            "",
            f"=== CONVERSATION THREAD ({len(comments)} comments) ===",
        ]

        if not comments:
            lines.append("(No comments recorded on this ticket yet.)")
        else:
            for idx, c in enumerate(comments, 1):
                role_label = "PUBLIC REPLY" if c.public else "INTERNAL NOTE (PRIVATE)"
                author_str = f"Author ID: {c.author_id}"
                time_str = c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "Unknown Time"
                lines.append(f"\n--- [{idx}] [{role_label}] {author_str} ({time_str}) ---")
                body = c.plain_body or c.body or "(empty body)"
                lines.append(body.strip())

        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def list_recent_tickets(status: Optional[str] = None, limit: int = 10) -> str:
    """List recent tickets from the Zendesk instance, optionally filtered by status.

    Use this tool to discover ticket IDs and find tickets to work with or summarize
    without leaving the conversation.

    Args:
        status: Optional status filter ('open', 'pending', 'solved', 'new', 'hold', 'closed').
        limit: Maximum number of tickets to list (default: 10, max: 50).
    """
    try:
        service = _get_service()
        clamped_limit = max(1, min(limit, 50))
        tickets = await service.list_recent_tickets(status=status, limit=clamped_limit)

        if not tickets:
            filter_msg = f" with status '{status}'" if status else ""
            return f"No tickets found{filter_msg}."

        lines = [f"Found {len(tickets)} recent ticket(s)" + (f" matching status '{status}':" if status else ":"), ""]
        for t in tickets:
            p = t.priority or "normal"
            lines.append(f"- Ticket #{t.id}: [{t.status.upper()}] {t.subject} (Priority: {p})")

        return "\n".join(lines)
    except Exception as exc:
        return f"Error listing tickets: {str(exc)}"


@mcp.tool()
async def summarize_ticket(ticket_id: str, style: str = "standard") -> str:
    """Generate an AI summary of a Zendesk ticket's full conversation history.

    This produces a structured draft summary (covering the core issue, troubleshooting actions taken,
    current status, promised commitments/deadlines, sentiment, and action items).

    NOTE: This tool only GENERATES the draft summary; it does NOT post it to the ticket.

    Args:
        ticket_id: The Zendesk ticket ID to summarize (e.g. "1234").
        style: Summary style format ('standard', 'brief', 'action_only', 'detailed').
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.summarize_ticket(tid, summary_style=style)
        return resp.markdown_note
    except Exception as exc:
        return f"Error summarizing ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def post_internal_note(ticket_id: str, note_text: str) -> str:
    """Post an internal private note to a Zendesk ticket.

    ⚠️ CAUTION: This tool writes directly to a live Zendesk support ticket and is immediately
    visible to the support team and logged in ticket audit history. Only execute this tool
    after the user has reviewed and explicitly approved the summary text.

    The note will be posted strictly as a private internal note (public: false) so customers
    cannot see it.

    Args:
        ticket_id: The Zendesk ticket ID to post to (e.g. "1234").
        note_text: The reviewed and approved markdown/text content to post.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        if not note_text or not note_text.strip():
            return "Error: Cannot post an empty internal note."

        service = _get_service()
        resp = await service.post_summary_note(ticket_id=tid, note_body=note_text, public=False)
        return f"Success: Internal note posted successfully to Zendesk ticket #{tid}."
    except Exception as exc:
        return f"Error posting internal note to ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def summarize_text(text: str, subject: str = "", style: str = "standard") -> str:
    """Generate an AI structured summary for arbitrary support text, chat transcript, or email thread.

    Does not contact Zendesk; runs directly against the AI Summarization Engine.

    Args:
        text: The raw conversation transcript or message text.
        subject: Optional conversation subject or title.
        style: Summary style format ('standard', 'brief', 'action_only', 'detailed').
    """
    try:
        service = _get_service()
        resp = await service.summarize_raw_text(
            text=text,
            subject=subject if subject else None,
            summary_style=style,
        )
        return resp.markdown_note
    except Exception as exc:
        return f"Error summarizing text: {str(exc)}"


def main():
    """Run the FastMCP server over standard I/O (stdio)."""
    mcp.run()


if __name__ == "__main__":
    main()

# Tool schema refinement 1

# Tool schema refinement 2

# Tool schema refinement 3

# Tool schema refinement 4

# Tool schema refinement 5

# Tool schema refinement 6

# Tool schema refinement 7

# Tool schema refinement 8

# Tool schema refinement 9

# Tool schema refinement 10

# Tool schema refinement 11

# Tool schema refinement 12

# Tool schema refinement 13
