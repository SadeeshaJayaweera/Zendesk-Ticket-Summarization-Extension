"""Model Registry and Token Economics for Multi-Provider AI Architecture.

Maintains metadata, context window limits, pricing, and fallback chains
for Google Gemini, OpenAI, Anthropic Claude, and Groq.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModelMetadata:
    """Metadata describing a supported LLM model."""
    provider: str
    model_id: str
    display_name: str
    context_window_tokens: int
    max_output_tokens: int
    input_cost_per_million: float  # USD
    output_cost_per_million: float  # USD
    supports_structured_json: bool
    is_deprecated: bool = False
    fallback_model_id: Optional[str] = None


# Official Model Registry
MODEL_REGISTRY: Dict[str, ModelMetadata] = {
    # --- Google Gemini ---
    "gemini-1.5-flash": ModelMetadata(
        provider="gemini",
        model_id="gemini-1.5-flash",
        display_name="Google Gemini 1.5 Flash",
        context_window_tokens=1_048_576,
        max_output_tokens=8_192,
        input_cost_per_million=0.075,
        output_cost_per_million=0.30,
        supports_structured_json=True,
        fallback_model_id="llama-3.3-70b-versatile",
    ),
    "gemini-1.5-pro": ModelMetadata(
        provider="gemini",
        model_id="gemini-1.5-pro",
        display_name="Google Gemini 1.5 Pro",
        context_window_tokens=2_097_152,
        max_output_tokens=8_192,
        input_cost_per_million=1.25,
        output_cost_per_million=5.00,
        supports_structured_json=True,
        fallback_model_id="gpt-4o",
    ),
    "gemini-2.0-flash": ModelMetadata(
        provider="gemini",
        model_id="gemini-2.0-flash",
        display_name="Google Gemini 2.0 Flash",
        context_window_tokens=1_048_576,
        max_output_tokens=8_192,
        input_cost_per_million=0.10,
        output_cost_per_million=0.40,
        supports_structured_json=True,
        fallback_model_id="gemini-1.5-flash",
    ),

    # --- Groq (High-Speed Open Weights) ---
    "llama-3.3-70b-versatile": ModelMetadata(
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        display_name="Groq LLaMA 3.3 70B Versatile",
        context_window_tokens=128_000,
        max_output_tokens=8_192,
        input_cost_per_million=0.59,
        output_cost_per_million=0.79,
        supports_structured_json=True,
        fallback_model_id="gpt-4o-mini",
    ),
    "llama-3.1-8b-instant": ModelMetadata(
        provider="groq",
        model_id="llama-3.1-8b-instant",
        display_name="Groq LLaMA 3.1 8B Instant",
        context_window_tokens=128_000,
        max_output_tokens=8_192,
        input_cost_per_million=0.05,
        output_cost_per_million=0.08,
        supports_structured_json=True,
        fallback_model_id="gemini-1.5-flash",
    ),

    # --- OpenAI ---
    "gpt-4o-mini": ModelMetadata(
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="OpenAI GPT-4o Mini",
        context_window_tokens=128_000,
        max_output_tokens=16_384,
        input_cost_per_million=0.15,
        output_cost_per_million=0.60,
        supports_structured_json=True,
        fallback_model_id="claude-3-5-haiku-20241022",
    ),
    "gpt-4o": ModelMetadata(
        provider="openai",
        model_id="gpt-4o",
        display_name="OpenAI GPT-4o",
        context_window_tokens=128_000,
        max_output_tokens=16_384,
        input_cost_per_million=2.50,
        output_cost_per_million=10.00,
        supports_structured_json=True,
        fallback_model_id="claude-3-5-sonnet-20241022",
    ),

    # --- Anthropic Claude ---
    "claude-3-5-haiku-20241022": ModelMetadata(
        provider="anthropic",
        model_id="claude-3-5-haiku-20241022",
        display_name="Anthropic Claude 3.5 Haiku",
        context_window_tokens=200_000,
        max_output_tokens=8_192,
        input_cost_per_million=0.80,
        output_cost_per_million=4.00,
        supports_structured_json=True,
        fallback_model_id="gemini-1.5-flash",
    ),
    "claude-3-5-sonnet-20241022": ModelMetadata(
        provider="anthropic",
        model_id="claude-3-5-sonnet-20241022",
        display_name="Anthropic Claude 3.5 Sonnet",
        context_window_tokens=200_000,
        max_output_tokens=8_192,
        input_cost_per_million=3.00,
        output_cost_per_million=15.00,
        supports_structured_json=True,
        fallback_model_id="gpt-4o",
    ),
}

# Default provider models
DEFAULT_PROVIDER_MODELS: Dict[str, str] = {
    "gemini": "gemini-1.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
}


def get_model_metadata(model_id: str) -> Optional[ModelMetadata]:
    """Retrieve metadata for a model ID."""
    return MODEL_REGISTRY.get(model_id)


def calculate_cost(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Compute estimated cost in USD for a given token usage."""
    meta = get_model_metadata(model_id)
    if not meta:
        # Default conservative estimation ($0.50 / $1.50 per 1M)
        return (prompt_tokens * 0.50 + completion_tokens * 1.50) / 1_000_000

    input_cost = (prompt_tokens * meta.input_cost_per_million) / 1_000_000
    output_cost = (completion_tokens * meta.output_cost_per_million) / 1_000_000
    return round(input_cost + output_cost, 6)


def get_fallback_chain(primary_provider: str, primary_model: Optional[str] = None) -> List[tuple[str, str]]:
    """Determine the ordered sequence of (provider, model) pairs for resilient failover.

    Example chain for primary 'gemini':
    1. (gemini, gemini-1.5-flash)
    2. (groq, llama-3.3-70b-versatile)
    3. (openai, gpt-4o-mini)
    4. (anthropic, claude-3-5-haiku-20241022)
    """
    model = primary_model or DEFAULT_PROVIDER_MODELS.get(primary_provider, "gemini-1.5-flash")
    chain: List[tuple[str, str]] = [(primary_provider, model)]

    # Standard fallback sequence
    priority_providers = ["gemini", "groq", "openai", "anthropic"]
    for p in priority_providers:
        if p != primary_provider:
            m = DEFAULT_PROVIDER_MODELS.get(p)
            if m:
                chain.append((p, m))

    return chain
