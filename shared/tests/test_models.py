"""Unit tests for Pydantic models in zendesk_summarizer_shared.models."""

from datetime import datetime
from zendesk_summarizer_shared.models import (
    SummaryStructured,
    ZendeskComment,
    ZendeskTicket,
    SummarizeResponse,
    PostNoteRequest,
)


def test_zendesk_ticket_model():
    """Test ZendeskTicket parsing and default fields."""
    ticket = ZendeskTicket(
        id=123,
        subject="Login Failure",
        description="User cannot login",
        status="open",
        priority="high",
        requester_id=456,
        tags=["auth", "urgent"],
    )
    assert ticket.id == 123
    assert ticket.subject == "Login Failure"
    assert ticket.tags == ["auth", "urgent"]


def test_zendesk_comment_model():
    """Test ZendeskComment parsing and public flag defaults."""
    comment = ZendeskComment(
        id=999,
        author_id=456,
        body="This is an internal note",
        public=False,
    )
    assert comment.id == 999
    assert comment.public is False
    assert comment.attachments == []


def test_summary_structured_to_markdown():
    """Test converting SummaryStructured to formatted Markdown."""
    summary = SummaryStructured(
        executive_summary="Customer experiencing checkout timeout.",
        customer_issue="Gateway error 504 on credit card submission.",
        actions_taken=["Verified stripe webhook.", "Restarted payment pod."],
        current_status="Investigating payment gateway logs",
        action_items=["Follow up with customer in 1 hour", "Review Stripe dashboard"],
        sentiment="frustrated",
    )

    md = summary.to_markdown()
    assert "### 🤖 AI Ticket Summary" in md
    assert "Customer experiencing checkout timeout." in md
    assert "Gateway error 504 on credit card submission." in md
    assert "🟠 Frustrated" in md
    assert "- Verified stripe webhook." in md
    assert "- [ ] Follow up with customer in 1 hour" in md


def test_post_note_request_defaults_to_private():
    """Test that PostNoteRequest strictly defaults to public=False (Internal Note)."""
    req = PostNoteRequest(body="Note body here")
    assert req.public is False


def test_user_model_and_aliases():
    """Test User / ZendeskUser model parsing and aliases."""
    from zendesk_summarizer_shared.models import User, ZendeskUser, UserResponse, Ticket, Comment

    user = User(
        id=789,
        name="Support Lead",
        email="lead@example.com",
        role="admin",
        active=True,
    )
    assert isinstance(user, ZendeskUser)
    assert user.id == 789
    assert user.name == "Support Lead"
    assert user.role == "admin"
    assert user.active is True

    user_resp = UserResponse(user=user)
    assert user_resp.user.id == 789

    # Verify model alias equality
    assert User is ZendeskUser
    assert Ticket is ZendeskTicket
    assert Comment is ZendeskComment

