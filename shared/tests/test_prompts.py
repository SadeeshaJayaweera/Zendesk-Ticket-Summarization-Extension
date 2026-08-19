"""Unit tests for prompt templates and conversation formatting."""

from zendesk_summarizer_shared.models import ZendeskComment, ZendeskTicket
from zendesk_summarizer_shared.prompts import (
    build_raw_text_prompt,
    build_summarization_prompt,
    format_conversation_transcript,
)


def test_format_conversation_transcript():
    """Test conversation formatting with ticket and comments."""
    ticket = ZendeskTicket(
        id=101,
        subject="Password Reset",
        description="I forgot my password",
        requester_id=500,
        assignee_id=600,
    )
    comments = [
        ZendeskComment(
            id=1,
            author_id=500,
            body="I need help resetting my password.",
            public=True,
        ),
        ZendeskComment(
            id=2,
            author_id=600,
            body="Reset link generated internally.",
            public=False,
        ),
    ]

    transcript = format_conversation_transcript(ticket, comments)
    assert "Ticket ID: #101" in transcript
    assert "Subject: Password Reset" in transcript
    assert "[PUBLIC REPLY] Requester/Customer" in transcript
    assert "[INTERNAL NOTE (PRIVATE)] Assigned Agent" in transcript


def test_build_summarization_prompt():
    """Test building full summarization prompt for Gemini."""
    ticket = ZendeskTicket(id=101, subject="Bug Report")
    comments = [ZendeskComment(id=1, author_id=500, body="Crash on load", public=True)]

    prompt = build_summarization_prompt(ticket, comments, summary_style="detailed")
    assert "Zendesk Customer Support Operations AI Assistant" in prompt
    assert "JSON Schema" in prompt
    assert "Bug Report" in prompt
    assert "Crash on load" in prompt


def test_build_raw_text_prompt():
    """Test building raw text prompt for arbitrary conversation."""
    prompt = build_raw_text_prompt("Customer: Hello, I have an issue.", subject="Support Chat")
    assert "Subject: Support Chat" in prompt
    assert "Customer: Hello, I have an issue." in prompt
