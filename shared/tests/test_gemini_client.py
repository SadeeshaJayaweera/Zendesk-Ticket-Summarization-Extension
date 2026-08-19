"""Unit tests for GeminiClient using respx mock."""

import json
import httpx
import pytest
import respx
from zendesk_summarizer_shared.config import Settings
from zendesk_summarizer_shared.gemini_client import (
    GeminiAuthError,
    GeminiClient,
    GeminiRateLimitError,
)


@pytest.fixture
def settings():
    return Settings(
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_MODEL="gemini-1.5-flash",
    )


@pytest.mark.asyncio
@respx.mock
async def test_generate_summary_json_success(settings):
    """Test generating summary with valid JSON returned by Gemini."""
    client = GeminiClient(settings=settings)
    expected_structured = {
        "executive_summary": "Customer unable to update billing information.",
        "customer_issue": "Form submission error on credit card change.",
        "actions_taken": ["Agent verified account billing permissions."],
        "current_status": "Awaiting customer to try alternative browser.",
        "action_items": ["Follow up in 24 hours."],
        "sentiment": "frustrated",
    }

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(expected_structured)}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=test-gemini-key"
    ).mock(return_value=httpx.Response(200, json=mock_gemini_response))

    summary = await client.generate_summary("Summarize this ticket")
    assert summary.executive_summary == "Customer unable to update billing information."
    assert summary.sentiment == "frustrated"
    assert len(summary.actions_taken) == 1
    assert len(summary.action_items) == 1


@pytest.mark.asyncio
@respx.mock
async def test_generate_summary_markdown_fence_stripped(settings):
    """Test that markdown code blocks (```json ... ```) are cleanly parsed."""
    client = GeminiClient(settings=settings)
    raw_payload = """```json
{
  "executive_summary": "Login timeout reported.",
  "customer_issue": "SSO SAML loop",
  "actions_taken": ["Cleared cache"],
  "current_status": "Resolved",
  "action_items": [],
  "sentiment": "neutral"
}
```"""

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": raw_payload}],
                    "role": "model",
                }
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=test-gemini-key"
    ).mock(return_value=httpx.Response(200, json=mock_gemini_response))

    summary = await client.generate_summary("Summarize this ticket")
    assert summary.executive_summary == "Login timeout reported."
    assert summary.customer_issue == "SSO SAML loop"


@pytest.mark.asyncio
@respx.mock
async def test_gemini_auth_error(settings):
    """Test 400 API_KEY_INVALID error."""
    client = GeminiClient(settings=settings)
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=test-gemini-key"
    ).mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}},
        )
    )

    with pytest.raises(GeminiAuthError):
        await client.generate_summary("Prompt")


@pytest.mark.asyncio
@respx.mock
async def test_gemini_rate_limit(settings):
    """Test 429 Rate Limit error."""
    client = GeminiClient(settings=settings)
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=test-gemini-key"
    ).mock(
        return_value=httpx.Response(429, json={"error": {"message": "Resource has been exhausted"}})
    )

    with pytest.raises(GeminiRateLimitError):
        await client.generate_summary("Prompt")
