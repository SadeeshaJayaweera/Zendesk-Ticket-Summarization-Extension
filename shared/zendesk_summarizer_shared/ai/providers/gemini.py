"""Google Gemini AI Provider Adapter using Async HTTPX."""

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

logger = logging.getLogger("zendesk_summarizer.ai.gemini")
T = TypeVar("T", bound=BaseModel)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseAIProvider):
    """Adapter for Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-1.5-flash",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(provider_name="gemini", default_model=default_model, timeout=timeout)
        self.api_key = api_key
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client and not self._client.is_closed:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    def _map_http_error(self, status: int, text: str) -> AIProviderError:
        if status in (401, 403):
            return AIProviderAuthError(f"Gemini API key invalid or unauthorized: {text}", provider="gemini")
        elif status == 429:
            return AIProviderRateLimitError(f"Gemini rate limit exceeded: {text}", provider="gemini")
        elif status >= 500:
            return AIProviderError(f"Gemini upstream server error {status}: {text}", provider="gemini", status_code=status, retryable=True)
        return AIProviderError(f"Gemini API error {status}: {text}", provider="gemini", status_code=status)

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Call Gemini REST API and return text response."""
        if not self.api_key:
            raise AIProviderAuthError("Gemini API key is not configured.", provider="gemini")

        target_model = model or self.default_model
        url = f"{GEMINI_API_BASE}/{target_model}:generateContent?key={self.api_key}"

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        client = self._get_client()
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                raise self._map_http_error(resp.status_code, resp.text)

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIProviderError("Gemini returned no candidates (filtered or empty)", provider="gemini")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise AIProviderError("Gemini candidate has no content parts", provider="gemini")

            return parts[0].get("text", "").strip()

        except httpx.TimeoutException:
            raise AIProviderTimeoutError("Gemini request timed out", provider="gemini")
        except httpx.RequestError as exc:
            raise AIProviderError(f"Gemini network error: {exc}", provider="gemini", retryable=True)

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
            raise AIProviderAuthError("Gemini API key is not configured.", provider="gemini")

        target_model = model or self.default_model
        url = f"{GEMINI_API_BASE}/{target_model}:generateContent?key={self.api_key}"

        # Inject JSON instruction into prompt for model reliability
        schema_json = json.dumps(schema_cls.model_json_schema(), indent=2)
        enriched_prompt = (
            f"{prompt}\n\n"
            f"### CRITICAL REQUIREMENT:\n"
            f"Output MUST be valid JSON strictly matching this schema:\n{schema_json}\n"
            f"Do NOT include markdown backticks or commentary outside the JSON."
        )

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": enriched_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        client = self._get_client()
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                raise self._map_http_error(resp.status_code, resp.text)

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIProviderError("Gemini returned no candidates", provider="gemini")

            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed_dict = self.extract_json_from_text(raw_text)

            try:
                return schema_cls.model_validate(parsed_dict)
            except ValidationError as val_err:
                logger.warning("Pydantic validation failure on Gemini response: %s", val_err)
                raise AIProviderError(f"Validation error against schema: {val_err}", provider="gemini", retryable=True)

        except httpx.TimeoutException:
            raise AIProviderTimeoutError("Gemini request timed out", provider="gemini")
        except httpx.RequestError as exc:
            raise AIProviderError(f"Gemini network error: {exc}", provider="gemini", retryable=True)

    async def health_check(self) -> bool:
        """Verify API key works with a lightweight prompt."""
        if not self.api_key:
            return False
        try:
            res = await self.generate_completion(prompt="respond with 'OK'", max_tokens=10)
            return bool(res)
        except Exception:
            return False
