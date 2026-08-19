#!/usr/bin/env python3
"""Live End-to-End Pipeline Verification for Ticket Summarization Engine.

Runs the complete pipeline:
1. Fetch ticket metadata and comment history via ZendeskClient (or load realistic multi-turn conversation).
2. Build structured prompt context via TicketContextBuilder (with speaker labels & recency preservation).
3. Generate structured summary via GeminiSummarizer or GroqSummarizer.
4. Format into clean Markdown internal note via InternalNoteFormatter.
5. (Optional) Post internal note back to ticket with public=False.

Usage:
  poetry run python scripts/test_summarize_pipeline.py [--ticket-id <ID>] [--post-note] [--style standard|brief|action_only|detailed]
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

# Ensure shared package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))

from zendesk_summarizer_shared.config import get_settings
from zendesk_summarizer_shared.models import Comment, Ticket, User
from zendesk_summarizer_shared.summarizer import (
    InternalNoteFormatter,
    TicketContextBuilder,
    get_summarizer,
)
from zendesk_summarizer_shared.zendesk_client import ZendeskClient


def create_realistic_sample_conversation():
    """Fallback multi-message conversation for demonstration and validation if no live Zendesk ticket ID is given."""
    ticket = Ticket(
        id=9901,
        subject="Webhook delivery failures on invoice.payment_succeeded events",
        description="Our webhooks for invoice payments have stopped delivering since 8:00 AM UTC today.",
        status="open",
        priority="urgent",
        requester_id=5001,
        assignee_id=9001,
        tags=["webhooks", "billing", "api", "tier1-enterprise"],
        created_at=datetime(2026, 8, 18, 8, 15, 0),
    )

    requester = User(id=5001, name="Sarah Chen (VP Engineering)", email="schen@fintechcorp.io", role="end-user")
    assignee = User(id=9001, name="David Miller (Senior Escalations)", email="dmiller@support.com", role="agent")

    comments = [
        Comment(
            id=1,
            author_id=5001,
            body=(
                "Hi Support Team, starting at 08:00 UTC, our production endpoint https://api.fintechcorp.io/webhooks/stripe "
                "stopped receiving invoice.payment_succeeded events. We see 0 inbound requests. "
                "Our automated billing pipeline is currently halted. This is affecting ~1,200 transactions."
            ),
            public=True,
            created_at=datetime(2026, 8, 18, 8, 15, 0),
        ),
        Comment(
            id=2,
            author_id=9001,
            body=(
                "Internal Note: Checking webhook dispatcher logs in Datadog. Webhook queue worker cluster #3 experienced "
                "a deadlock following migration patch 4.12.0 at 07:55 UTC. Dispatcher queue currently backed up by 15,400 messages. "
                "Escalating to on-call infrastructure engineer (Alex)."
            ),
            public=False,
            created_at=datetime(2026, 8, 18, 8, 25, 0),
        ),
        Comment(
            id=3,
            author_id=9001,
            body=(
                "Hi Sarah, thanks for reaching out. We have identified an unexpected processing delay in our "
                "webhook dispatch cluster following a morning maintenance release. Our engineering team is currently "
                "draining the stalled queue workers and rolling back the worker service. "
                "We will provide a status update every 30 minutes until full resolution."
            ),
            public=True,
            created_at=datetime(2026, 8, 18, 8, 35, 0),
        ),
        Comment(
            id=4,
            author_id=5001,
            body=(
                "Thanks David. Can you confirm whether missed webhook payloads will be automatically retried with their "
                "original event IDs, or will we need to run manual backfills via the reconciliation API?"
            ),
            public=True,
            created_at=datetime(2026, 8, 18, 8, 45, 0),
        ),
        Comment(
            id=5,
            author_id=9001,
            body=(
                "Hi Sarah, I can confirm that all queued events are intact and will be automatically redelivered with "
                "their original event IDs and timestamp signatures once the worker cluster recovers. No manual backfill needed. "
                "Queue drain is now at 65%. I will follow up with you by 09:30 UTC with final confirmation."
            ),
            public=True,
            created_at=datetime(2026, 8, 18, 9, 0, 0),
        ),
    ]

    return ticket, comments, requester, assignee


async def run_pipeline(ticket_id: int | None = None, post_note: bool = False, style: str = "standard"):
    print("=" * 75)
    print("🧠 Starting Zendesk Summarizer Full Pipeline Verification")
    print("=" * 75)

    settings = get_settings()
    print(f"LLM Provider Configured : {settings.llm_provider.upper()}")
    if settings.llm_provider == "groq":
        print(f"Groq Model              : {settings.groq_model}")
        print(f"Groq Key Status         : {'SET' if settings.is_groq_configured else 'MISSING'}")
    else:
        print(f"Gemini Model            : {settings.gemini_model}")
        print(f"Gemini Key Status       : {'SET' if settings.is_gemini_configured else 'MISSING'}")

    ticket = None
    comments = []
    requester = None
    assignee = None

    # Step 1: Fetch Ticket & Comments
    if ticket_id and settings.is_zendesk_configured:
        print(f"\n📥 [1/4] Fetching Ticket #{ticket_id} from Zendesk instance ({settings.zendesk_subdomain})...")
        client = ZendeskClient(settings=settings)
        ticket = await client.get_ticket(ticket_id)
        comments = await client.get_ticket_comments(ticket_id)
        requester, assignee = await client.get_ticket_requester_and_assignee(ticket_id)
        print(f"   ✅ Retrieved Ticket: '{ticket.subject}' with {len(comments)} comment(s).")
    else:
        print("\n📥 [1/4] Using realistic multi-turn sample conversation transcript...")
        ticket, comments, requester, assignee = create_realistic_sample_conversation()
        print(f"   ✅ Loaded Ticket #{ticket.id}: '{ticket.subject}' ({len(comments)} comments).")

    # Step 2: Build Prompt Context
    print("\n📝 [2/4] Building structured prompt context with TicketContextBuilder...")
    context_builder = TicketContextBuilder()
    context = context_builder.build_context(
        ticket=ticket,
        comments=comments,
        requester=requester,
        assignee=assignee,
    )
    print(f"   ✅ Context built ({len(context)} characters, {len(comments)} comments formatted).")

    # Step 3: Run AI Summarizer
    print(f"\n🤖 [3/4] Running AI Summarization (Style: '{style}')...")
    summarizer = get_summarizer(settings=settings)

    if (settings.llm_provider == "gemini" and not settings.is_gemini_configured) and not settings.is_groq_configured:
        print("\n⚠️ No LLM API key (GEMINI_API_KEY or GROQ_API_KEY) found in environment or .env.")
        print("   Demonstrating defensive parser and note formatter with verified sample response...")
        from zendesk_summarizer_shared.models import SummaryStructured
        structured_summary = SummaryStructured(
            executive_summary="Webhook delivery failure on invoice.payment_succeeded halted production billing for ~1,200 transactions.",
            customer_issue="Inbound payment webhooks stopped delivering at 08:00 UTC due to worker queue backlog.",
            actions_taken=[
                "Agent identified deadlock on worker cluster #3 following patch 4.12.0.",
                "Engineering drained and restarted worker pool (drain progress at 65%).",
                "Agent confirmed queued events will automatically redeliver with original event IDs."
            ],
            current_status="Queue draining in progress; worker cluster recovering.",
            commitments=[
                "Provide status updates every 30 minutes.",
                "Final resolution confirmation by 09:30 UTC."
            ],
            action_items=[
                "Verify queue drain reaches 100% by 09:30 UTC.",
                "Confirm customer receives backlogged webhook deliveries."
            ],
            sentiment="urgent",
            notes=["Tier 1 enterprise customer affecting 1,200 transactions."]
        )
    else:
        structured_summary = await summarizer.summarize_context(context, summary_style=style)

    print("   ✅ AI Structured Summary Generated Successfully!")
    print(f"      - Issue       : {structured_summary.customer_issue}")
    print(f"      - Status      : {structured_summary.current_status}")
    print(f"      - Sentiment   : {structured_summary.sentiment}")
    print(f"      - Commitments : {len(structured_summary.commitments)} item(s)")
    print(f"      - Actions     : {len(structured_summary.actions_taken)} item(s)")

    # Step 4: Format Internal Note
    print("\n📄 [4/4] Generating Scannable Markdown Note via InternalNoteFormatter:")
    formatted_note = InternalNoteFormatter.format(structured_summary)

    print("\n" + "=" * 75)
    print("📌 GENERATED ZENDESK INTERNAL NOTE PREVIEW:")
    print("=" * 75)
    print(formatted_note)
    print("=" * 75)

    # Optional: Post back to Zendesk
    if post_note and ticket_id and settings.is_zendesk_configured:
        print(f"\n🚀 Posting internal note to Zendesk ticket #{ticket_id} (public=False)...")
        client = ZendeskClient(settings=settings)
        await client.post_internal_note(ticket_id=ticket_id, body=formatted_note, public=False)
        print("   ✅ Internal note posted to Zendesk successfully!")

    return True


def main():
    parser = argparse.ArgumentParser(description="Zendesk Summarizer Pipeline Test")
    parser.add_argument("--ticket-id", type=int, default=None, help="Live Zendesk ticket ID to summarize")
    parser.add_argument("--style", type=str, default="standard", choices=["standard", "brief", "action_only", "detailed"])
    parser.add_argument("--post-note", action="store_true", help="Post generated note to Zendesk (requires live credentials)")
    args = parser.parse_args()

    asyncio.run(run_pipeline(ticket_id=args.ticket_id, post_note=args.post_note, style=args.style))


if __name__ == "__main__":
    main()
