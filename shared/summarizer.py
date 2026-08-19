"""Re-export module for summarization engine in shared package root.

Provides:
- TicketContextBuilder
- InternalNoteFormatter
- BaseSummarizer
- GeminiSummarizer
- GroqSummarizer
- get_summarizer
- SummarizationError, LLMAuthError, LLMRateLimitError, LLMAPIError
"""

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
    build_ticket_summary_prompt,
    extract_structured_json,
    get_summarizer,
    parse_llm_response_to_summary,
)

__all__ = [
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
    "build_ticket_summary_prompt",
    "extract_structured_json",
    "parse_llm_response_to_summary",
]
