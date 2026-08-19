"""Asynchronous Google Gemini AI Client for Zendesk Ticket Summarization."""

import json
import re
from typing import Any, Dict, Optional
import httpx
from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.models import SummaryStructured


class GeminiAPIError(Exception):
    """Base exception for Gemini API calls."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class GeminiAuthError(GeminiAPIError):
    """Gemini API authentication failure (400/403 with invalid API key)."""
    pass


class GeminiRateLimitError(GeminiAPIError):
    """Gemini API quota or rate limit exceeded (429)."""
    pass


class GeminiClient:
    """Client for generating AI summaries using Google Gemini REST API."""

    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None):
        self.settings = settings or get_settings()
        self._client = client

    def _get_api_key(self) -> str:
        """Retrieve the configured Gemini API key."""
        key = self.settings.gemini_api_key.get_secret_value().strip()
        if not key:
            raise GeminiAuthError("Gemini API key is not configured in settings (GEMINI_API_KEY).")
        return key

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON object from Gemini response text, handling code blocks."""
        cleaned = text.strip()
        
        # Strip markdown ```json ... ``` or ``` ... ``` code fences
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        elif cleaned.startswith("{") and cleaned.endswith("}"):
            pass
        else:
            # Look for outer-most braces
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace:last_brace + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Fallback structure if LLM returned free-form text instead of valid JSON
            return {
                "executive_summary": text.strip()[:300] if text else "Summary generation completed.",
                "customer_issue": "Customer reported an inquiry.",
                "actions_taken": ["Conversation reviewed by AI."],
                "current_status": "Open",
                "action_items": ["Review full ticket details."],
                "sentiment": "neutral",
            }

    async def generate_summary(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 1000,
    ) -> SummaryStructured:
        """Call Gemini generateContent and parse the structured summary."""
        api_key = self._get_api_key()
        model = self.settings.gemini_model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            }
        }
        params = {"key": api_key}
        headers = {"Content-Type": "application/json"}

        try:
            if self._client is not None:
                response = await self._client.post(
                    url,
                    params=params,
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url,
                        params=params,
                        headers=headers,
                        json=payload,
                    )
        except httpx.RequestError as exc:
            raise GeminiAPIError(f"Network error contacting Gemini API: {exc}")

        if response.status_code in (401, 403) or (
            response.status_code == 400 and ("api key" in response.text.lower() or "api_key_invalid" in response.text.lower())
        ):
            raise GeminiAuthError(
                f"Gemini API authentication failed ({response.status_code}): {response.text}",
                status_code=response.status_code,
                response_text=response.text,
            )
        elif response.status_code == 429:
            raise GeminiRateLimitError(
                f"Gemini API rate limit / quota exceeded (429): {response.text}",
                status_code=429,
                response_text=response.text,
            )
        elif response.status_code >= 400:
            raise GeminiAPIError(
                f"Gemini API error ({response.status_code}): {response.text}",
                status_code=response.status_code,
                response_text=response.text,
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiAPIError(
                f"Gemini API returned no candidates in response: {data}",
                status_code=response.status_code,
                response_text=response.text,
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise GeminiAPIError("Gemini response candidate contains no text parts.")

        raw_text = parts[0]["text"]
        parsed_dict = self._extract_json_from_text(raw_text)

        # Validate with Pydantic model
        try:
            return SummaryStructured.model_validate(parsed_dict)
        except Exception:
            # Fallback if structure fields are missing
            return SummaryStructured(
                executive_summary=parsed_dict.get("executive_summary", raw_text[:200]),
                customer_issue=parsed_dict.get("customer_issue", "Support inquiry"),
                actions_taken=parsed_dict.get("actions_taken", []),
                current_status=parsed_dict.get("current_status", "In Progress"),
                action_items=parsed_dict.get("action_items", []),
                sentiment=parsed_dict.get("sentiment", "neutral"),
            )
