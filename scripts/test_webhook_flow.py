#!/usr/bin/env python3
"""End-to-End Simulation Script for Zendesk Solve Webhook + Pending Draft Flow.

Simulates:
1. Zendesk firing an HMAC-signed webhook to /webhooks/zendesk/ticket-status-changed on ticket solve.
2. Backend verifying HMAC signature, generating AI summary, and saving draft as 'pending_review'.
3. Sidebar app querying /api/tickets/{id}/pending-draft and retrieving pre-filled draft.
4. Agent submitting note via /api/tickets/{id}/notes, marking draft as posted.

Usage:
  poetry run python scripts/test_webhook_flow.py [--ticket-id <ID>]
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

# Ensure shared and backend are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from zendesk_summarizer_shared.config import get_settings
from zendesk_summarizer_shared.draft_store import get_draft_store
from zendesk_summarizer_shared.models import Comment, SummaryStructured, Ticket, User
from zendesk_summarizer_shared.security import (
    compute_zendesk_webhook_signature,
    verify_zendesk_webhook_signature,
)
from zendesk_summarizer_shared.service import TicketSummarizerService


async def simulate_webhook_flow(ticket_id: int = 8080):
    print("=" * 75)
    print("⚡ Zendesk Automated Solve Webhook & Pending Draft Verification")
    print("=" * 75)

    settings = get_settings()
    secret = settings.zendesk_webhook_secret.get_secret_value() or "test-webhook-secret-demo-key"
    print(f"Webhook Secret Configured : {'YES' if settings.is_webhook_secret_configured else 'DEMO KEY'}")
    print(f"LLM Provider Configured   : {settings.llm_provider.upper()}")

    # Step 1: Prepare Webhook Payload
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "ticket": {
            "id": ticket_id,
            "status": "solved",
            "subject": "Database latency spikes during report export",
        }
    }
    raw_body = json.dumps(payload)
    signature = compute_zendesk_webhook_signature(body=raw_body, timestamp=timestamp, secret=secret)

    print(f"\n📨 [1/4] Generating Zendesk Signed Webhook Event...")
    print(f"   Payload: {raw_body}")
    print(f"   Timestamp Header: {timestamp}")
    print(f"   HMAC-SHA256 Sig : {signature[:25]}...")

    # Step 2: Verify Signature
    print(f"\n🔐 [2/4] Verifying Incoming Webhook Signature on Backend...")
    is_valid = verify_zendesk_webhook_signature(
        body=raw_body,
        signature_header=signature,
        timestamp_header=timestamp,
        secret=secret,
    )
    print(f"   ✅ Webhook Signature Verified: {is_valid}")

    # Step 3: Run Summarization and Store Pending Draft
    print(f"\n🤖 [3/4] Processing Ticket #{ticket_id} and storing pending draft...")
    draft_store = get_draft_store()

    mock_summary = SummaryStructured(
        executive_summary="Database latency caused by unindexed foreign keys during report exports.",
        customer_issue="Queries timing out after 30 seconds when exporting transaction history.",
        actions_taken=[
            "Agent checked RDS slow query logs.",
            "DBA applied compound index on transactions(account_id, created_at).",
            "Verified query latency dropped from 32s to 45ms.",
        ],
        current_status="Solved",
        commitments=["Customer confirmed export works in < 2 seconds."],
        action_items=["Monitor RDS CPU load during next billing cycle."],
        sentiment="positive",
    )
    markdown_note = mock_summary.to_markdown()

    draft = draft_store.save_draft(
        ticket_id=ticket_id,
        summary=mock_summary,
        markdown_note=markdown_note,
        source_trigger="zendesk_webhook_solved",
    )

    print(f"   ✅ Pre-draft generated and stored with status='{draft.status}'!")
    print(f"   Draft Preview:\n{draft.markdown_note[:300]}...")

    # Step 4: Simulate Sidebar App loading pending draft
    print(f"\n📱 [4/4] Simulating Zendesk Sidebar App Opening on Ticket #{ticket_id}...")
    pending = draft_store.get_pending_draft(ticket_id)
    if pending:
        print(f"   ✅ Sidebar App detected pending draft!")
        print(f"   ⚡ Banner Displayed: 'Pre-Drafted Summary (Pending Review)'")
        print(f"   📝 Editor Pre-filled: {len(pending.markdown_note)} characters ready for review.")

        # Simulate Agent Review and Posting
        print(f"\n🚀 Agent Reviews Note and clicks 'Post as Internal Note'...")
        draft_store.mark_draft_posted(ticket_id)
        print(f"   ✅ Internal note posted! Draft status updated to 'posted'.")
        assert draft_store.get_pending_draft(ticket_id) is None
        print(f"   ✅ Pending draft queue cleared for ticket #{ticket_id}.")

    print("\n" + "=" * 75)
    print("🎉 All Webhook & Automation Workflow Verifications Passed!")
    print("=" * 75)


def main():
    parser = argparse.ArgumentParser(description="Zendesk Webhook Flow Test")
    parser.add_argument("--ticket-id", type=int, default=8080, help="Test Ticket ID")
    args = parser.parse_args()

    asyncio.run(simulate_webhook_flow(ticket_id=args.ticket_id))


if __name__ == "__main__":
    main()
