"""Unit tests for ZendeskClient using respx mock."""

import json
from unittest.mock import AsyncMock
import httpx
import pytest
import respx
from zendesk_summarizer_shared.config import Settings
from zendesk_summarizer_shared.models import Comment, Ticket, User, ZendeskComment, ZendeskTicket, ZendeskUser
from zendesk_summarizer_shared.zendesk_client import (
    ZendeskAPIError,
    ZendeskAuthError,
    ZendeskClient,
    ZendeskNotFoundError,
    ZendeskRateLimitError,
    ZendeskValidationError,
)


@pytest.fixture
def settings():
    return Settings(
        ZENDESK_SUBDOMAIN="testhelp",
        ZENDESK_EMAIL="support@testhelp.com",
        ZENDESK_API_TOKEN="token999",
    )


@pytest.fixture
def noop_sleep():
    """Mock sleep function that avoids real time delays in tests."""
    return AsyncMock()


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_success(settings):
    """Test retrieving a ticket successfully with full metadata."""
    client = ZendeskClient(settings=settings)
    mock_ticket = {
        "ticket": {
            "id": 1234,
            "url": "https://testhelp.zendesk.com/api/v2/tickets/1234.json",
            "subject": "Payment issue",
            "description": "Payment was declined",
            "status": "open",
            "priority": "high",
            "requester_id": 501,
            "assignee_id": 901,
            "tags": ["billing", "vip"],
            "created_at": "2026-08-18T10:00:00Z",
            "updated_at": "2026-08-18T10:30:00Z",
        }
    }
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(200, json=mock_ticket)
    )

    ticket = await client.get_ticket(1234)
    assert isinstance(ticket, Ticket)
    assert ticket.id == 1234
    assert ticket.subject == "Payment issue"
    assert ticket.status == "open"
    assert ticket.priority == "high"
    assert ticket.requester_id == 501
    assert ticket.assignee_id == 901
    assert ticket.tags == ["billing", "vip"]


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_not_found(settings):
    """Test 404 Not Found error handling."""
    client = ZendeskClient(settings=settings)
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/9999.json").mock(
        return_value=httpx.Response(404, json={"error": "RecordNotFound"})
    )

    with pytest.raises(ZendeskNotFoundError) as exc_info:
        await client.get_ticket(9999)
    assert exc_info.value.status_code == 404
    assert "9999" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_auth_error_401(settings):
    """Test 401 Unauthorized handling."""
    client = ZendeskClient(settings=settings)
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(401, json={"error": "InvalidCredentials"})
    )

    with pytest.raises(ZendeskAuthError) as exc_info:
        await client.get_ticket(1234)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_forbidden_403(settings):
    """Test 403 Forbidden handling."""
    client = ZendeskClient(settings=settings)
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(403, json={"error": "Forbidden"})
    )

    with pytest.raises(ZendeskAuthError) as exc_info:
        await client.get_ticket(1234)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_validation_error_422(settings):
    """Test 422 Unprocessable Entity handling."""
    client = ZendeskClient(settings=settings)
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(422, json={"error": "UnprocessableEntity", "details": "Max limit reached"})
    )

    with pytest.raises(ZendeskValidationError) as exc_info:
        await client.get_ticket(1234)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_comments_single_page(settings):
    """Test retrieving ticket comments from a single page."""
    client = ZendeskClient(settings=settings)
    mock_comments = {
        "comments": [
            {
                "id": 1,
                "author_id": 501,
                "body": "First public comment",
                "public": True,
                "created_at": "2026-08-18T10:00:00Z",
            },
            {
                "id": 2,
                "author_id": 502,
                "body": "Internal triage note",
                "public": False,
                "created_at": "2026-08-18T10:10:00Z",
            },
        ],
        "count": 2,
        "next_page": None,
    }
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234/comments.json").mock(
        return_value=httpx.Response(200, json=mock_comments)
    )

    comments = await client.get_ticket_comments(1234)
    assert len(comments) == 2
    assert isinstance(comments[0], Comment)
    assert comments[0].public is True
    assert comments[1].public is False
    assert comments[1].body == "Internal triage note"


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_comments_pagination_multiple_pages(settings):
    """Test pagination for tickets with long threads across multiple pages."""
    client = ZendeskClient(settings=settings)

    page1_data = {
        "comments": [
            {"id": 101, "author_id": 501, "body": "Comment page 1 - item 1", "public": True},
            {"id": 102, "author_id": 502, "body": "Comment page 1 - item 2", "public": False},
        ],
        "count": 4,
        "next_page": "https://testhelp.zendesk.com/api/v2/tickets/1234/comments.json?page=2",
    }
    page2_data = {
        "comments": [
            {"id": 103, "author_id": 501, "body": "Comment page 2 - item 3", "public": True},
            {"id": 104, "author_id": 502, "body": "Comment page 2 - item 4", "public": False},
        ],
        "count": 4,
        "next_page": None,
    }

    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234/comments.json?page=2").mock(
        return_value=httpx.Response(200, json=page2_data)
    )
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234/comments.json").mock(
        return_value=httpx.Response(200, json=page1_data)
    )

    comments = await client.get_ticket_comments(1234)
    assert len(comments) == 4
    assert [c.id for c in comments] == [101, 102, 103, 104]
    assert comments[0].body == "Comment page 1 - item 1"
    assert comments[3].body == "Comment page 2 - item 4"



@pytest.mark.asyncio
@respx.mock
async def test_post_internal_note_sends_public_false_strictly(settings):
    """CRITICAL TEST: Verify post_internal_note strictly sends public: false in JSON body."""
    client = ZendeskClient(settings=settings)
    mock_response = {
        "ticket": {
            "id": 1234,
            "subject": "Payment issue",
            "status": "open",
            "updated_at": "2026-08-18T10:15:00Z",
            "assignee_id": 901,
        }
    }
    route = respx.put("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    comment = await client.post_internal_note(1234, body="Confidential internal diagnosis")
    assert route.called
    assert isinstance(comment, Comment)

    # Inspect exact request payload
    sent_request = route.calls.last.request
    payload = json.loads(sent_request.read().decode("utf-8"))

    assert "ticket" in payload
    assert "comment" in payload["ticket"]
    assert payload["ticket"]["comment"]["public"] is False
    assert payload["ticket"]["comment"]["body"] == "Confidential internal diagnosis"


@pytest.mark.asyncio
@respx.mock
async def test_post_internal_note_with_audit_parsing(settings):
    """Test that post_internal_note parses created Comment from audit events."""
    client = ZendeskClient(settings=settings)
    mock_response = {
        "ticket": {
            "id": 1234,
            "subject": "Payment issue",
        },
        "audit": {
            "id": 8888,
            "ticket_id": 1234,
            "author_id": 901,
            "created_at": "2026-08-18T10:20:00Z",
            "events": [
                {
                    "id": 77777,
                    "type": "Comment",
                    "author_id": 901,
                    "body": "AI Note body",
                    "public": False,
                }
            ],
        },
    }
    respx.put("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    comment = await client.post_internal_note(1234, body="AI Note body")
    assert comment.id == 77777
    assert comment.author_id == 901
    assert comment.public is False
    assert comment.audit_id == 8888


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_retry_success_with_retry_after(settings, noop_sleep):
    """Test 429 Rate Limit retry behavior: retries with Retry-After delay and succeeds."""
    client = ZendeskClient(settings=settings, max_retries=3, sleep_fn=noop_sleep)

    route = respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "2"}, json={"error": "TooManyRequests"}),
        httpx.Response(200, json={"ticket": {"id": 1234, "subject": "Recovered"}}),
    ]

    ticket = await client.get_ticket(1234)
    assert ticket.id == 1234
    assert ticket.subject == "Recovered"
    assert route.call_count == 2
    noop_sleep.assert_called_once_with(2.0)


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_retry_exhausted(settings, noop_sleep):
    """Test 429 Rate Limit retry exhaustion raises ZendeskRateLimitError."""
    client = ZendeskClient(settings=settings, max_retries=2, sleep_fn=noop_sleep)

    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "5"}, json={"error": "TooManyRequests"})
    )

    with pytest.raises(ZendeskRateLimitError) as exc_info:
        await client.get_ticket(1234)

    assert exc_info.value.retry_after == 5
    assert exc_info.value.status_code == 429
    assert noop_sleep.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_user_success(settings):
    """Test retrieving a single user by ID."""
    client = ZendeskClient(settings=settings)
    mock_user = {
        "user": {
            "id": 501,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "role": "end-user",
            "active": True,
        }
    }
    respx.get("https://testhelp.zendesk.com/api/v2/users/501.json").mock(
        return_value=httpx.Response(200, json=mock_user)
    )

    user = await client.get_user(501)
    assert isinstance(user, User)
    assert user.id == 501
    assert user.name == "Jane Doe"
    assert user.email == "jane@example.com"
    assert user.role == "end-user"


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_requester_and_assignee_sideloaded(settings):
    """Test retrieving requester and assignee via side-loaded users."""
    client = ZendeskClient(settings=settings)
    mock_ticket_with_users = {
        "ticket": {
            "id": 1234,
            "subject": "Bug Report",
            "requester_id": 501,
            "assignee_id": 901,
        },
        "users": [
            {"id": 501, "name": "Jane Customer", "email": "customer@example.com", "role": "end-user"},
            {"id": 901, "name": "Bob Agent", "email": "agent@example.com", "role": "agent"},
        ],
    }
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(200, json=mock_ticket_with_users)
    )

    requester, assignee = await client.get_ticket_requester_and_assignee(1234)
    assert requester is not None
    assert requester.id == 501
    assert requester.name == "Jane Customer"
    assert assignee is not None
    assert assignee.id == 901
    assert assignee.name == "Bob Agent"


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_requester_and_assignee_fallback(settings):
    """Test fallback to individual user lookups if not side-loaded."""
    client = ZendeskClient(settings=settings)
    mock_ticket_no_users = {
        "ticket": {
            "id": 1234,
            "subject": "Bug Report",
            "requester_id": 501,
            "assignee_id": 901,
        }
    }
    respx.get("https://testhelp.zendesk.com/api/v2/tickets/1234.json").mock(
        return_value=httpx.Response(200, json=mock_ticket_no_users)
    )
    respx.get("https://testhelp.zendesk.com/api/v2/users/501.json").mock(
        return_value=httpx.Response(200, json={"user": {"id": 501, "name": "Jane Customer", "role": "end-user"}})
    )
    respx.get("https://testhelp.zendesk.com/api/v2/users/901.json").mock(
        return_value=httpx.Response(200, json={"user": {"id": 901, "name": "Bob Agent", "role": "agent"}})
    )

    requester, assignee = await client.get_ticket_requester_and_assignee(1234)
    assert requester is not None
    assert requester.name == "Jane Customer"
    assert assignee is not None
    assert assignee.name == "Bob Agent"


@pytest.mark.asyncio
async def test_network_error_handling(settings):
    """Test network connection error wrapping in ZendeskAPIError."""
    # Create client with mock transport that raises ConnectError
    mock_transport = httpx.MockTransport(httpx.Response(200))

    async def raise_connect_error(request):
        raise httpx.ConnectError("Connection refused", request=request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(raise_connect_error))
    client = ZendeskClient(settings=settings, client=mock_client)

    with pytest.raises(ZendeskAPIError) as exc_info:
        await client.get_ticket(1234)

    assert "Network error" in str(exc_info.value)
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_missing_credentials_raises_auth_error():
    """Test that missing credentials raises ZendeskAuthError immediately."""
    empty_settings = Settings(ZENDESK_SUBDOMAIN="", ZENDESK_EMAIL="", ZENDESK_API_TOKEN="")
    client = ZendeskClient(settings=empty_settings)

    with pytest.raises(ZendeskAuthError):
        await client.get_ticket(1234)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets(settings):
    """Test listing tickets with pagination parameters."""
    client = ZendeskClient(settings=settings)
    respx.get("https://testhelp.zendesk.com/api/v2/tickets.json?per_page=5&page=1").mock(
        return_value=httpx.Response(
            200,
            json={
                "tickets": [
                    {"id": 1, "subject": "Ticket 1", "status": "open"},
                    {"id": 2, "subject": "Ticket 2", "status": "closed"},
                ]
            },
        )
    )

    tickets = await client.list_tickets(per_page=5, page=1)
    assert len(tickets) == 2
    assert tickets[0].id == 1
    assert tickets[1].id == 2

