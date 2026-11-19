"""Groq AI Provider Adapter using Async HTTPX."""

from typing import Optional
import httpx
from zendesk_summarizer_shared.ai.providers.openai_provider import OpenAIProvider

GROQ_API_URL = "https://api.groq.com/openai/v1"


class GroqProvider(OpenAIProvider):
    """Adapter for Groq Cloud API, subclassing OpenAIProvider for high-speed inference."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "llama-3.3-70b-versatile",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            api_key=api_key,
            base_url=GROQ_API_URL,
            default_model=default_model,
            timeout=timeout,
            client=client,
        )
        self.provider_name = "groq"
