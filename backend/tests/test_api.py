"""Comprehensive tests for FastAPI backend routes and error handling."""

from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from zendesk_summarizer_shared.models import (
    PostNoteResponse,
    SummarizeResponse,
    SummaryStructured,
    TicketDetailResponse,
    TicketHistoryResponse,
    TicketHistorySummaryItem,
    ZendeskComment,
    ZendeskTicket,
)

from zendesk_summarizer_shared.zendesk_client import (
    ZendeskAuthError,
    ZendeskNotFoundError,
    ZendeskRateLimitError,
)
from zendesk_summarizer_shared.gemini_client import GeminiAPIError


@pytest.fixture
def mock_service():
    """Mock TicketSummarizerService dependency."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def client(mock_service):
    """TestClient with overridden get_service dependency."""
    app.dependency_overrides[get_service] = lambda: mock_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_get_ticket_endpoint(client, mock_service):
    """Test GET /api/tickets/{ticket_id}."""
    mock_service.get_ticket_details.return_value = TicketDetailResponse(
        ticket=ZendeskTicket(id=101, subject="Login Failure", status="open"),
        comments=[
            ZendeskComment(id=1, author_id=10, body="Help!", public=True)
        ],
        total_comments=1,
    )

    response = client.get("/api/tickets/101")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket"]["id"] == 101
    assert data["ticket"]["subject"] == "Login Failure"
    assert len(data["comments"]) == 1
    mock_service.get_ticket_details.assert_called_once_with(101)


def test_get_ticket_history_endpoint(client, mock_service):
    """Test GET /api/tickets/{ticket_id}/history."""
    mock_service.get_ticket_history.return_value = TicketHistoryResponse(
        ticket_id=101,
        summaries=[
            TicketHistorySummaryItem(
                id=55,
                author_id=99,
                body="### 🤖 AI Ticket Summary\nIssue resolved",
                is_internal=True,
                preview="### 🤖 AI Ticket Summary",
            )
        ],
        total=1,
    )

    response = client.get("/api/tickets/101/history")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == 101
    assert len(data["summaries"]) == 1
    assert data["summaries"][0]["id"] == 55
    mock_service.get_ticket_history.assert_called_once_with(101)



def test_summarize_ticket_endpoint(client, mock_service):
    """Test POST /api/tickets/{ticket_id}/summarize."""
    structured = SummaryStructured(
        executive_summary="User cannot login.",
        customer_issue="Password expired.",
        actions_taken=["Reset email sent."],
        current_status="Awaiting user action",
        action_items=["Verify login."],
        sentiment="neutral",
    )
    mock_service.summarize_ticket.return_value = SummarizeResponse(
        ticket_id=101,
        subject="Login Failure",
        summary=structured,
        markdown_note=structured.to_markdown(),
        model_used="gemini-1.5-flash",
    )

    response = client.post(
        "/api/tickets/101/summarize",
        json={"summary_style": "brief"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == 101
    assert data["summary"]["executive_summary"] == "User cannot login."
    assert "### 🤖 AI Ticket Summary" in data["markdown_note"]
    mock_service.summarize_ticket.assert_called_once_with(ticket_id=101, summary_style="brief")


def test_post_note_endpoint(client, mock_service):
    """Test POST /api/tickets/{ticket_id}/notes."""
    mock_service.post_summary_note.return_value = PostNoteResponse(
        ticket_id=101,
        comment_id=555,
        is_public=False,
        status="success",
        message="Internal note posted successfully",
    )

    response = client.post(
        "/api/tickets/101/notes",
        json={"body": "AI Note content", "public": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_public"] is False
    mock_service.post_summary_note.assert_called_once_with(
        ticket_id=101,
        note_body="AI Note content",
        public=False,
    )


def test_summarize_and_post_endpoint(client, mock_service):
    """Test POST /api/tickets/{ticket_id}/summarize-and-post."""
    structured = SummaryStructured(
        executive_summary="Summary text.",
        customer_issue="Issue text.",
        actions_taken=[],
        current_status="Resolved",
        action_items=[],
        sentiment="positive",
    )
    summary_resp = SummarizeResponse(
        ticket_id=101,
        summary=structured,
        markdown_note="Note markdown",
        model_used="gemini-1.5-flash",
    )
    post_resp = PostNoteResponse(ticket_id=101, is_public=False, status="success")
    mock_service.summarize_and_post.return_value = (summary_resp, post_resp)

    response = client.post("/api/tickets/101/summarize-and-post")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == 101


def test_summarize_raw_text_endpoint(client, mock_service):
    """Test POST /api/summarize-text."""
    structured = SummaryStructured(
        executive_summary="Direct text summary.",
        customer_issue="Query details.",
        actions_taken=[],
        current_status="Open",
        action_items=[],
        sentiment="neutral",
    )
    mock_service.summarize_raw_text.return_value = SummarizeResponse(
        subject="Custom Transcript",
        summary=structured,
        markdown_note="Markdown content",
        model_used="gemini-1.5-flash",
    )

    response = client.post(
        "/api/summarize-text",
        json={"text": "Customer: Help with checkout", "subject": "Custom Transcript"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["executive_summary"] == "Direct text summary."


def test_zendesk_not_found_error_mapping(client, mock_service):
    """Test mapping ZendeskNotFoundError to HTTP 404."""
    mock_service.get_ticket_details.side_effect = ZendeskNotFoundError("Ticket 999 not found", status_code=404)

    response = client.get("/api/tickets/999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "ZendeskNotFoundError"


def test_zendesk_rate_limit_error_mapping(client, mock_service):
    """Test mapping ZendeskRateLimitError to HTTP 429 with Retry-After header."""
    mock_service.summarize_ticket.side_effect = ZendeskRateLimitError("Rate limit hit", retry_after=30)

    response = client.post("/api/tickets/101/summarize")
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "30"
    data = response.json()
    assert data["error"] == "ZendeskRateLimitError"
    assert data["retry_after"] == 30


def test_gemini_api_error_mapping(client, mock_service):
    """Test mapping GeminiAPIError to HTTP 502 Bad Gateway."""
    mock_service.summarize_raw_text.side_effect = GeminiAPIError("Gemini service unavailable")

    response = client.post(
        "/api/summarize-text",
        json={"text": "Some conversation"},
    )
    assert response.status_code == 502
    data = response.json()
    assert data["error"] == "GeminiAPIError"
