"""Unit tests for Multi-Provider AI Orchestration and Automatic Failover."""

from unittest.mock import AsyncMock, patch
import pytest
from pydantic import BaseModel

from zendesk_summarizer_shared.ai.orchestrator import AIOrchestrator, GenerationResult
from zendesk_summarizer_shared.ai.providers.base import (
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)
from zendesk_summarizer_shared.ai.registry import (
    calculate_cost,
    get_fallback_chain,
)
from zendesk_summarizer_shared.config import Settings


class MockOutputSchema(BaseModel):
    summary: str
    status: str


def test_registry_fallback_chain():
    """Verify fallback chain contains primary and sequential backups."""
    chain = get_fallback_chain("gemini", "gemini-1.5-flash")
    assert len(chain) >= 2
    assert chain[0] == ("gemini", "gemini-1.5-flash")
    providers = [c[0] for c in chain]
    assert "groq" in providers or "openai" in providers


def test_calculate_cost():
    """Verify cost calculation across different models."""
    cost = calculate_cost("gemini-1.5-flash", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0.0
    assert cost < 0.01  # Gemini flash is very cheap

    gpt_cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert gpt_cost > cost  # GPT-4o is more expensive than gemini flash


@pytest.mark.asyncio
async def test_orchestrator_primary_provider_success():
    """Test successful generation on the primary provider without needing fallback."""
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="test-key",
        gemini_model="gemini-1.5-flash",
    )
    orchestrator = AIOrchestrator(settings=settings)

    mock_gemini = AsyncMock()
    mock_gemini.is_configured = True
    mock_gemini.generate_structured.return_value = MockOutputSchema(
        summary="Ticket solved successfully",
        status="solved",
    )
    orchestrator._providers["gemini"] = mock_gemini

    result = await orchestrator.generate_structured_with_fallback(
        prompt="Summarize ticket",
        schema_cls=MockOutputSchema,
        primary_provider="gemini",
    )

    assert isinstance(result, GenerationResult)
    assert result.provider == "gemini"
    assert result.model == "gemini-1.5-flash"
    assert result.output.summary == "Ticket solved successfully"
    assert result.output.status == "solved"
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_orchestrator_fallback_on_rate_limit():
    """Test that when primary provider hits rate limit, fallback provider is executed."""
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="test-key",
        groq_api_key="test-groq-key",
    )
    orchestrator = AIOrchestrator(settings=settings)

    # Primary fails with rate limit
    mock_gemini = AsyncMock()
    mock_gemini.is_configured = True
    mock_gemini.generate_structured.side_effect = AIProviderRateLimitError("Rate limit exceeded")

    # Fallback succeeds
    mock_groq = AsyncMock()
    mock_groq.is_configured = True
    mock_groq.generate_structured.return_value = MockOutputSchema(
        summary="Fallback summary generated",
        status="open",
    )

    orchestrator._providers["gemini"] = mock_gemini
    orchestrator._providers["groq"] = mock_groq

    with patch("zendesk_summarizer_shared.ai.orchestrator.get_fallback_chain") as mock_chain:
        mock_chain.return_value = [
            ("gemini", "gemini-1.5-flash"),
            ("groq", "llama-3.3-70b-versatile"),
        ]
        result = await orchestrator.generate_structured_with_fallback(
            prompt="Summarize ticket",
            schema_cls=MockOutputSchema,
            primary_provider="gemini",
        )

        assert result.provider == "groq"
        assert result.model == "llama-3.3-70b-versatile"
        assert result.output.summary == "Fallback summary generated"
        assert result.attempts >= 2


@pytest.mark.asyncio
async def test_orchestrator_all_providers_fail():
    """Test that if all providers in chain fail, an AIProviderError is raised with telemetry."""
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="test-key",
    )
    orchestrator = AIOrchestrator(settings=settings)

    mock_gemini = AsyncMock()
    mock_gemini.is_configured = True
    mock_gemini.generate_structured.side_effect = AIProviderTimeoutError("Request timed out")

    orchestrator._providers["gemini"] = mock_gemini

    with patch("zendesk_summarizer_shared.ai.orchestrator.get_fallback_chain") as mock_chain:
        mock_chain.return_value = [("gemini", "gemini-1.5-flash")]

        with pytest.raises(AIProviderError) as exc_info:
            await orchestrator.generate_structured_with_fallback(
                prompt="Summarize ticket",
                schema_cls=MockOutputSchema,
                primary_provider="gemini",
            )
        assert "failed" in str(exc_info.value).lower()
