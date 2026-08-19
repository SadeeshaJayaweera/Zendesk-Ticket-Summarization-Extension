"""Unit tests for TicketSummarizerService orchestration."""

from unittest.mock import AsyncMock
import pytest
from zendesk_summarizer_shared.config import Settings
from zendesk_summarizer_shared.models import (
    SummaryStructured,
    ZendeskComment,
    ZendeskTicket,
)
from zendesk_summarizer_shared.service import TicketSummarizerService


@pytest.fixture
def mock_zendesk():
    mock = AsyncMock()
    mock.get_ticket.return_value = ZendeskTicket(
        id=777,
        subject="Sync Error",
        description="Sync failing",
        status="open",
        requester_id=10,
    )
    mock.get_ticket_comments.return_value = [
        ZendeskComment(id=1, author_id=10, body="Sync failed with error 500", public=True),
        ZendeskComment(id=2, author_id=20, body="Checking database queue", public=False),
    ]
    mock.post_internal_note.return_value = ZendeskTicket(id=777, subject="Sync Error")
    return mock


@pytest.fixture
def mock_gemini():
    mock = AsyncMock()
    mock.generate_summary.return_value = SummaryStructured(
        executive_summary="Database sync failing with error 500.",
        customer_issue="Sync job stopped.",
        actions_taken=["Agent checking database queue."],
        current_status="In progress",
        action_items=["Restart worker pod."],
        sentiment="neutral",
    )
    return mock


@pytest.mark.asyncio
async def test_service_summarize_ticket(mock_zendesk, mock_gemini):
    """Test full summarize_ticket service flow."""
    service = TicketSummarizerService(
        zendesk_client=mock_zendesk,
        gemini_client=mock_gemini,
        settings=Settings(GEMINI_MODEL="gemini-1.5-flash"),
    )

    response = await service.summarize_ticket(777, summary_style="standard")
    assert response.ticket_id == 777
    assert response.subject == "Sync Error"
    assert response.summary.executive_summary == "Database sync failing with error 500."
    assert "### 🤖 AI Ticket Summary" in response.markdown_note
    assert mock_zendesk.get_ticket.called
    assert mock_zendesk.get_ticket_comments.called
    assert mock_gemini.generate_summary.called


@pytest.mark.asyncio
async def test_service_post_summary_note(mock_zendesk, mock_gemini):
    """Test post_summary_note service method enforcing private note."""
    service = TicketSummarizerService(
        zendesk_client=mock_zendesk,
        gemini_client=mock_gemini,
    )

    res = await service.post_summary_note(777, note_body="Internal AI summary", public=False)
    assert res.status == "success"
    assert res.is_public is False
    assert mock_zendesk.post_internal_note.called
    mock_zendesk.post_internal_note.assert_called_with(
        ticket_id=777,
        body="Internal AI summary",
        public=False,
    )


@pytest.mark.asyncio
async def test_service_summarize_and_post(mock_zendesk, mock_gemini):
    """Test summarize_and_post combined convenience method."""
    service = TicketSummarizerService(
        zendesk_client=mock_zendesk,
        gemini_client=mock_gemini,
    )

    summary_resp, post_resp = await service.summarize_and_post(777)
    assert summary_resp.ticket_id == 777
    assert post_resp.status == "success"
    assert mock_zendesk.post_internal_note.called
