"""AI Orchestration Engine with Multi-Provider Fallback and Cost Tracking.

Orchestrates calls across Google Gemini, OpenAI, Anthropic Claude, and Groq,
with automatic failover, exponential backoff, token budgeting, and cost metrics.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

from zendesk_summarizer_shared.ai.providers.anthropic_provider import AnthropicProvider
from zendesk_summarizer_shared.ai.providers.base import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    BaseAIProvider,
)
from zendesk_summarizer_shared.ai.providers.gemini import GeminiProvider
from zendesk_summarizer_shared.ai.providers.groq_provider import GroqProvider
from zendesk_summarizer_shared.ai.providers.openai_provider import OpenAIProvider
from zendesk_summarizer_shared.ai.registry import (
    calculate_cost,
    get_fallback_chain,
    get_model_metadata,
)
from zendesk_summarizer_shared.config import Settings, get_settings

logger = logging.getLogger("zendesk_summarizer.ai.orchestrator")
T = TypeVar("T", bound=BaseModel)


class GenerationResult:
    """Wrapper holding model output alongside generation telemetry."""
    def __init__(
        self,
        output: Any,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float,
        latency_seconds: float,
        attempts: int,
    ):
        self.output = output
        self.provider = provider
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.latency_seconds = latency_seconds
        self.attempts = attempts


class AIOrchestrator:
    """Multi-provider AI orchestration engine with automated fallback."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        max_retries_per_provider: int = 2,
    ):
        self.settings = settings or get_settings()
        self.max_retries_per_provider = max_retries_per_provider
        self._providers: Dict[str, BaseAIProvider] = {}
        self._init_providers()

    def _init_providers(self):
        """Instantiate configured provider adapters."""
        # Google Gemini
        gemini_key = getattr(self.settings, "gemini_api_key", None)
        gemini_model = getattr(self.settings, "gemini_model", "gemini-1.5-flash")
        self._providers["gemini"] = GeminiProvider(
            api_key=gemini_key,
            default_model=gemini_model,
        )

        # Groq
        groq_key = getattr(self.settings, "groq_api_key", None)
        groq_model = getattr(self.settings, "groq_model", "llama-3.3-70b-versatile")
        self._providers["groq"] = GroqProvider(
            api_key=groq_key,
            default_model=groq_model,
        )

        # OpenAI
        openai_key = getattr(self.settings, "openai_api_key", None)
        openai_model = getattr(self.settings, "openai_model", "gpt-4o-mini")
        self._providers["openai"] = OpenAIProvider(
            api_key=openai_key,
            default_model=openai_model,
        )

        # Anthropic Claude
        anthropic_key = getattr(self.settings, "anthropic_api_key", None)
        anthropic_model = getattr(self.settings, "anthropic_model", "claude-3-5-haiku-20241022")
        self._providers["anthropic"] = AnthropicProvider(
            api_key=anthropic_key,
            default_model=anthropic_model,
        )

    def get_provider(self, name: str) -> Optional[BaseAIProvider]:
        """Fetch provider adapter by name."""
        return self._providers.get(name.lower())

    async def generate_structured_with_fallback(
        self,
        prompt: str,
        schema_cls: Type[T],
        system_prompt: Optional[str] = None,
        primary_provider: Optional[str] = None,
        primary_model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> GenerationResult:
        """Execute structured generation with automated multi-provider failover."""
        provider_name = primary_provider or self.settings.llm_provider or "gemini"
        chain = get_fallback_chain(provider_name, primary_model)

        errors_encountered: List[str] = []
        total_attempts = 0
        start_time = time.time()

        for prov_id, model_id in chain:
            provider = self.get_provider(prov_id)
            if not provider:
                continue

            for attempt in range(1, self.max_retries_per_provider + 1):
                total_attempts += 1
                try:
                    logger.info(
                        "Attempting structured AI generation via provider=%s model=%s (attempt %d)",
                        prov_id,
                        model_id,
                        attempt,
                    )
                    parsed_output = await provider.generate_structured(
                        prompt=prompt,
                        schema_cls=schema_cls,
                        system_prompt=system_prompt,
                        model=model_id,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                    latency = time.time() - start_time
                    # Token estimation
                    prompt_tokens = len(prompt) // 4
                    completion_tokens = 500  # Default structured response estimate
                    cost = calculate_cost(model_id, prompt_tokens, completion_tokens)

                    logger.info(
                        "AI Generation succeeded via provider=%s model=%s (latency=%.2fs, cost=$%.6f)",
                        prov_id,
                        model_id,
                        latency,
                        cost,
                    )

                    return GenerationResult(
                        output=parsed_output,
                        provider=prov_id,
                        model=model_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        estimated_cost_usd=cost,
                        latency_seconds=round(latency, 3),
                        attempts=total_attempts,
                    )

                except AIProviderAuthError as auth_err:
                    msg = f"Auth error on {prov_id}: {auth_err}"
                    logger.warning(msg)
                    errors_encountered.append(msg)
                    # Non-retryable on same provider, immediately try next provider
                    break

                except (AIProviderRateLimitError, AIProviderTimeoutError, AIProviderError) as exc:
                    msg = f"Error on {prov_id} (attempt {attempt}): {exc}"
                    logger.warning(msg)
                    errors_encountered.append(msg)
                    if attempt < self.max_retries_per_provider and exc.retryable:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        await asyncio.sleep(backoff)
                    else:
                        break  # Move to next provider in fallback chain

        all_errs = "; ".join(errors_encountered)
        raise AIProviderError(
            f"All AI providers in fallback chain failed. Errors: {all_errs}",
            provider="orchestrator",
        )
