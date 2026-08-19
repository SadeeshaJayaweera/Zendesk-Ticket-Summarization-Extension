#!/usr/bin/env python3
"""Interactive Verification Script for Zendesk Ticket Summarizer MCP Server.

Simulates an MCP client communicating with the MCP tools directly.

Usage:
  poetry run python scripts/test_mcp_client.py [--ticket-id <ID>] [--post]
"""

import argparse
import asyncio
import os
import sys

# Ensure shared and mcp-server are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp-server")))

from mcp_server.server import (
    get_service_status,
    get_ticket,
    list_recent_tickets,
    post_internal_note,
    summarize_text,
    summarize_ticket,
)
from zendesk_summarizer_shared.config import get_settings


async def run_mcp_verification(ticket_id: str | None = None, post_note: bool = False):
    print("=" * 75)
    print("🔌 Zendesk Ticket Summarizer — MCP Server Verification")
    print("=" * 75)

    settings = get_settings()

    # 1. Check Service Status
    print("\n🔍 [1/4] Checking MCP Service Status via get_service_status()...")
    status_output = get_service_status()
    print(status_output)

    # 2. List Recent Tickets or Demo Text
    if settings.is_zendesk_configured:
        print("\n📋 [2/4] Fetching recent tickets via list_recent_tickets()...")
        recent_tickets_str = await list_recent_tickets(limit=5)
        print(recent_tickets_str)

        target_id = ticket_id or "1"
        print(f"\n📥 [3/4] Inspecting ticket #{target_id} via get_ticket()...")
        ticket_details = await get_ticket(target_id)
        print(ticket_details[:500] + ("..." if len(ticket_details) > 500 else ""))

        print(f"\n🤖 [4/4] Summarizing ticket #{target_id} via summarize_ticket()...")
        summary_result = await summarize_ticket(target_id, style="standard")
        print("\n" + "=" * 60)
        print(summary_result)
        print("=" * 60)

        if post_note:
            print(f"\n🚀 Posting internal note to ticket #{target_id} via post_internal_note()...")
            post_result = await post_internal_note(target_id, summary_result)
            print(post_result)
    else:
        print("\nℹ️ Zendesk credentials not configured in environment.")
        print("   Testing direct summarization tool summarize_text()...")
        sample_transcript = (
            "Customer (Alice): I can't export my billing report to CSV.\n"
            "Agent (Bob): We investigated and found high load on the query service.\n"
            "Agent (Bob): We applied a performance patch and will update you by 2 PM."
        )
        print("\nInput Transcript:")
        print(sample_transcript)

        print("\n🤖 Generating Summary via summarize_text():")
        summary_result = await summarize_text(sample_transcript, subject="Billing CSV Export Failure")
        print("\n" + "=" * 60)
        print(summary_result)
        print("=" * 60)

    print("\n✅ MCP Server Tool Handler Verification Complete!")


def main():
    parser = argparse.ArgumentParser(description="MCP Client Verification")
    parser.add_argument("--ticket-id", type=str, default=None, help="Zendesk ticket ID")
    parser.add_argument("--post", action="store_true", help="Post internal note to ticket")
    args = parser.parse_args()

    asyncio.run(run_mcp_verification(ticket_id=args.ticket_id, post_note=args.post))


if __name__ == "__main__":
    main()
