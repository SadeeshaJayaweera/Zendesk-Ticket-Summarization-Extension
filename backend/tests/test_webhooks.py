"""Unit tests for Zendesk webhook signature verification and automated solve trigger workflow."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service, get_settings
from zendesk_summarizer_shared.config import Settings
from zendesk_summarizer_shared.draft_store import DraftStore, get_draft_store
from zendesk_summarizer_shared.models import (
    PendingDraft,
    PostNoteResponse,
    SummarizeResponse,
    SummaryStructured,
    Ticket,
    TicketDetailResponse,
    ZendeskComment,
    ZendeskTicket,
)
from zendesk_summarizer_shared.security import (
    WebhookVerificationError,
    compute_zendesk_webhook_signature,
    verify_zendesk_webhook_signature,
)


@pytest.fixture
def clean_draft_store():
    """Ensure a clean draft store for tests."""
    store = get_draft_store()
    store.clear()
    yield store
    store.clear()


@pytest.fixture
def mock_service(clean_draft_store):
    service = AsyncMock()
    service.draft_store = clean_draft_store
    return service


@pytest.fixture
def client(mock_service):
    app.dependency_overrides[get_service] = lambda: mock_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# --- Security & Signature Verification Unit Tests ---

def test_compute_and_verify_signature_success():
    """Test valid signature computation and verification."""
    secret = "my-secret-webhook-key-123"
    timestamp = "2026-08-18T15:00:00Z"
    body = json.dumps({"ticket": {"id": 1001, "status": "solved"}})

    signature = compute_zendesk_webhook_signature(body=body, timestamp=timestamp, secret=secret)
    assert signature is not None
    assert len(signature) > 10

    # Verification must pass
    assert verify_zendesk_webhook_signature(
        body=body,
        signature_header=signature,
        timestamp_header=timestamp,
        secret=secret,
    ) is True


def test_verify_signature_mismatch():
    """Test verification failure on tampered body or invalid signature."""
    secret = "my-secret-webhook-key-123"
    timestamp = "2026-08-18T15:00:00Z"
    body = json.dumps({"ticket": {"id": 1001, "status": "solved"}})
    tampered_body = json.dumps({"ticket": {"id": 1001, "status": "open"}})

    signature = compute_zendesk_webhook_signature(body=body, timestamp=timestamp, secret=secret)

    with pytest.raises(WebhookVerificationError) as exc_info:
        verify_zendesk_webhook_signature(
            body=tampered_body,
            signature_header=signature,
            timestamp_header=timestamp,
            secret=secret,
        )
    assert "Invalid webhook signature" in str(exc_info.value)


def test_verify_signature_missing_headers():
    """Test verification failure on missing signature or timestamp headers."""
    secret = "test-secret"
    body = "{}"

    with pytest.raises(WebhookVerificationError) as exc1:
        verify_zendesk_webhook_signature(body, signature_header=None, timestamp_header="123", secret=secret)
    assert "Missing 'X-Zendesk-Webhook-Signature'" in str(exc1.value)

    with pytest.raises(WebhookVerificationError) as exc2:
        verify_zendesk_webhook_signature(body, signature_header="sig", timestamp_header=None, secret=secret)
    assert "Missing 'X-Zendesk-Webhook-Signature-Timestamp'" in str(exc2.value)


# --- Webhook Endpoint Integration Tests ---

def test_webhook_endpoint_valid_signature_and_draft_creation(client, mock_service, clean_draft_store):
    """Test POST /webhooks/zendesk/ticket-status-changed with valid HMAC signature."""
    secret = "webhook-test-secret"
    app.dependency_overrides[get_settings] = lambda: Settings(
        ZENDESK_WEBHOOK_SECRET=secret,
        GEMINI_API_KEY="test-key",
    )

    timestamp = "2026-08-18T15:30:00Z"
    payload = {
        "ticket": {
            "id": 999,
            "status": "solved",
            "subject": "VPN connection drops",
        }
    }
    body_str = json.dumps(payload)
    sig = compute_zendesk_webhook_signature(body=body_str, timestamp=timestamp, secret=secret)

    # Mock service.process_solved_ticket_webhook
    mock_draft = PendingDraft(
        ticket_id=999,
        status="pending_review",
        summary=SummaryStructured(
            executive_summary="VPN MTU mismatch caused packet drops.",
            customer_issue="VPN connection drops.",
            actions_taken=["Updated MTU setting to 1420."],
            current_status="Solved",
            sentiment="neutral",
        ),
        markdown_note="### 🤖 AI Ticket Summary\nVPN MTU mismatch solved.",
    )
    mock_service.process_solved_ticket_webhook.return_value = mock_draft

    response = client.post(
        "/webhooks/zendesk/ticket-status-changed",
        content=body_str,
        headers={
            "Content-Type": "application/json",
            "X-Zendesk-Webhook-Signature": sig,
            "X-Zendesk-Webhook-Signature-Timestamp": timestamp,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["ticket_id"] == 999
    assert data["draft_status"] == "pending_review"
    mock_service.process_solved_ticket_webhook.assert_called_once_with(ticket_id=999)


def test_webhook_endpoint_invalid_signature_rejected(client):
    """Test POST /webhooks/zendesk/ticket-status-changed rejects invalid signature with 401."""
    app.dependency_overrides[get_settings] = lambda: Settings(ZENDESK_WEBHOOK_SECRET="secret-123")

    body_str = json.dumps({"ticket": {"id": 999, "status": "solved"}})
    response = client.post(
        "/webhooks/zendesk/ticket-status-changed",
        content=body_str,
        headers={
            "Content-Type": "application/json",
            "X-Zendesk-Webhook-Signature": "invalid-signature-value",
            "X-Zendesk-Webhook-Signature-Timestamp": "2026-08-18T15:30:00Z",
        },
    )
    assert response.status_code == 401
    assert "Invalid webhook signature" in response.json()["detail"]


def test_get_pending_draft_endpoint(client, mock_service, clean_draft_store):
    """Test GET /api/tickets/{ticket_id}/pending-draft when draft exists."""
    from zendesk_summarizer_shared.models import PendingDraftResponse

    mock_draft = PendingDraft(
        ticket_id=505,
        status="pending_review",
        summary=SummaryStructured(
            executive_summary="Draft summary.",
            customer_issue="Issue.",
            actions_taken=[],
            current_status="Solved",
            sentiment="positive",
        ),
        markdown_note="### 🤖 AI Summary Note",
    )
    mock_service.get_pending_draft.return_value = PendingDraftResponse(
        ticket_id=505,
        has_pending_draft=True,
        draft=mock_draft,
    )

    response = client.get("/api/tickets/505/pending-draft")
    assert response.status_code == 200
    data = response.json()
    assert data["has_pending_draft"] is True
    assert data["draft"]["ticket_id"] == 505
    assert data["draft"]["status"] == "pending_review"
    assert "### 🤖 AI Summary Note" in data["draft"]["markdown_note"]


def test_draft_store_workflow(clean_draft_store):
    """Test DraftStore save, retrieval, posted lifecycle."""
    summary = SummaryStructured(
        executive_summary="Exec",
        customer_issue="Issue",
        actions_taken=[],
        current_status="Solved",
        sentiment="neutral",
    )

    # 1. Save draft
    draft = clean_draft_store.save_draft(
        ticket_id=777,
        summary=summary,
        markdown_note="Note",
    )
    assert draft.status == "pending_review"

    # 2. Get pending draft
    retrieved = clean_draft_store.get_pending_draft(777)
    assert retrieved is not None
    assert retrieved.ticket_id == 777

    # 3. Mark as posted
    posted = clean_draft_store.mark_draft_posted(777)
    assert posted.status == "posted"

    # 4. Pending draft is no longer returned as pending_review
    assert clean_draft_store.get_pending_draft(777) is None
