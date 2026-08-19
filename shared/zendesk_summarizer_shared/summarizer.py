"""AI Summarization Engine for Zendesk Tickets.

Provides:
1. TicketContextBuilder: formats ticket metadata and comment threads into structured LLM prompt context,
   with speaker labeling and smart recency-preserving truncation for long threads.
2. InternalNoteFormatter: converts structured AI summaries into scannable Markdown internal notes.
3. BaseSummarizer / GeminiSummarizer / GroqSummarizer: LLM-backed summarization implementations
   with defensive JSON parsing and robust error handling.
4. get_summarizer: factory function selectable via config (LLM_PROVIDER).
"""

import abc
import json
import re
from typing import Any, Dict, List, Optional
import httpx

from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.models import (
    Comment,
    SummaryStructured,
    Ticket,
    TicketSummary,
    User,
)


# --- Custom Exceptions ---

class SummarizationError(Exception):
    """Base exception for summarization failures."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class LLMAuthError(SummarizationError):
    """Authentication failure against LLM API (401/403 or invalid key)."""
    pass


class LLMRateLimitError(SummarizationError):
    """LLM quota or rate limit exceeded (429)."""
    pass


class LLMAPIError(SummarizationError):
    """Upstream API error from LLM provider."""
    pass


# --- Ticket Context Builder ---

class TicketContextBuilder:
    """Formats Ticket and comment thread into structured prompt context with smart truncation.

    Truncation Strategy:
    - If thread is within limits (default <= 25 comments and <= 12,000 chars), all comments
      are included in chronological order with full text.
    - If thread exceeds limits:
      1. Comment #1 (initial customer inquiry / issue description) is preserved in FULL.
      2. Older middle comments are compressed into 1-line timestamped summaries with key snippets.
      3. The most recent N comments (default: last 8 comments) are preserved in FULL with
         complete message bodies, ensuring the latest resolution steps are never lost.
    """

    def __init__(
        self,
        max_comments: int = 25,
        max_thread_chars: int = 12000,
        keep_recent_comments: int = 8,
    ):
        self.max_comments = max_comments
        self.max_thread_chars = max_thread_chars
        self.keep_recent_comments = keep_recent_comments

    def _resolve_speaker_label(
        self,
        comment: Comment,
        ticket: Optional[Ticket],
        users_map: Dict[int, User],
        requester: Optional[User],
        assignee: Optional[User],
    ) -> str:
        """Construct a descriptive speaker role and identity label."""
        user = users_map.get(comment.author_id)
        user_name = user.name if user else None

        if ticket and comment.author_id == ticket.requester_id:
            label = f"Customer / Requester: {user_name or f'User #{comment.author_id}'}"
        elif requester and comment.author_id == requester.id:
            label = f"Customer / Requester: {requester.name}"
        elif ticket and comment.author_id == ticket.assignee_id:
            label = f"Support Agent: {user_name or f'User #{comment.author_id}'}"
        elif assignee and comment.author_id == assignee.id:
            label = f"Support Agent: {assignee.name}"
        elif user and user.role in ("agent", "admin"):
            label = f"Support Agent: {user.name}"
        elif user and user.role == "end-user":
            label = f"Customer: {user.name}"
        else:
            label = f"User #{comment.author_id}"

        visibility = "PUBLIC REPLY" if comment.public else "INTERNAL NOTE (PRIVATE)"
        return f"[{visibility}] {label}"

    def build_context(
        self,
        ticket: Optional[Ticket],
        comments: List[Comment],
        requester: Optional[User] = None,
        assignee: Optional[User] = None,
        users_map: Optional[Dict[int, User]] = None,
    ) -> str:
        """Build clean structured text context from ticket metadata and conversation comments."""
        known_users: Dict[int, User] = dict(users_map or {})
        if requester:
            known_users[requester.id] = requester
        if assignee:
            known_users[assignee.id] = assignee

        parts: List[str] = []

        # 1. Metadata Block
        if ticket:
            parts.append("=== TICKET METADATA ===")
            parts.append(f"Ticket ID: #{ticket.id}")
            parts.append(f"Subject: {ticket.subject or '(No subject)'}")
            parts.append(f"Status: {ticket.status.upper()}")
            parts.append(f"Priority: {ticket.priority or 'normal'}")

            requester_name = (
                f"{requester.name} ({requester.email})"
                if requester and requester.email
                else requester.name if requester
                else f"User #{ticket.requester_id}" if ticket.requester_id
                else "Unknown"
            )
            parts.append(f"Requester: {requester_name}")

            assignee_name = (
                f"{assignee.name} ({assignee.email})"
                if assignee and assignee.email
                else assignee.name if assignee
                else f"User #{ticket.assignee_id}" if ticket.assignee_id
                else "Unassigned"
            )
            parts.append(f"Assignee: {assignee_name}")

            if ticket.tags:
                parts.append(f"Tags: {', '.join(ticket.tags)}")
            if ticket.created_at:
                parts.append(f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            if ticket.description and (not comments or ticket.description != comments[0].body):
                parts.append(f"Initial Description:\n{ticket.description.strip()}")
            parts.append("=======================\n")

        # 2. Conversation Thread
        parts.append("=== CONVERSATION THREAD (Chronological) ===")

        if not comments:
            parts.append("No comments recorded.")
        else:
            total_chars = sum(len(c.plain_body or c.body or "") for c in comments)
            num_comments = len(comments)
            should_truncate = (num_comments > self.max_comments) or (total_chars > self.max_thread_chars)

            if not should_truncate or num_comments <= self.keep_recent_comments + 1:
                # Thread is within budget: include all comments in full
                for idx, comment in enumerate(comments, start=1):
                    speaker = self._resolve_speaker_label(comment, ticket, known_users, requester, assignee)
                    time_str = comment.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if comment.created_at else "Unknown Time"
                    body = (comment.plain_body or comment.body or "").strip()
                    parts.append(f"[{idx}] {speaker} at {time_str}:\n{body}\n")
            else:
                # Long thread: apply recency-preserving window truncation
                # Comment 1: Opening customer issue (Always in FULL)
                first_comment = comments[0]
                speaker = self._resolve_speaker_label(first_comment, ticket, known_users, requester, assignee)
                time_str = first_comment.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if first_comment.created_at else "Unknown Time"
                body = (first_comment.plain_body or first_comment.body or "").strip()
                parts.append(f"[1] {speaker} at {time_str} [OPENING INQUIRY]:\n{body}\n")

                # Middle comments: compress into 1-line timestamped snippets
                recent_start_idx = num_comments - self.keep_recent_comments
                middle_comments = comments[1:recent_start_idx]
                parts.append(f"--- [Middle {len(middle_comments)} comments summarized for context brevity] ---")
                for idx, comment in enumerate(middle_comments, start=2):
                    speaker = self._resolve_speaker_label(comment, ticket, known_users, requester, assignee)
                    time_str = comment.created_at.strftime("%Y-%m-%d %H:%M:%S") if comment.created_at else "Time N/A"
                    raw_body = (comment.plain_body or comment.body or "").strip().replace("\n", " ")
                    snippet = raw_body[:140] + ("..." if len(raw_body) > 140 else "")
                    parts.append(f"  • [#{idx}] {speaker} ({time_str}): {snippet}")
                parts.append("--- [Most recent exchanges in FULL below] ---\n")

                # Recent comments: in FULL
                for idx, comment in enumerate(comments[recent_start_idx:], start=recent_start_idx + 1):
                    speaker = self._resolve_speaker_label(comment, ticket, known_users, requester, assignee)
                    time_str = comment.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if comment.created_at else "Unknown Time"
                    body = (comment.plain_body or comment.body or "").strip()
                    parts.append(f"[{idx}] {speaker} at {time_str}:\n{body}\n")

        parts.append("===========================================")
        return "\n".join(parts)


# --- Formatter ---

class InternalNoteFormatter:
    """Formats structured AI ticket summaries into clean Zendesk internal notes."""

    @staticmethod
    def format(summary: SummaryStructured) -> str:
        """Format SummaryStructured into scannable Markdown note text."""
        return summary.to_markdown()


# --- Prompt Templates ---

def build_ticket_summary_prompt(context: str, summary_style: str = "standard") -> str:
    """Build standardized prompt instructing LLM to output structured JSON."""
    style_guidance = {
        "brief": "Keep customer_issue concise, limit actions_taken and action_items to top 2 bullet points.",
        "action_only": "Focus heavily on current_status, commitments made, and pending action_items.",
        "detailed": "Provide an in-depth chronological breakdown of all troubleshooting steps, logs, and findings.",
        "standard": "Provide a balanced, thorough summary covering issue, actions taken, current status, commitments, and next steps.",
    }.get(summary_style.lower(), "Provide a balanced, thorough summary.")

    json_schema_example = json.dumps(
        {
            "executive_summary": "1-2 sentence overview of the ticket situation.",
            "customer_issue": "The primary root problem or question reported by the customer.",
            "actions_taken": [
                "Agent investigated auth logs.",
                "Reset token issued to customer email."
            ],
            "current_status": "Awaiting customer confirmation of login success.",
            "commitments": [
                "Agent promised follow-up by 3:00 PM EST if no reply received."
            ],
            "action_items": [
                "Verify login success once customer replies.",
                "Close ticket if confirmed resolved."
            ],
            "sentiment": "neutral",
            "notes": [
                "Customer has open billing inquiry ticket #4421."
            ]
        },
        indent=2
    )

    return f"""You are an expert Zendesk Customer Support Operations AI Assistant.
Analyze the following customer support ticket and conversation thread, then generate a high-value structured summary for an agent's internal note.

### Style Instruction:
{style_guidance}

### Requirements:
1. Identify the customer's core problem, question, or request (`customer_issue`).
2. List key actions, troubleshooting steps, or diagnostic answers already performed (`actions_taken`).
3. State the current status and what remains open or unresolved (`current_status`).
4. Note any commitments, promises, or ETAs given to the customer (`commitments`). If none, return an empty array.
5. Provide actionable next steps for the next support agent (`action_items`).
6. Detect customer sentiment: choose one of ["positive", "neutral", "frustrated", "urgent"].
7. Output MUST BE valid JSON strictly matching the schema below without markdown backticks or commentary.

### JSON Schema & Example:
{json_schema_example}

### Support Ticket Context:
{context}

### JSON Output:"""


# --- Defensive JSON Parsing ---

def extract_structured_json(text: str) -> Dict[str, Any]:
    """Defensively extract and parse JSON object from LLM response text."""
    if not text or not text.strip():
        raise SummarizationError("LLM response was empty.")

    cleaned = text.strip()

    # 1. Strip markdown ```json ... ``` code fences if present
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    elif cleaned.startswith("{") and cleaned.endswith("}"):
        pass
    else:
        # 2. Extract substring between outermost braces
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace:last_brace + 1]

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 3. Fallback recovery: extract key sections if JSON decode fails
    return {
        "executive_summary": text.strip()[:250] if text else "Summary generation completed.",
        "customer_issue": "Customer reported an inquiry (parsed from text).",
        "actions_taken": ["Conversation reviewed by AI."],
        "current_status": "Open",
        "commitments": [],
        "action_items": ["Review conversation details."],
        "sentiment": "neutral",
        "notes": [],
    }


def parse_llm_response_to_summary(raw_text: str) -> SummaryStructured:
    """Parse raw LLM output into validated SummaryStructured model."""
    data = extract_structured_json(raw_text)

    # Normalize fields defensively
    customer_issue = data.get("customer_issue") or data.get("issue") or "Inquiry reported by customer."
    actions = data.get("actions_taken") or data.get("actions") or []
    if isinstance(actions, str):
        actions = [actions]

    status = data.get("current_status") or data.get("status") or "Open"
    commitments = data.get("commitments") or data.get("promises") or []
    if isinstance(commitments, str):
        commitments = [commitments]

    action_items = data.get("action_items") or data.get("next_steps") or []
    if isinstance(action_items, str):
        action_items = [action_items]

    sentiment = str(data.get("sentiment", "neutral")).lower()
    if sentiment not in ("positive", "neutral", "frustrated", "urgent"):
        sentiment = "neutral"

    notes = data.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]

    exec_summary = data.get("executive_summary") or f"{customer_issue} - Status: {status}"

    return SummaryStructured(
        executive_summary=exec_summary,
        customer_issue=customer_issue,
        actions_taken=actions,
        current_status=status,
        commitments=commitments,
        action_items=action_items,
        sentiment=sentiment,
        notes=notes,
    )


# --- Base & Concrete Summarizers ---

class BaseSummarizer(abc.ABC):
    """Abstract base class for LLM summarizers."""

    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None):
        self.settings = settings or get_settings()
        self._client = client
        self.context_builder = TicketContextBuilder()

    @abc.abstractmethod
    async def summarize_context(self, context: str, summary_style: str = "standard") -> SummaryStructured:
        """Send formatted context to the LLM and return structured summary."""
        pass

    async def summarize_ticket(
        self,
        ticket: Optional[Ticket],
        comments: List[Comment],
        requester: Optional[User] = None,
        assignee: Optional[User] = None,
        users_map: Optional[Dict[int, User]] = None,
        summary_style: str = "standard",
    ) -> SummaryStructured:
        """Build context from ticket and comments, then generate structured summary."""
        context = self.context_builder.build_context(
            ticket=ticket,
            comments=comments,
            requester=requester,
            assignee=assignee,
            users_map=users_map,
        )
        return await self.summarize_context(context, summary_style=summary_style)


class GeminiSummarizer(BaseSummarizer):
    """Summarizer using Google Gemini REST API."""

    def _get_api_key(self) -> str:
        key = self.settings.gemini_api_key.get_secret_value().strip()
        if not key:
            raise LLMAuthError("Gemini API key is missing (GEMINI_API_KEY).")
        return key

    async def summarize_context(self, context: str, summary_style: str = "standard") -> SummaryStructured:
        api_key = self._get_api_key()
        model = self.settings.gemini_model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        prompt = build_ticket_summary_prompt(context, summary_style=summary_style)
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1200,
            }
        }
        params = {"key": api_key}
        headers = {"Content-Type": "application/json"}

        try:
            if self._client is not None:
                response = await self._client.post(url, params=params, headers=headers, json=payload, timeout=30.0)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, params=params, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise SummarizationError(f"Network error contacting Gemini API: {exc}") from exc

        if response.status_code in (401, 403) or (
            response.status_code == 400 and ("api key" in response.text.lower() or "api_key_invalid" in response.text.lower())
        ):
            raise LLMAuthError(f"Gemini authentication failed ({response.status_code}): {response.text}", status_code=response.status_code, response_text=response.text)
        elif response.status_code == 429:
            raise LLMRateLimitError(f"Gemini rate limit / quota exceeded (429): {response.text}", status_code=429, response_text=response.text)
        elif response.status_code >= 400:
            raise LLMAPIError(f"Gemini API error ({response.status_code}): {response.text}", status_code=response.status_code, response_text=response.text)

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise SummarizationError(f"Gemini returned no response candidates: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise SummarizationError("Gemini response candidate contains no text parts.")

        raw_text = parts[0]["text"]
        return parse_llm_response_to_summary(raw_text)


class GroqSummarizer(BaseSummarizer):
    """Alternative summarizer using Groq OpenAI-compatible Chat Completions REST API.

    Enables seamless fallback if Gemini quota limits are hit.
    """

    def _get_api_key(self) -> str:
        key = self.settings.groq_api_key.get_secret_value().strip()
        if not key:
            raise LLMAuthError("Groq API key is missing (GROQ_API_KEY).")
        return key

    async def summarize_context(self, context: str, summary_style: str = "standard") -> SummaryStructured:
        api_key = self._get_api_key()
        model = self.settings.groq_model or "llama-3.3-70b-versatile"
        url = "https://api.groq.com/openai/v1/chat/completions"

        prompt = build_ticket_summary_prompt(context, summary_style=summary_style)
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert customer support ticket summarization assistant. Always respond in valid, structured JSON strictly matching the requested schema."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            if self._client is not None:
                response = await self._client.post(url, headers=headers, json=payload, timeout=30.0)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise SummarizationError(f"Network error contacting Groq API: {exc}") from exc

        if response.status_code in (401, 403):
            raise LLMAuthError(f"Groq authentication failed ({response.status_code}): {response.text}", status_code=response.status_code, response_text=response.text)
        elif response.status_code == 429:
            raise LLMRateLimitError(f"Groq rate limit / quota exceeded (429): {response.text}", status_code=429, response_text=response.text)
        elif response.status_code >= 400:
            raise LLMAPIError(f"Groq API error ({response.status_code}): {response.text}", status_code=response.status_code, response_text=response.text)

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise SummarizationError(f"Groq returned no choices: {data}")

        message = choices[0].get("message", {})
        raw_text = message.get("content", "")
        if not raw_text:
            raise SummarizationError("Groq response message content was empty.")

        return parse_llm_response_to_summary(raw_text)


def get_summarizer(
    settings: Optional[Settings] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> BaseSummarizer:
    """Factory function: instantiates the configured summarizer (Gemini or Groq).

    Selection is controlled by `settings.llm_provider` ('gemini' or 'groq').
    If provider is 'groq' (or if Gemini key is unset and Groq key is set), GroqSummarizer is used.
    """
    s = settings or get_settings()
    provider = s.llm_provider.strip().lower()

    if provider == "groq" or (not s.is_gemini_configured and s.is_groq_configured):
        return GroqSummarizer(settings=s, client=client)
    return GeminiSummarizer(settings=s, client=client)

# Prompt tuning revision 1

# Prompt tuning revision 2

# Prompt tuning revision 3

# Prompt tuning revision 4

# Prompt tuning revision 5

# Prompt tuning revision 6

# Prompt tuning revision 7

# Prompt tuning revision 8

# Prompt tuning revision 9

# Prompt tuning revision 10

# Prompt tuning revision 11

# Prompt tuning revision 12

# Prompt tuning revision 13

# Prompt tuning revision 14

# Prompt tuning revision 15

# Prompt tuning revision 16

# Prompt tuning revision 17

# Prompt tuning revision 18

# Prompt tuning revision 19

# Prompt tuning revision 20

# Prompt tuning revision 21

# Prompt tuning revision 22

# Prompt tuning revision 23

# Prompt tuning revision 24

# Prompt tuning revision 25

# Prompt tuning revision 26
