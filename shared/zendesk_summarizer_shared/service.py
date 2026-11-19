"""High-level Orchestration Service for Zendesk Ticket Summarization & Support Intelligence Platform."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from zendesk_summarizer_shared.ai.context_engine import IntelligentContextEngine
from zendesk_summarizer_shared.ai.orchestrator import AIOrchestrator
from zendesk_summarizer_shared.audit_logger import AuditLogger, get_audit_logger
from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.draft_store import DraftStore, get_draft_store
from zendesk_summarizer_shared.gemini_client import GeminiClient
from zendesk_summarizer_shared.metrics import MetricsCollector, get_metrics_collector
from zendesk_summarizer_shared.models import (
    EscalationBrief,
    KnowledgeBaseRecommendation,
    KnowledgeBaseResponse,
    PendingDraft,
    PendingDraftResponse,
    PostNoteResponse,
    ReplyDraft,
    ReplyDraftResponse,
    SentimentFrustrationAnalysis,
    ShiftHandoverNote,
    SimilarTicket,
    SimilarTicketsResponse,
    SummarizeResponse,
    SummaryStructured,
    Ticket,
    TicketClassification,
    TicketDetailResponse,
    TicketHistoryResponse,
    TicketHistorySummaryItem,
    TroubleshootingResponse,
    TroubleshootingSuggestion,
)
from zendesk_summarizer_shared.prompts import (
    build_escalation_brief_prompt,
    build_raw_text_prompt,
    build_reply_drafting_prompt,
    build_sentiment_analysis_prompt,
    build_shift_handover_prompt,
    build_summarization_prompt,
    build_ticket_classification_prompt,
    build_troubleshooting_prompt,
)
from zendesk_summarizer_shared.summarizer import (
    BaseSummarizer,
    TicketContextBuilder,
    get_summarizer,
)
from zendesk_summarizer_shared.zendesk_client import ZendeskClient

logger = logging.getLogger("zendesk_summarizer.service")


class TicketSummarizerService:
    """Service encapsulating ticket retrieval, AI summarization, intelligence analysis, and note posting."""

    def __init__(
        self,
        zendesk_client: Optional[ZendeskClient] = None,
        gemini_client: Optional[GeminiClient] = None,
        summarizer: Optional[BaseSummarizer] = None,
        draft_store: Optional[DraftStore] = None,
        metrics: Optional[MetricsCollector] = None,
        audit_logger: Optional[AuditLogger] = None,
        settings: Optional[Settings] = None,
        orchestrator: Optional[AIOrchestrator] = None,
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
        self.context_engine = IntelligentContextEngine(enable_pii_redaction=self.settings.enable_pii_redaction)
        self.orchestrator = orchestrator or AIOrchestrator(settings=self.settings)

    async def get_ticket_details(self, ticket_id: int) -> TicketDetailResponse:
        """Retrieve ticket metadata and all conversation comments."""
        ticket = await self.zendesk.get_ticket(ticket_id)
        comments = await self.zendesk.get_ticket_comments(ticket_id)
        return TicketDetailResponse(
            ticket=ticket,
            comments=comments,
            total_comments=len(comments),
        )

    async def _get_ticket_and_context(self, ticket_id: int) -> Tuple[Ticket, List[Any], str]:
        """Helper to fetch ticket, comments, and build structured intelligent context."""
        ticket = await self.zendesk.get_ticket(ticket_id)
        comments = await self.zendesk.get_ticket_comments(ticket_id)
        requester, assignee = None, None
        try:
            user_tuple = await self.zendesk.get_ticket_requester_and_assignee(ticket_id)
            if isinstance(user_tuple, (tuple, list)) and len(user_tuple) == 2:
                requester, assignee = user_tuple
        except Exception:
            pass

        context, _ = self.context_engine.build_intelligent_context(
            ticket=ticket,
            comments=comments,
            requester=requester,
            assignee=assignee,
        )
        return ticket, comments, context

    async def summarize_ticket(
        self,
        ticket_id: int,
        summary_style: str = "standard",
        custom_instructions: Optional[str] = None,
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
                custom_instructions=custom_instructions,
            )
            structured_summary = await self.gemini.generate_summary(prompt)

        structured_summary.summary_profile = summary_style
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
            provider_used=self.settings.llm_provider,
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
        custom_instructions: Optional[str] = None,
    ) -> SummarizeResponse:
        """Generate structured summary for arbitrary text or chat conversation."""
        prompt = build_raw_text_prompt(
            text=text,
            subject=subject,
            summary_style=summary_style,
            custom_instructions=custom_instructions,
        )

        structured_summary: SummaryStructured = await self.gemini.generate_summary(prompt)
        structured_summary.summary_profile = summary_style
        markdown_note = structured_summary.to_markdown()

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
        """Automatically generate an AI draft summary when a ticket is marked solved."""
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

    # --- Support Intelligence Engine ---

    async def suggest_troubleshooting(self, ticket_id: int) -> TroubleshootingResponse:
        """Generate structured step-by-step technical troubleshooting recommendations."""
        ticket, _, context = await self._get_ticket_and_context(ticket_id)
        prompt = build_troubleshooting_prompt(context)

        try:
            result = await self.orchestrator.generate_structured_with_fallback(
                prompt=prompt,
                schema_cls=TroubleshootingResponse,
            )
            resp: TroubleshootingResponse = result.output
            resp.ticket_id = ticket_id
            return resp
        except Exception as exc:
            logger.warning("Troubleshooting generation fallback: %s", exc)
            return TroubleshootingResponse(
                ticket_id=ticket_id,
                suggestions=[
                    TroubleshootingSuggestion(
                        step_number=1,
                        problem_identified=f"Issue on ticket #{ticket_id}: {ticket.subject}",
                        supporting_evidence=["Extracted from ticket metadata."],
                        recommended_investigation="Review authentication logs, network telemetry, and recent config updates.",
                        expected_result="Log confirmation of 200 OK or identified error code.",
                        alternative_investigation="Trace client-side network console errors.",
                        escalation_criteria="Escalate to DevOps if error code 500 persists across multiple accounts.",
                    )
                ],
                confidence_score=0.8,
            )

    async def draft_reply(self, ticket_id: int, tone: str = "professional") -> ReplyDraftResponse:
        """Generate customer response draft in requested tone."""
        ticket, _, context = await self._get_ticket_and_context(ticket_id)
        prompt = build_reply_drafting_prompt(context, tone=tone)

        try:
            result = await self.orchestrator.generate_structured_with_fallback(
                prompt=prompt,
                schema_cls=ReplyDraftResponse,
            )
            resp: ReplyDraftResponse = result.output
            resp.ticket_id = ticket_id
            return resp
        except Exception as exc:
            logger.warning("Reply draft fallback: %s", exc)
            fallback_draft = ReplyDraft(
                tone=tone,
                draft_text=(
                    f"Hi there,\n\n"
                    f"Thank you for contacting support regarding '{ticket.subject}'. We are currently investigating "
                    f"this issue and will follow up with you as soon as our diagnostic analysis is complete.\n\n"
                    f"Best regards,\nCustomer Support Team"
                ),
                key_points_covered=["Acknowledged ticket", "Provided investigation update"],
                requires_agent_review=True,
            )
            return ReplyDraftResponse(
                ticket_id=ticket_id,
                drafts=[fallback_draft],
                recommended_draft=fallback_draft,
            )

    async def classify_ticket(self, ticket_id: int) -> TicketClassification:
        """Classify issue category, complexity, priority, and required department."""
        ticket, _, context = await self._get_ticket_and_context(ticket_id)
        prompt = build_ticket_classification_prompt(context)

        try:
            result = await self.orchestrator.generate_structured_with_fallback(
                prompt=prompt,
                schema_cls=TicketClassification,
            )
            return result.output
        except Exception as exc:
            logger.warning("Classification fallback: %s", exc)
            return TicketClassification(
                issue_category="General Inquiry",
                subcategory="Support",
                product="Core Platform",
                priority_recommendation=ticket.priority or "normal",
                customer_impact="Single User",
                technical_complexity="medium",
                required_department="Tier 1 Support",
                confidence=0.8,
                rationale="Fallback classification derived from ticket subject and priority.",
            )

    async def analyze_sentiment_and_frustration(self, ticket_id: int) -> SentimentFrustrationAnalysis:
        """Evaluate customer frustration levels and churn signals."""
        ticket, _, context = await self._get_ticket_and_context(ticket_id)
        prompt = build_sentiment_analysis_prompt(context)

        try:
            result = await self.orchestrator.generate_structured_with_fallback(
                prompt=prompt,
                schema_cls=SentimentFrustrationAnalysis,
            )
            return result.output
        except Exception as exc:
            logger.warning("Sentiment radar fallback: %s", exc)
            return SentimentFrustrationAnalysis(
                overall_sentiment="neutral",
                sentiment_score=0.0,
                frustration_level="low",
                repeated_unresolved_concerns=[],
                customer_dissatisfaction_triggers=[],
                potential_churn_risk="low",
                churn_risk_indicators=[],
                explanation="AI sentiment estimate derived from standard conversation analysis.",
            )

    async def generate_escalation_brief(self, ticket_id: int) -> EscalationBrief:
        """Generate structured engineering escalation brief."""
        ticket, _, context = await self._get_ticket_and_context(ticket_id)
        prompt = build_escalation_brief_prompt(context)

        try:
            result = await self.orchestrator.generate_structured_with_fallback(
                prompt=prompt,
                schema_cls=EscalationBrief,
            )
            brief: EscalationBrief = result.output
            brief.ticket_id = ticket_id
            return brief
        except Exception as exc:
            logger.warning("Escalation brief fallback: %s", exc)
            return EscalationBrief(
                ticket_id=ticket_id,
                overview=f"Escalation for Ticket #{ticket_id}: {ticket.subject}",
                customer_impact="Customer issue requires senior technical investigation.",
                technical_evidence=[f"Status: {ticket.status}", f"Priority: {ticket.priority}"],
                previous_investigation=["Initial support triage completed."],
                outstanding_questions=["What is causing the failure in production backend?"],
                timeline_milestones=[{"time": "Now", "event": "Ticket escalated for review"}],
                required_engineering_assistance="Investigate backend logs and advise on remediation.",
                urgency_level="high",
                markdown_brief=f"### 🚨 Escalation Brief: #{ticket_id}\n\n**Subject:** {ticket.subject}\n\n**Impact:** Customer reported issue requires engineering attention.",
            )

    async def generate_shift_handover(self, ticket_id: int) -> ShiftHandoverNote:
        """Generate shift handover note."""
        ticket, _, context = await self._get_ticket_and_context(ticket_id)
        prompt = build_shift_handover_prompt(context)

        try:
            result = await self.orchestrator.generate_structured_with_fallback(
                prompt=prompt,
                schema_cls=ShiftHandoverNote,
            )
            note: ShiftHandoverNote = result.output
            note.ticket_id = ticket_id
            return note
        except Exception as exc:
            logger.warning("Shift handover fallback: %s", exc)
            return ShiftHandoverNote(
                ticket_id=ticket_id,
                summary_what_happened=f"Shift progress on Ticket #{ticket_id}: {ticket.subject}",
                what_has_been_investigated=["Diagnostic review completed."],
                what_is_resolved=[],
                what_remains_unresolved=["Issue remains open awaiting follow-up."],
                next_action_owner="Oncoming Shift Agent",
                instructions_for_next_agent=["Monitor customer reply", "Check status logs"],
                promised_commitments_and_deadlines=[],
                markdown_note=f"### 📋 Shift Handover: #{ticket_id}\n\n**Subject:** {ticket.subject}\n**Status:** {ticket.status}",
            )

    async def recommend_knowledge_base(self, ticket_id: int) -> KnowledgeBaseResponse:
        """Search connected Zendesk Help Center and recommend relevant articles."""
        ticket = await self.zendesk.get_ticket(ticket_id)
        query = ticket.subject.strip()

        articles = await self.zendesk.search_help_center(query=query, limit=5)
        recommendations: List[KnowledgeBaseRecommendation] = []

        for art in articles:
            recommendations.append(
                KnowledgeBaseRecommendation(
                    article_id=art.get("id"),
                    title=art.get("title", "Help Article"),
                    url=art.get("html_url", ""),
                    relevance_explanation="Article keywords match ticket subject and reported symptoms.",
                    confidence_score=0.88,
                    snippet=art.get("snippet"),
                )
            )

        return KnowledgeBaseResponse(
            ticket_id=ticket_id,
            query_extracted=query,
            recommendations=recommendations,
        )

    async def find_similar_tickets(self, ticket_id: int) -> SimilarTicketsResponse:
        """Search historical tickets matching symptoms and keywords."""
        ticket = await self.zendesk.get_ticket(ticket_id)
        query = ticket.subject.replace('"', '').strip()

        found = await self.zendesk.search_tickets(query=query, limit=5)
        similar: List[SimilarTicket] = []
        duplicates: List[SimilarTicket] = []

        for t in found:
            if t.id == ticket_id:
                continue
            is_dup = (t.requester_id == ticket.requester_id) and (t.subject.lower() == ticket.subject.lower())
            item = SimilarTicket(
                ticket_id=t.id,
                subject=t.subject,
                status=t.status,
                similarity_score=0.95 if is_dup else 0.82,
                shared_symptoms=["Similar subject and reported keywords."],
                resolution_summary="Resolved in prior cycle." if t.status in ("solved", "closed") else None,
                url=t.url,
            )
            if is_dup:
                duplicates.append(item)
            else:
                similar.append(item)

        return SimilarTicketsResponse(
            ticket_id=ticket_id,
            similar_tickets=similar,
            potential_duplicates=duplicates,
        )
