"""Zendesk Summarizer Shared Package.

Provides shared configuration, Zendesk client, Gemini AI client, prompt templates,
and unified business logic for both the FastAPI backend service and the MCP server.
"""

from zendesk_summarizer_shared.audit_logger import AuditLogger, get_audit_logger
from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.draft_store import DraftStore, get_draft_store
from zendesk_summarizer_shared.gemini_client import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiClient,
    GeminiRateLimitError,
)
from zendesk_summarizer_shared.metrics import MetricsCollector, get_metrics_collector
from zendesk_summarizer_shared.models import (
    Attachment,
    Comment,
    DirectSummarizeRequest,
    PendingDraft,
    PendingDraftResponse,
    PostNoteRequest,
    PostNoteResponse,
    SummarizeRequest,
    SummarizeResponse,
    SummaryStructured,
    Ticket,
    TicketCommentsResponse,
    TicketDetailResponse,
    TicketHistoryResponse,
    TicketHistorySummaryItem,
    TicketResponse,
    TicketSummary,
    User,
    UserResponse,
    WebhookTicketPayload,
    ZendeskAttachment,
    ZendeskComment,
    ZendeskTicket,
    ZendeskUser,
)
from zendesk_summarizer_shared.prompts import (
    build_raw_text_prompt,
    build_summarization_prompt,
    format_conversation_transcript,
)
from zendesk_summarizer_shared.rate_limiter import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    get_rate_limiter,
)
from zendesk_summarizer_shared.security import (
    WebhookVerificationError,
    compute_zendesk_webhook_signature,
    verify_zendesk_webhook_signature,
)
from zendesk_summarizer_shared.service import TicketSummarizerService
from zendesk_summarizer_shared.summarizer import (
    BaseSummarizer,
    GeminiSummarizer,
    GroqSummarizer,
    InternalNoteFormatter,
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    SummarizationError,

    TicketContextBuilder,
    get_summarizer,
)
from zendesk_summarizer_shared.zendesk_client import (
    ZendeskAPIError,
    ZendeskAuthError,
    ZendeskClient,
    ZendeskNotFoundError,
    ZendeskRateLimitError,
    ZendeskValidationError,
)


__all__ = [
    "Settings",
    "get_settings",
    "ZendeskClient",
    "GeminiClient",
    "TicketSummarizerService",
    "TicketContextBuilder",
    "InternalNoteFormatter",
    "BaseSummarizer",
    "GeminiSummarizer",
    "GroqSummarizer",
    "get_summarizer",
    "SummarizationError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMAPIError",
    "Ticket",
    "Comment",
    "User",
    "Attachment",
    "ZendeskTicket",
    "ZendeskComment",
    "ZendeskUser",
    "ZendeskAttachment",
    "UserResponse",
    "TicketResponse",
    "TicketCommentsResponse",
    "TicketDetailResponse",
    "SummaryStructured",
    "TicketSummary",
    "SummarizeRequest",
    "DirectSummarizeRequest",
    "SummarizeResponse",
    "PostNoteRequest",
    "PostNoteResponse",
    "build_summarization_prompt",
    "build_raw_text_prompt",
    "format_conversation_transcript",
    "ZendeskAPIError",
    "ZendeskAuthError",
    "ZendeskNotFoundError",
    "ZendeskRateLimitError",
    "ZendeskValidationError",
    "DraftStore",
    "get_draft_store",
    "PendingDraft",
    "PendingDraftResponse",
    "TicketHistoryResponse",
    "TicketHistorySummaryItem",
    "WebhookTicketPayload",
    "verify_zendesk_webhook_signature",
    "compute_zendesk_webhook_signature",
    "WebhookVerificationError",
    "MetricsCollector",
    "get_metrics_collector",
    "SlidingWindowRateLimiter",
    "get_rate_limiter",
    "RateLimitExceededError",
    "AuditLogger",
    "get_audit_logger",
    "GeminiAPIError",
    "GeminiAuthError",
    "GeminiRateLimitError",
]




