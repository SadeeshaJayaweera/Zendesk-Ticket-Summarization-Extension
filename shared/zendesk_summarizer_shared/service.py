"""High-level Orchestration Service for Zendesk Ticket Summarization."""

from typing import List, Optional, Tuple
from zendesk_summarizer_shared.audit_logger import AuditLogger, get_audit_logger
from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.draft_store import DraftStore, get_draft_store
from zendesk_summarizer_shared.gemini_client import GeminiClient
from zendesk_summarizer_shared.metrics import MetricsCollector, get_metrics_collector
from zendesk_summarizer_shared.models import (
    PendingDraft,
    PendingDraftResponse,
    PostNoteResponse,
    SummarizeResponse,
    SummaryStructured,
    Ticket,
    TicketDetailResponse,
    TicketHistoryResponse,
    TicketHistorySummaryItem,
)
from zendesk_summarizer_shared.prompts import (
    build_raw_text_prompt,
    build_summarization_prompt,
)
from zendesk_summarizer_shared.summarizer import (
    BaseSummarizer,
    TicketContextBuilder,
    get_summarizer,
)
from zendesk_summarizer_shared.zendesk_client import ZendeskClient


class TicketSummarizerService:
    """Service encapsulating ticket retrieval, AI summarization, and note posting."""

    def __init__(
        self,
        zendesk_client: Optional[ZendeskClient] = None,
        gemini_client: Optional[GeminiClient] = None,
        summarizer: Optional[BaseSummarizer] = None,
        draft_store: Optional[DraftStore] = None,
        metrics: Optional[MetricsCollector] = None,
        audit_logger: Optional[AuditLogger] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.zendesk = zendesk_client or ZendeskClient(settings=self.settings)
        self.gemini = gemini_client or GeminiClient(settings=self.settings)
        if summarizer is not None:
            self.summarizer = summarizer
        elif gemini_client is not None:
            self.summarizer = None
        else:
            self.summarizer = get_summarizer(settings=self.settings)
        self.draft_store = draft_store or get_draft_store()
        self.metrics = metrics or get_metrics_collector()
        self.audit_logger = audit_logger or get_audit_logger()
        self.context_builder = TicketContextBuilder()




    async def get_ticket_details(self, ticket_id: int) -> TicketDetailResponse:
        """Retrieve ticket metadata and all conversation comments."""
        ticket = await self.zendesk.get_ticket(ticket_id)
        comments = await self.zendesk.get_ticket_comments(ticket_id)
        return TicketDetailResponse(
            ticket=ticket,
            comments=comments,
            total_comments=len(comments),
        )

    async def summarize_ticket(
        self,
        ticket_id: int,
        summary_style: str = "standard",
    ) -> SummarizeResponse:
        """Fetch ticket conversation, generate AI summary, and produce markdown output."""
        ticket = await self.zendesk.get_ticket(ticket_id)
        comments = await self.zendesk.get_ticket_comments(ticket_id)
        requester, assignee = None, None
        try:
            user_tuple = await self.zendesk.get_ticket_requester_and_assignee(ticket_id)
            if isinstance(user_tuple, (tuple, list)) and len(user_tuple) == 2:
                requester, assignee = user_tuple
        except Exception:
            requester, assignee = None, None

        # Use summarizer if configured, otherwise fallback to gemini client
        if self.summarizer:
            structured_summary: SummaryStructured = await self.summarizer.summarize_ticket(
                ticket=ticket,
                comments=comments,
                requester=requester,
                assignee=assignee,
                summary_style=summary_style,
            )
        else:
            prompt = build_summarization_prompt(
                ticket=ticket,
                comments=comments,
                summary_style=summary_style,
            )
            structured_summary = await self.gemini.generate_summary(prompt)


        markdown_note = structured_summary.to_markdown()
        model_used = self.settings.groq_model if self.settings.llm_provider == "groq" else self.settings.gemini_model

        # Record metrics & audit event
        self.metrics.record_summary_generated(style=summary_style, provider=self.settings.llm_provider)
        self.audit_logger.log_event(
            event_type="summarize_ticket",
            ticket_id=ticket_id,
            status="success",
            model_used=model_used,
            summary_style=summary_style,
            source="agent_request",
        )

        return SummarizeResponse(
            ticket_id=ticket_id,
            subject=ticket.subject,
            summary=structured_summary,
            markdown_note=markdown_note,
            model_used=model_used,
        )

    async def post_summary_note(
        self,
        ticket_id: int,
        note_body: str,
        public: bool = False,
    ) -> PostNoteResponse:
        """Post a summary as a Zendesk internal note (public=False by default)."""
        await self.zendesk.post_internal_note(
            ticket_id=ticket_id,
            body=note_body,
            public=public,
        )

        # Mark any existing automated pending draft as posted
        self.draft_store.mark_draft_posted(ticket_id)

        # Record metrics & audit event
        self.metrics.record_note_posted()
        self.audit_logger.log_event(
            event_type="post_note",
            ticket_id=ticket_id,
            status="success",
            source="agent_post",
            details={"public": public, "body_length": len(note_body)},
        )

        note_type = "Public reply" if public else "Internal note"
        return PostNoteResponse(
            ticket_id=ticket_id,
            is_public=public,
            status="success",
            message=f"{note_type} posted successfully to ticket #{ticket_id}",
        )

    async def summarize_and_post(
        self,
        ticket_id: int,
        summary_style: str = "standard",
    ) -> Tuple[SummarizeResponse, PostNoteResponse]:
        """Convenience method: generate AI summary and automatically post as internal note."""
        summary_resp = await self.summarize_ticket(ticket_id, summary_style=summary_style)
        post_resp = await self.post_summary_note(
            ticket_id=ticket_id,
            note_body=summary_resp.markdown_note,
            public=False,
        )
        return summary_resp, post_resp

    async def summarize_raw_text(
        self,
        text: str,
        subject: Optional[str] = None,
        summary_style: str = "standard",
    ) -> SummarizeResponse:
        """Generate structured summary for arbitrary text or chat conversation."""
        prompt = build_raw_text_prompt(
            text=text,
            subject=subject,
            summary_style=summary_style,
        )

        structured_summary: SummaryStructured = await self.gemini.generate_summary(prompt)
        markdown_note = structured_summary.to_markdown()

        # Record metrics & audit
        self.metrics.record_summary_generated(style=summary_style, provider="gemini")
        self.audit_logger.log_event(
            event_type="summarize_text",
            status="success",
            model_used=self.settings.gemini_model,
            summary_style=summary_style,
            source="direct_text",
        )

        return SummarizeResponse(
            ticket_id=None,
            subject=subject,
            summary=structured_summary,
            markdown_note=markdown_note,
            model_used=self.settings.gemini_model,
        )

    async def get_ticket_history(self, ticket_id: int) -> TicketHistoryResponse:
        """Retrieve previous AI summaries and internal notes posted to the ticket, plus any pending draft."""
        comments = await self.zendesk.get_ticket_comments(ticket_id)
        
        # Filter comments for AI summaries (internal notes containing AI summary indicators)
        history_items: List[TicketHistorySummaryItem] = []
        for c in comments:
            body = c.plain_body or c.body or ""
            is_ai_summary = ("AI Ticket Summary" in body) or ("🤖" in body) or (not c.public and "Summary" in body)
            if is_ai_summary:
                first_line = body.strip().split("\n")[0][:100]
                history_items.append(
                    TicketHistorySummaryItem(
                        id=c.id,
                        author_id=c.author_id,
                        created_at=c.created_at,
                        body=body,
                        is_internal=not c.public,
                        preview=first_line,
                    )
                )

        pending = self.draft_store.get_pending_draft(ticket_id)

        return TicketHistoryResponse(
            ticket_id=ticket_id,
            summaries=history_items,
            total=len(history_items),
            pending_draft=pending,
        )

    async def get_pending_draft(self, ticket_id: int) -> PendingDraftResponse:
        """Retrieve pending review summary draft for a ticket if one exists."""
        draft = self.draft_store.get_pending_draft(ticket_id)
        return PendingDraftResponse(
            ticket_id=ticket_id,
            has_pending_draft=draft is not None,
            draft=draft,
        )

    async def process_solved_ticket_webhook(
        self,
        ticket_id: int,
        summary_style: str = "standard",
    ) -> PendingDraft:
        """Automatically generate an AI draft summary when a ticket is marked solved.

        Saves the resulting summary with status='pending_review' in DraftStore.
        DOES NOT auto-post to Zendesk (preserves human-in-the-loop review).
        """
        summary_resp = await self.summarize_ticket(ticket_id=ticket_id, summary_style=summary_style)
        draft = self.draft_store.save_draft(
            ticket_id=ticket_id,
            summary=summary_resp.summary,
            markdown_note=summary_resp.markdown_note,
            source_trigger="zendesk_webhook_solved",
        )

        self.metrics.record_webhook_received(status="pending_review")
        self.audit_logger.log_event(
            event_type="webhook_solve_trigger",
            ticket_id=ticket_id,
            status="pending_review",
            source="zendesk_webhook",
            details={"draft_status": draft.status},
        )
        return draft


    async def list_recent_tickets(
        self,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> List[Ticket]:
        """List recent tickets from Zendesk, optionally filtered by status."""
        return await self.zendesk.list_tickets(per_page=limit, status=status)




# Production service refinement 1

# Production service refinement 2

# Production service refinement 3

# Production service refinement 4
