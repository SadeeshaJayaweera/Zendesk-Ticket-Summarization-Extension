#!/usr/bin/env python3
"""Live Integration Verification Script for Zendesk API Client.

Performs live end-to-end integration tests against a real Zendesk sandbox/instance:
1. Validates configuration and credentials in .env.
2. Fetches ticket metadata (get_ticket).
3. Fetches ticket conversation comments (get_ticket_comments).
4. Fetches requester and assignee details (get_ticket_requester_and_assignee).
5. Posts a private internal note with public=False (post_internal_note).
6. Provides direct Zendesk Agent Workspace link for manual verification in the UI.

Usage:
  poetry run python scripts/test_zendesk_integration.py [--ticket-id <ID>]
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

# Ensure shared package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))

from zendesk_summarizer_shared.config import get_settings
from zendesk_summarizer_shared.zendesk_client import ZendeskClient, ZendeskAPIError, ZendeskAuthError


async def run_integration_check(ticket_id: int | None = None) -> bool:
    """Execute live Zendesk integration checks."""
    print("=" * 70)
    print("🚀 Starting Live Zendesk API Client Integration Check")
    print("=" * 70)

    settings = get_settings()

    if not settings.is_zendesk_configured:
        print("\n❌ Zendesk configuration is incomplete in .env.")
        print("   Required variables:")
        print(f"   - ZENDESK_SUBDOMAIN : {'SET (' + settings.zendesk_subdomain + ')' if settings.zendesk_subdomain else 'MISSING'}")
        print(f"   - ZENDESK_EMAIL     : {'SET (' + settings.zendesk_email + ')' if settings.zendesk_email else 'MISSING'}")
        print(f"   - ZENDESK_API_TOKEN : {'SET' if settings.zendesk_api_token.get_secret_value() else 'MISSING'}")
        print("\n💡 Please create/update your `.env` file with real sandbox credentials:")
        print("   ZENDESK_SUBDOMAIN=your_subdomain")
        print("   ZENDESK_EMAIL=your_email@example.com")
        print("   ZENDESK_API_TOKEN=your_token_here")
        return False

    client = ZendeskClient(settings=settings)

    print(f"Instance Subdomain : {settings.zendesk_subdomain}")
    print(f"Agent / Auth User  : {settings.zendesk_email}/token")
    print(f"Base API URL       : {settings.zendesk_base_url}")
    print("-" * 70)

    try:
        # Step 1: Determine target ticket ID
        target_ticket_id = ticket_id
        if not target_ticket_id:
            print("\n📋 [1/5] Listing recent tickets to locate target ticket...")
            tickets = await client.list_tickets(per_page=5, page=1)
            if not tickets:
                print("❌ No tickets found in this Zendesk instance.")
                print("   Please create a test ticket in Zendesk Agent Workspace or pass --ticket-id <ID>.")
                return False
            target_ticket_id = tickets[0].id
            print(f"   Using most recent ticket: #{target_ticket_id} ('{tickets[0].subject}')")
        else:
            print(f"\n📋 [1/5] Using specified ticket ID: #{target_ticket_id}")

        # Step 2: Fetch ticket details
        print(f"\n🎫 [2/5] Fetching Ticket #{target_ticket_id} metadata (get_ticket)...")
        ticket = await client.get_ticket(target_ticket_id)
        print(f"   ✅ Ticket Retrieved Successfully!")
        print(f"      - ID          : #{ticket.id}")
        print(f"      - Subject     : {ticket.subject}")
        print(f"      - Status      : {ticket.status.upper()}")
        print(f"      - Priority    : {ticket.priority}")
        print(f"      - Requester ID: {ticket.requester_id}")
        print(f"      - Assignee ID : {ticket.assignee_id}")
        print(f"      - Tags        : {ticket.tags}")
        print(f"      - Created At  : {ticket.created_at}")

        # Step 3: Fetch ticket comments thread
        print(f"\n💬 [3/5] Fetching Ticket comments thread (get_ticket_comments)...")
        comments = await client.get_ticket_comments(target_ticket_id)
        print(f"   ✅ Fetched {len(comments)} comment(s) in conversation thread!")
        for idx, c in enumerate(comments[:3], 1):
            visibility = "Public Reply" if c.public else "🔒 Internal Note"
            print(f"      [{idx}] Author #{c.author_id} | {visibility} | {len(c.body)} chars: {c.body[:60]}...")
        if len(comments) > 3:
            print(f"      ... ({len(comments) - 3} more comments)")

        # Step 4: Fetch requester and assignee user profiles
        print(f"\n👥 [4/5] Fetching Requester and Assignee details (get_ticket_requester_and_assignee)...")
        requester, assignee = await client.get_ticket_requester_and_assignee(target_ticket_id)
        if requester:
            print(f"   ✅ Requester: {requester.name} ({requester.email or 'no email'}) [Role: {requester.role}]")
        else:
            print(f"   ℹ️ Requester: None / Not Found")

        if assignee:
            print(f"   ✅ Assignee : {assignee.name} ({assignee.email or 'no email'}) [Role: {assignee.role}]")
        else:
            print(f"   ℹ️ Assignee : Unassigned")

        # Step 5: Post test internal note
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        test_note_body = (
            f"🔒 **[Zendesk Ticket Summarizer - Integration Verification]**\n"
            f"- **Timestamp:** {timestamp_str}\n"
            f"- **Visibility Check:** `public: false` (Internal Private Note)\n"
            f"- **Status:** Verified API client communication."
        )

        print(f"\n📝 [5/5] Posting Test Internal Note (public=False)...")
        created_comment = await client.post_internal_note(
            ticket_id=target_ticket_id,
            body=test_note_body,
            public=False,
        )
        print(f"   ✅ Internal Note Posted Successfully!")
        print(f"      - Comment ID : #{created_comment.id}")
        print(f"      - Is Public  : {created_comment.public} (strictly False)")

        # Verification summary
        agent_url = f"{settings.zendesk_base_url}/agent/tickets/{target_ticket_id}"
        print("\n" + "=" * 70)
        print("🎯 INTEGRATION VERIFICATION COMPLETE")
        print("=" * 70)
        print(f"🔗 Zendesk Agent Workspace URL:")
        print(f"   {agent_url}")
        print("\n📌 Visual Confirmation Steps in Zendesk UI:")
        print("   1. Open the URL above in your browser.")
        print("   2. Verify the newly posted comment appears with a yellow background / 'Internal note' tag.")
        print("   3. Confirm the note is NOT visible to end users in the customer portal.")
        print("=" * 70)
        return True

    except ZendeskAuthError as exc:
        print(f"\n❌ Zendesk Authentication Error: {exc}")
        return False
    except ZendeskAPIError as exc:
        print(f"\n❌ Zendesk API Error: {exc}")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Zendesk API Client Live Integration Check")
    parser.add_argument("--ticket-id", type=int, default=None, help="Specific Zendesk Ticket ID to test against")
    args = parser.parse_args()

    success = asyncio.run(run_integration_check(ticket_id=args.ticket_id))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
