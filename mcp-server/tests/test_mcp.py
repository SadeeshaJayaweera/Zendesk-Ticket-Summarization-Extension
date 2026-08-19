"""Unit tests for MCP Server tool handlers and defensive parsing."""

from unittest.mock import AsyncMock, patch
from datetime import datetime
import pytest

from mcp_server.server import (
    _parse_ticket_id,
    get_service_status,
    get_ticket,
    list_recent_tickets,
    post_internal_note,
    summarize_text,
    summarize_ticket,
)
from zendesk_summarizer_shared.models import (
    Comment,
    PostNoteResponse,
    SummarizeResponse,
    SummaryStructured,
    Ticket,
    TicketDetailResponse,
)


def test_parse_ticket_id():
    """Test defensive parsing of ticket ID strings and ints."""
    assert _parse_ticket_id(123) == 123
    assert _parse_ticket_id("123") == 123
    assert _parse_ticket_id("#123") == 123
    assert _parse_ticket_id("  #456  ") == 456

    with pytest.raises(ValueError):
        _parse_ticket_id("abc")


def test_get_service_status():
    """Test get_service_status tool output."""
    status_str = get_service_status()
    assert "Zendesk Ticket Summarizer MCP Server" in status_str
    assert "Zendesk Integration:" in status_str
    assert "LLM Provider:" in status_str


@pytest.mark.asyncio
async def test_get_ticket_tool():
    """Test get_ticket tool returning metadata and conversation thread."""
    mock_service = AsyncMock()
    ticket = Ticket(
        id=55,
        subject="Hardware problem",
        description="Printer broken",
        status="open",
        priority="high",
        requester_id=12,
        assignee_id=34,
        tags=["hardware", "printer"],
        created_at=datetime(2026, 8, 18, 10, 0, 0),
    )
    comments = [
        Comment(id=1, author_id=12, body="Printer is showing error 103.", public=True, created_at=datetime(2026, 8, 18, 10, 0, 0)),
        Comment(id=2, author_id=34, body="Ordered replacement toner drum.", public=False, created_at=datetime(2026, 8, 18, 10, 15, 0)),
    ]
    mock_service.get_ticket_details.return_value = TicketDetailResponse(
        ticket=ticket,
        comments=comments,
        total_comments=2,
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await get_ticket("#55")
        assert "=== TICKET #55: Hardware problem ===" in res
        assert "Status: OPEN | Priority: HIGH" in res
        assert "=== CONVERSATION THREAD (2 comments) ===" in res
        assert "[PUBLIC REPLY]" in res
        assert "Printer is showing error 103." in res
        assert "[INTERNAL NOTE (PRIVATE)]" in res
        assert "Ordered replacement toner drum." in res


@pytest.mark.asyncio
async def test_list_recent_tickets_tool():
    """Test list_recent_tickets tool with and without status filter."""
    mock_service = AsyncMock()
    mock_service.list_recent_tickets.return_value = [
        Ticket(id=101, subject="Network Outage", status="open", priority="urgent"),
        Ticket(id=102, subject="Password Reset", status="solved", priority="normal"),
    ]

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await list_recent_tickets(status="open", limit=5)
        assert "Found 2 recent ticket(s) matching status 'open':" in res
        assert "- Ticket #101: [OPEN] Network Outage (Priority: urgent)" in res
        assert "- Ticket #102: [SOLVED] Password Reset (Priority: normal)" in res
        mock_service.list_recent_tickets.assert_called_once_with(status="open", limit=5)


@pytest.mark.asyncio
async def test_summarize_ticket_tool():
    """Test summarize_ticket tool generating draft summary."""
    mock_service = AsyncMock()
    structured = SummaryStructured(
        executive_summary="Printer toner needs replacement.",
        customer_issue="Printer showing error 103.",
        actions_taken=["Ordered toner drum."],
        current_status="Waiting for shipment",
        commitments=["Delivery expected tomorrow"],
        action_items=["Install toner drum."],
        sentiment="neutral",
    )
    mock_service.summarize_ticket.return_value = SummarizeResponse(
        ticket_id=55,
        summary=structured,
        markdown_note="### 🤖 AI Ticket Summary\nPrinter toner needs replacement.",
        model_used="gemini-1.5-flash",
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await summarize_ticket("55", style="brief")
        assert "### 🤖 AI Ticket Summary" in res
        assert "Printer toner needs replacement" in res
        mock_service.summarize_ticket.assert_called_once_with(55, summary_style="brief")


@pytest.mark.asyncio
async def test_post_internal_note_tool():
    """Test post_internal_note tool handler."""
    mock_service = AsyncMock()
    mock_service.post_summary_note.return_value = PostNoteResponse(ticket_id=55, is_public=False, status="success")

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await post_internal_note("#55", "### 🤖 AI Ticket Summary\nIssue diagnosed.")
        assert "Success: Internal note posted successfully to Zendesk ticket #55." in res
        mock_service.post_summary_note.assert_called_once_with(
            ticket_id=55,
            note_body="### 🤖 AI Ticket Summary\nIssue diagnosed.",
            public=False,
        )


@pytest.mark.asyncio
async def test_post_internal_note_empty_body_rejection():
    """Test post_internal_note rejects empty note bodies."""
    res = await post_internal_note("55", "   ")
    assert "Error: Cannot post an empty internal note." in res


@pytest.mark.asyncio
async def test_summarize_text_tool():
    """Test summarize_text tool."""
    mock_service = AsyncMock()
    structured = SummaryStructured(
        executive_summary="Text summary.",
        customer_issue="General query.",
        actions_taken=[],
        current_status="Done",
        action_items=[],
        sentiment="neutral",
    )
    mock_service.summarize_raw_text.return_value = SummarizeResponse(
        summary=structured,
        markdown_note="### 🤖 AI Transcript Summary\nGeneral query resolved.",
        model_used="gemini-1.5-flash",
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await summarize_text("Customer: Where is my order?", subject="Order Status")
        assert "### 🤖 AI Transcript Summary" in res
        mock_service.summarize_raw_text.assert_called_once_with(
            text="Customer: Where is my order?",
            subject="Order Status",
            summary_style="standard",
        )
