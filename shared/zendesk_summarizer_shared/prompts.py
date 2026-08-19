"""Prompt generation and templating for Zendesk Ticket Summarization."""

import json
from typing import List, Optional
from zendesk_summarizer_shared.models import ZendeskComment, ZendeskTicket


def format_conversation_transcript(
    ticket: Optional[ZendeskTicket],
    comments: List[ZendeskComment]
) -> str:
    """Format ticket metadata and comments into a structured chronological transcript."""
    transcript_parts: List[str] = []

    if ticket:
        transcript_parts.append("=== TICKET METADATA ===")
        transcript_parts.append(f"Ticket ID: #{ticket.id}")
        transcript_parts.append(f"Subject: {ticket.subject or 'No subject'}")
        transcript_parts.append(f"Status: {ticket.status}")
        transcript_parts.append(f"Priority: {ticket.priority or 'normal'}")
        if ticket.tags:
            transcript_parts.append(f"Tags: {', '.join(ticket.tags)}")
        if ticket.description:
            transcript_parts.append(f"Original Description:\n{ticket.description.strip()}")
        transcript_parts.append("=======================\n")

    transcript_parts.append("=== CONVERSATION THREAD (Chronological) ===")

    if not comments:
        transcript_parts.append("No comments recorded yet.")
    else:
        for idx, comment in enumerate(comments, start=1):
            created_str = (
                comment.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                if comment.created_at
                else "Unknown Time"
            )
            visibility = "PUBLIC REPLY" if comment.public else "INTERNAL NOTE (PRIVATE)"
            role = f"User #{comment.author_id}"
            
            # If requester matches author
            if ticket and ticket.requester_id == comment.author_id:
                role = f"Requester/Customer (User #{comment.author_id})"
            elif ticket and ticket.assignee_id == comment.author_id:
                role = f"Assigned Agent (User #{comment.author_id})"

            body = comment.plain_body or comment.body or ""
            transcript_parts.append(
                f"[{idx}] [{visibility}] {role} at {created_str}:\n{body.strip()}\n"
            )

    transcript_parts.append("===========================================")
    return "\n".join(transcript_parts)


def build_summarization_prompt(
    ticket: Optional[ZendeskTicket],
    comments: List[ZendeskComment],
    summary_style: str = "standard"
) -> str:
    """Construct prompt for Gemini to generate a structured ticket summary."""
    transcript = format_conversation_transcript(ticket, comments)

    style_instructions = {
        "brief": "Keep the executive summary to 1 concise sentence and limit actions/action items to top 2 bullet points.",
        "action_only": "Focus heavily on actionable next steps, pending customer questions, and blocking issues.",
        "detailed": "Provide a comprehensive breakdown with all attempted solutions, error details, and diagnostic timeline.",
        "standard": "Provide a balanced, clear summary highlighting the root issue, actions taken, current status, and next steps.",
    }.get(summary_style.lower(), "Provide a balanced, clear summary.")

    json_schema_example = json.dumps(
        {
            "executive_summary": "High level 1-2 sentence overview of the ticket situation.",
            "customer_issue": "Specific root problem reported by the customer.",
            "actions_taken": [
                "Step 1: Customer reported error 403 on login.",
                "Step 2: Agent verified account was suspended.",
                "Step 3: Agent re-activated account and requested login re-try."
            ],
            "current_status": "Awaiting customer confirmation",
            "action_items": [
                "Follow up if customer does not reply within 24 hours",
                "Check server logs for recurring auth failure if issue persists"
            ],
            "sentiment": "frustrated"
        },
        indent=2
    )

    prompt = f"""You are an expert Zendesk Customer Support Operations AI Assistant.
Analyze the following customer support ticket and chronological conversation history, then produce a clear, high-value structured summary for support agents and team leads.

### Style Instruction:
{style_instructions}

### Requirements:
1. Distinguish between customer messages, agent public replies, and private internal notes.
2. Accurately identify the customer's actual pain point or technical issue.
3. Detail all key troubleshooting steps or actions that have already occurred.
4. Assess the customer sentiment: choose one of ["positive", "neutral", "frustrated", "urgent"].
5. Extract concrete action items / next steps for the agent.
6. Output MUST BE strictly valid JSON matching the schema below without any markdown code fence wrapping or backticks.

### JSON Schema & Example:
{json_schema_example}

### Support Ticket Conversation:
{transcript}

### JSON Output:"""
    return prompt


def build_raw_text_prompt(
    text: str,
    subject: Optional[str] = None,
    summary_style: str = "standard"
) -> str:
    """Construct prompt for Gemini to summarize arbitrary support conversation text."""
    style_instructions = {
        "brief": "Keep the executive summary to 1 concise sentence and limit actions/action items to top 2 bullet points.",
        "action_only": "Focus heavily on actionable next steps, pending customer questions, and blocking issues.",
        "detailed": "Provide a comprehensive breakdown with all attempted solutions, error details, and diagnostic timeline.",
        "standard": "Provide a balanced, clear summary.",
    }.get(summary_style.lower(), "Provide a balanced, clear summary.")

    json_schema_example = json.dumps(
        {
            "executive_summary": "High level 1-2 sentence overview of the ticket situation.",
            "customer_issue": "Specific root problem reported by the customer.",
            "actions_taken": ["Step 1..."],
            "current_status": "Open / In progress",
            "action_items": ["Action 1..."],
            "sentiment": "neutral"
        },
        indent=2
    )

    title_part = f"Subject: {subject}\n" if subject else ""

    prompt = f"""You are an expert Zendesk Customer Support Operations AI Assistant.
Analyze the following customer support conversation text, then produce a clear, high-value structured summary.

### Style Instruction:
{style_instructions}

### Requirements:
1. Accurately identify the customer's actual pain point or question.
2. Detail all key troubleshooting steps or actions that have already occurred.
3. Assess the customer sentiment: choose one of ["positive", "neutral", "frustrated", "urgent"].
4. Extract concrete action items / next steps.
5. Output MUST BE strictly valid JSON matching the schema below.

### JSON Schema & Example:
{json_schema_example}

### Conversation Text:
{title_part}{text}

### JSON Output:"""
    return prompt
