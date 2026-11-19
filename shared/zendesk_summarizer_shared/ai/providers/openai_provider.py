"""OpenAI and OpenAI-Compatible Provider Adapter using Async HTTPX."""

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

logger = logging.getLogger("zendesk_summarizer.ai.openai")
T = TypeVar("T", bound=BaseModel)

DEFAULT_OPENAI_URL = "https://api.openai.com/v1"


class OpenAIProvider(BaseAIProvider):
    """Adapter for OpenAI and OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_OPENAI_URL,
        default_model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(provider_name="openai", default_model=default_model, timeout=timeout)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client and not self._client.is_closed:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    def _map_http_error(self, status: int, text: str) -> AIProviderError:
        if status in (401, 403):
            return AIProviderAuthError(f"OpenAI authentication failed: {text}", provider="openai")
        elif status == 429:
            return AIProviderRateLimitError(f"OpenAI rate limit hit: {text}", provider="openai")
        elif status >= 500:
            return AIProviderError(f"OpenAI server error {status}: {text}", provider="openai", status_code=status, retryable=True)
        return AIProviderError(f"OpenAI API error {status}: {text}", provider="openai", status_code=status)

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Call OpenAI chat completions API."""
        if not self.api_key:
            raise AIProviderAuthError("OpenAI API key is not configured.", provider="openai")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        try:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code != 200:
                raise self._map_http_error(resp.status_code, resp.text)

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise AIProviderError("OpenAI returned no choices", provider="openai")

            return choices[0].get("message", {}).get("content", "").strip()

        except httpx.TimeoutException:
            raise AIProviderTimeoutError("OpenAI request timed out", provider="openai")
        except httpx.RequestError as exc:
            raise AIProviderError(f"OpenAI network error: {exc}", provider="openai", retryable=True)

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
        if not self.api_key:
            raise AIProviderAuthError("OpenAI API key is not configured.", provider="openai")

        schema_json = json.dumps(schema_cls.model_json_schema(), indent=2)
        sys_instruction = system_prompt or "You are an expert AI support intelligence assistant."
        sys_instruction += f"\n\nCRITICAL: You must return valid JSON strictly adhering to this schema:\n{schema_json}"

        messages = [
            {"role": "system", "content": sys_instruction},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        try:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code != 200:
                raise self._map_http_error(resp.status_code, resp.text)

            data = resp.json()
            raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed_dict = self.extract_json_from_text(raw_text)

            try:
                return schema_cls.model_validate(parsed_dict)
            except ValidationError as val_err:
                raise AIProviderError(f"OpenAI response schema mismatch: {val_err}", provider="openai", retryable=True)

        except httpx.TimeoutException:
            raise AIProviderTimeoutError("OpenAI request timed out", provider="openai")
        except httpx.RequestError as exc:
            raise AIProviderError(f"OpenAI network error: {exc}", provider="openai", retryable=True)

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            res = await self.generate_completion(prompt="OK", max_tokens=5)
            return bool(res)
        except Exception:
            return False
