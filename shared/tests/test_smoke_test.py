"""Tests for connectivity smoke test verification functions."""

import os
import sys
import respx
import httpx
import pytest

# Ensure scripts directory is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))
from smoke_test import verify_zendesk_connectivity, verify_gemini_connectivity
from zendesk_summarizer_shared.config import Settings


@respx.mock
def test_verify_zendesk_connectivity_success():
    """Test Zendesk connectivity check with valid 200 response."""
    settings = Settings(
        ZENDESK_SUBDOMAIN="testdomain",
        ZENDESK_EMAIL="agent@testdomain.com",
        ZENDESK_API_TOKEN="valid-token",
        GEMINI_API_KEY="test-key",
    )

    mock_route = respx.get("https://testdomain.zendesk.com/api/v2/tickets.json?per_page=1").mock(
        return_value=httpx.Response(
            200,
            json={
                "tickets": [{"id": 101, "subject": "Test Ticket", "description": "Details"}],
                "count": 1,
            },
        )
    )

    result = verify_zendesk_connectivity(settings)
    assert result is True
    assert mock_route.called
    auth_header = mock_route.calls.last.request.headers.get("authorization", "")
    assert auth_header.startswith("Basic ")


@respx.mock
def test_verify_zendesk_connectivity_auth_failure():
    """Test Zendesk connectivity check with 401 unauthorized response."""
    settings = Settings(
        ZENDESK_SUBDOMAIN="testdomain",
        ZENDESK_EMAIL="agent@testdomain.com",
        ZENDESK_API_TOKEN="invalid-token",
    )

    respx.get("https://testdomain.zendesk.com/api/v2/tickets.json?per_page=1").mock(
        return_value=httpx.Response(401, json={"error": "Couldn't authenticate you"})
    )

    result = verify_zendesk_connectivity(settings)
    assert result is False


def test_verify_zendesk_connectivity_missing_config():
    """Test Zendesk connectivity check when credentials are unset."""
    settings = Settings(
        ZENDESK_SUBDOMAIN="",
        ZENDESK_EMAIL="",
        ZENDESK_API_TOKEN="",
    )
    result = verify_zendesk_connectivity(settings)
    assert result is False


@respx.mock
def test_verify_gemini_connectivity_success():
    """Test Gemini connectivity check with 200 response."""
    settings = Settings(
        GEMINI_API_KEY="valid-gemini-key",
        GEMINI_MODEL="gemini-1.5-flash",
    )

    mock_route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=valid-gemini-key"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "CONNECTED"}]
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )
    )

    result = verify_gemini_connectivity(settings)
    assert result is True
    assert mock_route.called


@respx.mock
def test_verify_gemini_connectivity_auth_failure():
    """Test Gemini connectivity check with 400/403 invalid key response."""
    settings = Settings(
        GEMINI_API_KEY="invalid-key",
        GEMINI_MODEL="gemini-1.5-flash",
    )

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=invalid-key"
    ).mock(
        return_value=httpx.Response(400, json={"error": {"message": "API key not valid."}})
    )

    result = verify_gemini_connectivity(settings)
    assert result is False


def test_verify_gemini_connectivity_missing_config():
    """Test Gemini connectivity check when API key is missing."""
    settings = Settings(GEMINI_API_KEY="")
    result = verify_gemini_connectivity(settings)
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_run_integration_check_flow(monkeypatch):
    """Test the full flow of run_integration_check with mocked endpoints."""
    from test_zendesk_integration import run_integration_check

    test_settings = Settings(
        ZENDESK_SUBDOMAIN="testdomain",
        ZENDESK_EMAIL="agent@testdomain.com",
        ZENDESK_API_TOKEN="valid-token",
    )
    monkeypatch.setattr("test_zendesk_integration.get_settings", lambda: test_settings)

    # 1. list_tickets
    respx.get("https://testdomain.zendesk.com/api/v2/tickets.json?per_page=5&page=1").mock(
        return_value=httpx.Response(200, json={"tickets": [{"id": 100, "subject": "Integration Test Ticket"}]})
    )
    # 2. get_ticket
    respx.get("https://testdomain.zendesk.com/api/v2/tickets/100.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "ticket": {
                    "id": 100,
                    "subject": "Integration Test Ticket",
                    "status": "open",
                    "priority": "normal",
                    "requester_id": 501,
                    "assignee_id": 901,
                    "tags": ["test"],
                },
                "users": [
                    {"id": 501, "name": "Requester User", "role": "end-user"},
                    {"id": 901, "name": "Assignee Agent", "role": "agent"},
                ],
            },
        )
    )
    # 3. get_ticket_comments
    respx.get("https://testdomain.zendesk.com/api/v2/tickets/100/comments.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "comments": [
                    {"id": 1, "author_id": 501, "body": "Initial user comment", "public": True}
                ],
                "count": 1,
            },
        )
    )
    # 4. post_internal_note
    post_route = respx.put("https://testdomain.zendesk.com/api/v2/tickets/100.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "ticket": {"id": 100, "subject": "Integration Test Ticket"},
                "audit": {
                    "id": 555,
                    "author_id": 901,
                    "events": [{"id": 9999, "type": "Comment", "public": False, "body": "Note", "author_id": 901}],
                },
            },
        )
    )

    success = await run_integration_check(ticket_id=100)
    assert success is True
    assert post_route.called
    req_body = post_route.calls.last.request.read().decode("utf-8")
    assert '"public": false' in req_body or '"public":false' in req_body

