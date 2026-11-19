"""Anthropic Claude Provider Adapter using Async HTTPX."""

import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from zendesk_summarizer_shared.ai.providers.base import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    BaseAIProvider,
)

logger = logging.getLogger("zendesk_summarizer.ai.anthropic")
T = TypeVar("T", bound=BaseModel)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseAIProvider):
    """Adapter for Anthropic Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "claude-3-5-haiku-20241022",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(provider_name="anthropic", default_model=default_model, timeout=timeout)
        self.api_key = api_key
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client and not self._client.is_closed:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    def _map_http_error(self, status: int, text: str) -> AIProviderError:
        if status in (401, 403):
            return AIProviderAuthError(f"Anthropic API key unauthorized: {text}", provider="anthropic")
        elif status == 429:
            return AIProviderRateLimitError(f"Anthropic rate limit exceeded: {text}", provider="anthropic")
        elif status >= 500:
            return AIProviderError(f"Anthropic server error {status}: {text}", provider="anthropic", status_code=status, retryable=True)
        return AIProviderError(f"Anthropic API error {status}: {text}", provider="anthropic", status_code=status)

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Call Anthropic Claude messages API."""
        if not self.api_key:
            raise AIProviderAuthError("Anthropic API key is not configured.", provider="anthropic")

        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        client = self._get_client()
        try:
            resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                raise self._map_http_error(resp.status_code, resp.text)

            data = resp.json()
            content = data.get("content", [])
            if not content:
                raise AIProviderError("Anthropic returned empty content", provider="anthropic")

            return content[0].get("text", "").strip()

        except httpx.TimeoutException:
            raise AIProviderTimeoutError("Anthropic request timed out", provider="anthropic")
        except httpx.RequestError as exc:
            raise AIProviderError(f"Anthropic network error: {exc}", provider="anthropic", retryable=True)

    async def generate_structured(
        self,
        prompt: str,
        schema_cls: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> T:
        """Generate structured JSON and parse into Pydantic model."""
        if not self.api_key:
            raise AIProviderAuthError("Anthropic API key is not configured.", provider="anthropic")

        schema_json = json.dumps(schema_cls.model_json_schema(), indent=2)
        system_instruction = system_prompt or "You are an expert AI customer support assistant."
        system_instruction += (
            f"\n\nOUTPUT FORMAT SPECIFICATION:\n"
            f"You MUST output valid, parseable JSON strictly complying with this schema:\n{schema_json}\n"
            f"Output JSON ONLY. Do not write markdown tags or conversational prefix/suffix."
        )

        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_instruction,
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        client = self._get_client()
        try:
            resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                raise self._map_http_error(resp.status_code, resp.text)

            data = resp.json()
            raw_text = data.get("content", [{}])[0].get("text", "")
            parsed_dict = self.extract_json_from_text(raw_text)

            try:
                return schema_cls.model_validate(parsed_dict)
            except ValidationError as val_err:
                raise AIProviderError(f"Anthropic response schema mismatch: {val_err}", provider="anthropic", retryable=True)

        except httpx.TimeoutException:
            raise AIProviderTimeoutError("Anthropic request timed out", provider="anthropic")
        except httpx.RequestError as exc:
            raise AIProviderError(f"Anthropic network error: {exc}", provider="anthropic", retryable=True)

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            res = await self.generate_completion(prompt="respond with 'OK'", max_tokens=5)
            return bool(res)
        except Exception:
            return False
