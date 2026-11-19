"""Abstract Base Provider for Multi-Provider AI Architecture."""

from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

logger = logging.getLogger("zendesk_summarizer.ai.provider")

T = TypeVar("T", bound=BaseModel)


class AIProviderError(Exception):
    """Base exception for all AI provider errors."""
    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: Optional[int] = None,
        retryable: bool = False,
    ):
        super().__init__(f"[{provider.upper()}] {message}")
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class AIProviderAuthError(AIProviderError):
    """Authentication or authorization failure (401/403 or invalid API key)."""
    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, provider=provider, status_code=401, retryable=False)


class AIProviderRateLimitError(AIProviderError):
    """Quota or rate limit exceeded (429)."""
    def __init__(self, message: str, provider: str = "unknown", retry_after: int = 60):
        super().__init__(message, provider=provider, status_code=429, retryable=True)
        self.retry_after = retry_after


class AIProviderTimeoutError(AIProviderError):
    """Request timeout to AI provider."""
    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, provider=provider, status_code=504, retryable=True)


class BaseAIProvider(ABC):
    """Abstract interface that all LLM provider adapters must implement."""

    def __init__(self, provider_name: str, default_model: str, timeout: float = 30.0):
        self.provider_name = provider_name
        self.default_model = default_model
        self.timeout = timeout

    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Generate unstructured raw text response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema_cls: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> T:
        """Generate structured response validated against a Pydantic schema."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Validate connectivity and API credentials."""
        pass

    def extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Robustly extract and parse a JSON dictionary from LLM response text."""
        if not text or not text.strip():
            raise AIProviderError("LLM returned empty response", provider=self.provider_name)

        cleaned = text.strip()

        # 1. Check for markdown code fences: ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 2. Extract outermost matching curly braces
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = cleaned[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 3. Direct parse attempt
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON from %s response: %s", self.provider_name, exc)
            raise AIProviderError(
                f"Could not parse valid JSON from model response: {exc}",
                provider=self.provider_name,
                retryable=True,
            )
