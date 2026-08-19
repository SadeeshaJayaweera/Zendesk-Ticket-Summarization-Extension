"""Unit tests for AI Summarization Engine in shared/summarizer.py."""

import json
from datetime import datetime
import httpx
import pytest
import respx
from pydantic import SecretStr

from zendesk_summarizer_shared.config import Settings
from zendesk_summarizer_shared.models import (
    Comment,
    SummaryStructured,
    Ticket,
    TicketSummary,
    User,
)
from zendesk_summarizer_shared.summarizer import (
    BaseSummarizer,
    GeminiSummarizer,
    GroqSummarizer,
    InternalNoteFormatter,
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    SummarizationError,
    TicketContextBuilder,
    extract_structured_json,
    get_summarizer,
    parse_llm_response_to_summary,
)


# --- Fixtures ---

@pytest.fixture
def sample_ticket():
    return Ticket(
        id=4001,
        subject="Cannot export CSV reports",
        description="I am getting a timeout error 504 when trying to export my transactions to CSV.",
        status="open",
        priority="high",
        requester_id=101,
        assignee_id=202,
        tags=["reports", "export", "billing"],
        created_at=datetime(2026, 8, 18, 9, 0, 0),
    )


@pytest.fixture
def sample_users():
    requester = User(id=101, name="Alice Customer", email="alice@company.com", role="end-user")
    assignee = User(id=202, name="Bob Agent", email="bob@support.com", role="agent")
    return requester, assignee


@pytest.fixture
def sample_comments():
    return [
        Comment(
            id=1,
            author_id=101,
            body="I am getting a timeout error 504 when trying to export my transactions to CSV.",
            public=True,
            created_at=datetime(2026, 8, 18, 9, 0, 0),
        ),
        Comment(
            id=2,
            author_id=202,
            body="Checked worker logs; database query is taking > 30s on account 101. Increasing worker timeout.",
            public=False,
            created_at=datetime(2026, 8, 18, 9, 15, 0),
        ),
        Comment(
            id=3,
            author_id=202,
            body="Hi Alice, we identified slow query performance on large date ranges. We are applying a patch and will update you by 2 PM.",
            public=True,
            created_at=datetime(2026, 8, 18, 9, 30, 0),
        ),
    ]


# --- TicketContextBuilder Tests ---

def test_ticket_context_builder_metadata_and_speaker_labels(sample_ticket, sample_comments, sample_users):
    """Test that context builder accurately formats metadata, speaker roles, and visibility."""
    requester, assignee = sample_users
    builder = TicketContextBuilder()
    context = builder.build_context(
        ticket=sample_ticket,
        comments=sample_comments,
        requester=requester,
        assignee=assignee,
    )

    # Verify metadata block
    assert "=== TICKET METADATA ===" in context
    assert "Ticket ID: #4001" in context
    assert "Subject: Cannot export CSV reports" in context
    assert "Requester: Alice Customer (alice@company.com)" in context
    assert "Assignee: Bob Agent (bob@support.com)" in context
    assert "Tags: reports, export, billing" in context

    # Verify speaker labels & visibility
    assert "[1] [PUBLIC REPLY] Customer / Requester: Alice Customer" in context
    assert "[2] [INTERNAL NOTE (PRIVATE)] Support Agent: Bob Agent" in context
    assert "[3] [PUBLIC REPLY] Support Agent: Bob Agent" in context

    # Verify conversation bodies
    assert "timeout error 504" in context
    assert "Increasing worker timeout." in context
    assert "will update you by 2 PM." in context


def test_ticket_context_builder_truncation_on_long_thread(sample_ticket, sample_users):
    """Test smart truncation on a synthetic 30-comment thread.

    Verifies:
    1. Comment #1 is preserved in full.
    2. Middle comments are compressed into 1-line timestamped summaries.
    3. Last 8 comments are preserved in full.
    """
    requester, assignee = sample_users
    builder = TicketContextBuilder(max_comments=10, keep_recent_comments=4)

    # Generate 20 synthetic comments
    comments = []
    for i in range(1, 21):
        is_customer = (i % 2 != 0)
        comments.append(
            Comment(
                id=i,
                author_id=101 if is_customer else 202,
                body=f"Comment #{i} content detailing troubleshooting iteration {i}.",
                public=True,
                created_at=datetime(2026, 8, 18, 10, i, 0),
            )
        )

    context = builder.build_context(
        ticket=sample_ticket,
        comments=comments,
        requester=requester,
        assignee=assignee,
    )

    # Opening anchor must be in full
    assert "[1] [PUBLIC REPLY] Customer / Requester: Alice Customer" in context
    assert "[OPENING INQUIRY]" in context
    assert "Comment #1 content detailing troubleshooting iteration 1." in context

    # Middle summary notice must exist
    assert "comments summarized for context brevity" in context
    assert "• [#2]" in context

    # Recent exchanges (comments 17-20) must be in full
    assert "[17]" in context
    assert "[20]" in context
    assert "Comment #20 content detailing troubleshooting iteration 20." in context


# --- Defensive JSON Parsing Tests ---

def test_extract_structured_json_clean():
    """Test parsing standard clean JSON string."""
    raw = '{"customer_issue": "Broken button", "actions_taken": ["fixed CSS"], "current_status": "Resolved", "commitments": [], "action_items": [], "sentiment": "positive"}'
    data = extract_structured_json(raw)
    assert data["customer_issue"] == "Broken button"
    assert data["sentiment"] == "positive"


def test_extract_structured_json_markdown_fenced():
    """Test parsing JSON enclosed in markdown code fences."""
    raw = """Here is the structured summary:
```json
{
  "customer_issue": "Gateway Timeout",
  "actions_taken": ["Restarted pod"],
  "current_status": "Investigating",
  "commitments": ["ETA 1 hour"],
  "action_items": ["Check datadog"],
  "sentiment": "urgent",
  "notes": ["VIP account"]
}
```
Hope this helps!"""
    summary = parse_llm_response_to_summary(raw)
    assert summary.customer_issue == "Gateway Timeout"
    assert summary.actions_taken == ["Restarted pod"]
    assert summary.commitments == ["ETA 1 hour"]
    assert summary.sentiment == "urgent"
    assert summary.notes == ["VIP account"]


def test_parse_llm_response_fallback_on_unstructured_text():
    """Test graceful fallback when LLM outputs plain text instead of JSON."""
    raw_text = "The user reported login issue and agent reset the password."
    summary = parse_llm_response_to_summary(raw_text)
    assert isinstance(summary, SummaryStructured)
    assert summary.current_status == "Open"
    assert summary.sentiment == "neutral"


def test_extract_structured_json_empty_raises_error():
    """Test that empty LLM output raises SummarizationError."""
    with pytest.raises(SummarizationError):
        extract_structured_json("")


# --- Formatter Tests ---

def test_internal_note_formatter():
    """Test InternalNoteFormatter produces formatted, scannable markdown."""
    summary = SummaryStructured(
        executive_summary="Customer cannot export billing CSV due to timeout.",
        customer_issue="504 Gateway timeout during CSV transaction export.",
        actions_taken=["Analyzed query execution plan.", "Patched worker timeout."],
        current_status="Patch deployed; awaiting customer verification.",
        commitments=["Update customer by 2:00 PM EST."],
        action_items=["Verify transaction log after customer retry."],
        sentiment="frustrated",
        notes=["Account has 500,000 transaction records."],
    )

    note = InternalNoteFormatter.format(summary)
    assert "### 🤖 AI Ticket Summary" in note
    assert "**Executive Summary:** Customer cannot export billing CSV due to timeout." in note
    assert "**Customer Issue:** 504 Gateway timeout during CSV transaction export." in note
    assert "**Actions Taken / Troubleshooting:**" in note
    assert "- Analyzed query execution plan." in note
    assert "**Commitments / Promised Follow-ups:**" in note
    assert "- ⏳ Update customer by 2:00 PM EST." in note
    assert "**Next Steps / Action Items:**" in note
    assert "- [ ] Verify transaction log after customer retry." in note
    assert "🟠 Frustrated" in note
    assert "**Triage Notes:**" in note
    assert "- Account has 500,000 transaction records." in note


# --- GeminiSummarizer Tests ---

@pytest.mark.asyncio
@respx.mock
async def test_gemini_summarizer_success():
    """Test GeminiSummarizer calling Google Gemini REST API and parsing JSON."""
    settings = Settings(
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_MODEL="gemini-1.5-flash",
    )
    summarizer = GeminiSummarizer(settings=settings)

    mock_llm_json = {
        "customer_issue": "SSO Login Failure",
        "actions_taken": ["Regenerated SAML certificate"],
        "current_status": "Awaiting customer testing",
        "commitments": ["Follow up in 24h"],
        "action_items": ["Monitor Okta logs"],
        "sentiment": "urgent",
    }
    gemini_api_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_llm_json)}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=test-gemini-key"
    ).mock(return_value=httpx.Response(200, json=gemini_api_response))

    summary = await summarizer.summarize_context("Sample context")
    assert summary.customer_issue == "SSO Login Failure"
    assert summary.actions_taken == ["Regenerated SAML certificate"]
    assert summary.commitments == ["Follow up in 24h"]
    assert summary.sentiment == "urgent"


@pytest.mark.asyncio
@respx.mock
async def test_gemini_summarizer_auth_error():
    """Test GeminiSummarizer raises LLMAuthError on 400 invalid API key."""
    settings = Settings(GEMINI_API_KEY="bad-key")
    summarizer = GeminiSummarizer(settings=settings)

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=bad-key"
    ).mock(return_value=httpx.Response(400, json={"error": {"message": "API key not valid"}}))

    with pytest.raises(LLMAuthError):
        await summarizer.summarize_context("Context")


@pytest.mark.asyncio
@respx.mock
async def test_gemini_summarizer_rate_limit_error():
    """Test GeminiSummarizer raises LLMRateLimitError on 429 quota exceeded."""
    settings = Settings(GEMINI_API_KEY="test-key")
    summarizer = GeminiSummarizer(settings=settings)

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=test-key"
    ).mock(return_value=httpx.Response(429, json={"error": {"message": "Quota exceeded"}}))

    with pytest.raises(LLMRateLimitError):
        await summarizer.summarize_context("Context")


# --- GroqSummarizer Tests ---

@pytest.mark.asyncio
@respx.mock
async def test_groq_summarizer_success():
    """Test GroqSummarizer calling Groq OpenAI-compatible Chat Completions endpoint."""
    settings = Settings(
        GROQ_API_KEY="test-groq-key",
        GROQ_MODEL="llama-3.3-70b-versatile",
    )
    summarizer = GroqSummarizer(settings=settings)

    mock_llm_json = {
        "customer_issue": "Unable to connect Slack integration",
        "actions_taken": ["Verified OAuth scope", "Re-authorized bot"],
        "current_status": "Resolved",
        "commitments": [],
        "action_items": ["Close ticket"],
        "sentiment": "positive",
    }
    groq_api_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(mock_llm_json),
                }
            }
        ]
    }

    route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=groq_api_response)
    )

    summary = await summarizer.summarize_context("Context text")
    assert summary.customer_issue == "Unable to connect Slack integration"
    assert summary.actions_taken == ["Verified OAuth scope", "Re-authorized bot"]
    assert summary.sentiment == "positive"
    assert route.called
    assert route.calls.last.request.headers.get("authorization") == "Bearer test-groq-key"


@pytest.mark.asyncio
@respx.mock
async def test_groq_summarizer_auth_error():
    """Test GroqSummarizer raises LLMAuthError on 401 unauthorized."""
    settings = Settings(GROQ_API_KEY="bad-groq-key")
    summarizer = GroqSummarizer(settings=settings)

    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "Invalid API Key"})
    )

    with pytest.raises(LLMAuthError):
        await summarizer.summarize_context("Context text")


# --- Factory Function Tests ---

def test_get_summarizer_factory():
    """Test get_summarizer provider instantiation based on configuration."""
    gemini_settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="key1")
    s1 = get_summarizer(settings=gemini_settings)
    assert isinstance(s1, GeminiSummarizer)

    groq_settings = Settings(LLM_PROVIDER="groq", GROQ_API_KEY="key2")
    s2 = get_summarizer(settings=groq_settings)
    assert isinstance(s2, GroqSummarizer)
