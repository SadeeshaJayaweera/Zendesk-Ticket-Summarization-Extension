"""Model Context Protocol (MCP) Server for Zendesk Ticket Summarizer & Intelligence Platform.

Exposes Zendesk ticket inspection, multi-provider AI summarization, diagnostic troubleshooting,
reply drafting, ticket classification, sentiment radar, escalation/handover briefing, and knowledge base
tools to AI agent platforms (Claude Desktop, Google Antigravity, Cursor, Gemini CLI) via FastMCP.
"""

from typing import Optional
import json
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
    elif settings.llm_provider == "openai":
        llm_status = f"configured ({settings.openai_model})" if settings.is_openai_configured else "missing OPENAI_API_KEY"
    elif settings.llm_provider == "anthropic":
        llm_status = f"configured ({settings.anthropic_model})" if settings.is_anthropic_configured else "missing ANTHROPIC_API_KEY"
    else:
        llm_status = f"configured ({settings.gemini_model})" if settings.is_gemini_configured else "missing GEMINI_API_KEY"

    return (
        f"Zendesk Ticket Summarizer MCP Server (v0.2.0)\n"
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
async def get_ticket_details(ticket_id: str) -> str:
    """Retrieve detailed metadata and raw attributes for a ticket.

    Args:
        ticket_id: The Zendesk ticket ID (e.g. "1234").
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        details = await service.get_ticket_details(tid)
        t = details.ticket
        return json.dumps({
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "requester_id": t.requester_id,
            "assignee_id": t.assignee_id,
            "organization_id": t.organization_id,
            "tags": t.tags,
            "created_at": str(t.created_at),
            "updated_at": str(t.updated_at),
            "total_comments": details.total_comments,
        }, indent=2)
    except Exception as exc:
        return f"Error retrieving ticket details for '{ticket_id}': {str(exc)}"


@mcp.tool()
async def get_ticket_conversation(ticket_id: str) -> str:
    """Retrieve the formatted chronological conversation transcript of a ticket.

    Args:
        ticket_id: The Zendesk ticket ID.
    """
    return await get_ticket(ticket_id)


@mcp.tool()
async def list_recent_tickets(status: Optional[str] = None, limit: int = 10) -> str:
    """List recent tickets from the Zendesk instance, optionally filtered by status.

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
async def summarize_ticket(ticket_id: str, style: str = "standard", custom_instructions: Optional[str] = None) -> str:
    """Generate an AI summary of a Zendesk ticket's full conversation history.

    Produces a structured draft summary covering the core issue, troubleshooting actions taken,
    current status, promised commitments/deadlines, sentiment, and action items.

    Args:
        ticket_id: The Zendesk ticket ID to summarize (e.g. "1234").
        style: Summary style format ('standard', 'technical', 'complaint', 'handover', 'escalation',
               'bug', 'billing', 'integration', 'success', 'management', 'brief', 'action_only', 'detailed').
        custom_instructions: Optional specific focus or organizational guidelines.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        kwargs = {"summary_style": style}
        if custom_instructions is not None:
            kwargs["custom_instructions"] = custom_instructions
        resp = await service.summarize_ticket(tid, **kwargs)
        return resp.markdown_note
    except Exception as exc:
        return f"Error summarizing ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def generate_technical_summary(ticket_id: str) -> str:
    """Generate a technical troubleshooting summary for engineering and tier-2/3 agents.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    return await summarize_ticket(ticket_id, style="technical")


@mcp.tool()
async def generate_handover(ticket_id: str) -> str:
    """Generate a shift handover briefing note explaining unresolved issues and next agent obligations.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.generate_shift_handover(tid)
        return getattr(resp, "markdown_note", getattr(resp, "markdown_handover", str(resp)))
    except Exception as exc:
        return f"Error generating shift handover for ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def generate_escalation_brief(ticket_id: str) -> str:
    """Generate an engineering escalation brief containing customer impact, evidence, and repro details.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.generate_escalation_brief(tid)
        return resp.markdown_brief
    except Exception as exc:
        return f"Error generating escalation brief for ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def suggest_troubleshooting(ticket_id: str) -> str:
    """Generate structured diagnostic and troubleshooting procedures based on ticket evidence.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.suggest_troubleshooting(tid)
        lines = [f"=== DIAGNOSTIC PROCEDURES FOR TICKET #{tid} ===", ""]
        for idx, s in enumerate(resp.suggestions, 1):
            lines.append(f"Step {idx}: {s.problem_identified}")
            lines.append(f"- Supporting Evidence: {s.supporting_evidence or 'N/A'}")
            lines.append(f"- Recommended Action: {s.recommended_investigation}")
            lines.append(f"- Expected Result: {s.expected_result}")
            if s.alternative_investigation:
                lines.append(f"- Alternative: {s.alternative_investigation}")
            if s.escalation_criteria:
                lines.append(f"- Escalate if: {s.escalation_criteria}")
            lines.append("")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating troubleshooting for ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def draft_customer_reply(ticket_id: str, tone: str = "professional") -> str:
    """Draft a response to the customer based on conversation context and specified tone.

    NOTE: Draft only. Never sent automatically without agent review and confirmation.

    Args:
        ticket_id: Zendesk ticket ID.
        tone: Tone style ('professional', 'friendly', 'technical', 'empathetic', 'concise').
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.draft_reply(tid, tone=tone)
        draft_text = resp.recommended_draft.draft_text if hasattr(resp, "recommended_draft") else getattr(resp, "draft_reply", str(resp))
        return f"=== DRAFT CUSTOMER REPLY ({tone.upper()}) ===\n\n{draft_text}"
    except Exception as exc:
        return f"Error drafting customer reply for ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def classify_ticket(ticket_id: str) -> str:
    """Predict issue category, subcategory, priority recommendation, complexity, and department.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.classify_ticket(tid)
        return json.dumps(resp.model_dump(), indent=2)
    except Exception as exc:
        return f"Error classifying ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def analyze_sentiment(ticket_id: str) -> str:
    """Analyze customer sentiment, frustration escalation, repeated grievances, and churn risk.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.analyze_sentiment_and_frustration(tid)
        return json.dumps(resp.model_dump(), indent=2)
    except Exception as exc:
        return f"Error analyzing sentiment for ticket '{ticket_id}': {str(exc)}"


@mcp.tool()
async def find_similar_tickets(ticket_id: str) -> str:
    """Find historical resolved tickets with similar errors, symptoms, and potential duplicates.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        resp = await service.find_similar_tickets(tid)
        lines = [f"=== SIMILAR TICKETS FOR #{tid} ({len(resp.similar_tickets)} found) ===", ""]
        for t in resp.similar_tickets:
            dup_tag = " [POTENTIAL DUPLICATE]" if t.is_potential_duplicate else ""
            lines.append(f"- Ticket #{t.ticket_id}: {t.subject}{dup_tag}")
            lines.append(f"  Similarity: {round(t.similarity_score * 100)}% | Status: {t.status}")
            lines.append(f"  Matches: {', '.join(t.matching_reasons)}")
            if t.resolution_summary:
                lines.append(f"  Resolution: {t.resolution_summary}")
            lines.append("")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error finding similar tickets for '{ticket_id}': {str(exc)}"


@mcp.tool()
async def search_knowledge_base(query: str) -> str:
    """Search connected Zendesk Help Center documentation articles matching a technical issue or query.

    Args:
        query: Search keywords or problem description.
    """
    try:
        service = _get_service()
        articles = await service.zendesk.search_help_center(query=query)
        if not articles:
            return f"No Help Center articles found matching '{query}'."

        lines = [f"Found {len(articles)} article(s) matching '{query}':", ""]
        for a in articles:
            lines.append(f"- {a.title}: {a.url}")
            if a.snippet:
                lines.append(f"  Summary: {a.snippet}")
            lines.append("")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error searching knowledge base for '{query}': {str(exc)}"


@mcp.tool()
async def get_summary_history(ticket_id: str) -> str:
    """Retrieve historical AI summaries generated on this ticket.

    Args:
        ticket_id: Zendesk ticket ID.
    """
    try:
        tid = _parse_ticket_id(ticket_id)
        service = _get_service()
        history = await service.get_ticket_history(tid)
        if not history.summaries:
            return f"No past AI summaries found on ticket #{tid}."

        lines = [f"=== PAST SUMMARIES FOR TICKET #{tid} ({len(history.summaries)} recorded) ===", ""]
        for idx, s in enumerate(history.summaries, 1):
            time_str = s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "Unknown Time"
            lines.append(f"--- Summary #{idx} ({time_str}) ---")
            lines.append(s.body.strip())
            lines.append("")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving summary history for ticket '{ticket_id}': {str(exc)}"


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
        await service.post_summary_note(ticket_id=tid, note_body=note_text, public=False)
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
