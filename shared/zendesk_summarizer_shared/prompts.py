"""Prompt generation and templating for Zendesk Ticket Summarization & Support Intelligence.

Supports:
1. All 10 specialized summary profiles.
2. AI Troubleshooting Assistant.
3. AI Reply Drafting across professional, friendly, technical, empathetic, and concise tones.
4. Ticket Classification.
5. Customer Frustration & Sentiment Analysis.
6. Escalation Briefs and Shift Handover Notes.
"""

import json
from typing import Any, Dict, List, Optional
from zendesk_summarizer_shared.models import (
    ReplyTone,
    SummaryStyle,
    ZendeskComment,
    ZendeskTicket,
)

# Profile-specific instructions for the 10 summary types
SUMMARY_PROFILE_INSTRUCTIONS: Dict[str, str] = {
    SummaryStyle.STANDARD.value: (
        "Focus on providing a balanced, comprehensive operational summary covering original customer issue, "
        "business impact, troubleshooting attempted, confirmed root cause (or explicitly 'Undetermined' if unknown), "
        "current status, customer commitments, and next action items."
    ),
    SummaryStyle.TECHNICAL.value: (
        "Focus deeply on technical diagnostics, error messages, HTTP status codes, API endpoints, stack traces, "
        "reproduction steps, system logs, verified facts versus hypotheses, and concrete engineering next steps."
    ),
    SummaryStyle.COMPLAINT.value: (
        "Focus on the customer's grievances, dissatisfaction triggers, unmet expectations, impact on their business, "
        "frustration level, agent handling critique, broken commitments, and immediate de-escalation actions."
    ),
    SummaryStyle.HANDOVER.value: (
        "Focus on shift transition needs: exact status at handover, what was investigated this shift, what is "
        "blocked, what customer commitments/deadlines are pending, and step-by-step instructions for the oncoming agent."
    ),
    SummaryStyle.ESCALATION.value: (
        "Format as an executive/engineering escalation brief: why tier 1/2 could not resolve, customer contract tier "
        "and business impact, complete technical evidence gathered, and specific questions or actions requested from engineering."
    ),
    SummaryStyle.BUG.value: (
        "Format as a software bug investigation report: defect summary, affected software version/component, exact "
        "reproduction steps, expected vs actual behavior, error messages/logs, and potential workarounds."
    ),
    SummaryStyle.BILLING.value: (
        "Focus on financial details: invoice numbers, transaction IDs, disputed amounts, payment gateway errors, "
        "refund or credit requests, subscription tier status, and required finance team actions."
    ),
    SummaryStyle.INTEGRATION.value: (
        "Focus on 3rd-party integration failure: endpoint URLs, webhook delivery IDs, payload snippets, authentication "
        "failures, network latency/timeouts, partner service status, and API contract discrepancies."
    ),
    SummaryStyle.SUCCESS.value: (
        "Format from a Customer Success perspective: account health trajectory, product adoption friction, sentiment "
        "trend, feature requests or blockers, expansion signals, or churn risk warnings."
    ),
    SummaryStyle.MANAGEMENT.value: (
        "Format for executive leadership: 3-sentence high-level summary, operational business impact, customer risk, "
        "estimated time to resolution, and key organizational takeaways."
    ),
    SummaryStyle.BRIEF.value: (
        "Keep executive summary to 1 concise sentence and limit actions and action items to top 2 bullet points."
    ),
    SummaryStyle.ACTION_ONLY.value: (
        "Focus heavily on actionable next steps, pending customer questions, and blocking issues."
    ),
    SummaryStyle.DETAILED.value: (
        "Provide a comprehensive chronological breakdown of all attempted solutions, error details, and diagnostic timeline."
    ),
}


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
    summary_style: str = "standard",
    custom_instructions: Optional[str] = None,
) -> str:
    """Construct prompt for LLM to generate a structured ticket summary."""
    transcript = format_conversation_transcript(ticket, comments)
    style_key = summary_style.lower().strip()
    profile_guidance = SUMMARY_PROFILE_INSTRUCTIONS.get(style_key, SUMMARY_PROFILE_INSTRUCTIONS["standard"])

    custom_block = f"\n### Custom Organizational Instructions:\n{custom_instructions}\n" if custom_instructions else ""

    json_schema_example = json.dumps(
        {
            "executive_summary": "1-2 sentence high-level overview of the ticket situation.",
            "customer_issue": "Specific root problem reported by the customer.",
            "customer_expectations": "What the customer wants resolved.",
            "business_impact": "Operational impact on customer business.",
            "technical_symptoms": ["Error 504 Gateway Timeout on checkout API"],
            "attempted_troubleshooting": ["Verified pod status", "Checked Redis connection pool"],
            "root_cause": "Undetermined (Pending log verification) OR Confirmed root cause",
            "actions_taken": ["Customer reported error 504.", "Agent verified pod restart."],
            "current_status": "Awaiting customer confirmation",
            "commitments": ["Agent promised follow-up by 3:00 PM EST"],
            "deadlines": ["SLA breach in 2 hours"],
            "responsible_party": "Tier-2 Escalations",
            "action_items": ["Verify redis connection latency", "Update customer once logs analyzed"],
            "sentiment": "frustrated",
            "urgency_level": "high",
            "notes": ["Customer is on Tier-1 Enterprise plan"]
        },
        indent=2
    )

    prompt = f"""You are an expert Zendesk Customer Support Operations AI Assistant.
Analyze the following customer support ticket and conversation thread, then generate an accurate, high-value structured summary.

### Summary Profile ({style_key.upper()}):
{profile_guidance}
{custom_block}
### Strict Factual Grounding Rules:
1. NEVER invent or hallucinate information not present in the conversation.
2. Clearly distinguish CONFIRMED facts from HYPOTHESES.
3. If the root cause is not conclusively proven by evidence in the text, explicitly state: 'Undetermined'.
4. Do NOT pretend suggested actions were already performed.
5. Identify customer commitments and promised deadlines explicitly.
6. Output MUST BE strictly valid JSON matching the schema below without any markdown fences or commentary.

### JSON Schema & Example:
{json_schema_example}

### Support Ticket Conversation:
{transcript}

### JSON Output:"""
    return prompt


def build_raw_text_prompt(
    text: str,
    subject: Optional[str] = None,
    summary_style: str = "standard",
    custom_instructions: Optional[str] = None,
) -> str:
    """Construct prompt for LLM to summarize arbitrary support conversation text."""
    style_key = summary_style.lower().strip()
    profile_guidance = SUMMARY_PROFILE_INSTRUCTIONS.get(style_key, SUMMARY_PROFILE_INSTRUCTIONS["standard"])
    custom_block = f"\n### Custom Instructions:\n{custom_instructions}\n" if custom_instructions else ""

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
{profile_guidance}
{custom_block}
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


# --- Specialized Support Intelligence Prompts ---

def build_troubleshooting_prompt(context: str) -> str:
    """Build prompt for AI Troubleshooting Assistant."""
    return f"""You are a Principal Technical Support Engineer.
Analyze the following Zendesk ticket context and construct a prioritized, structured diagnostic investigation plan.

### Requirements:
1. For each diagnostic suggestion, provide:
   - problem_identified: specific symptom or subsystem failure
   - supporting_evidence: list of quotes or evidence from ticket
   - recommended_investigation: step-by-step technical check
   - expected_result: what a healthy system should output
   - alternative_investigation: fallback check if primary check fails
   - escalation_criteria: exact trigger when this must be escalated to dev/engineering
2. Ground all suggestions strictly in the evidence. Do NOT pretend any suggested action has already been performed.
3. Output strictly valid JSON matching this schema:
{{
  "ticket_id": 0,
  "suggestions": [
    {{
      "step_number": 1,
      "problem_identified": "...",
      "supporting_evidence": ["..."],
      "recommended_investigation": "...",
      "expected_result": "...",
      "alternative_investigation": "...",
      "escalation_criteria": "..."
    }}
  ],
  "confidence_score": 0.9,
  "disclaimer": "Recommendations generated based on ticket evidence. Actions have NOT been executed automatically."
}}

### Ticket Context:
{context}

### JSON Output:"""


def build_reply_drafting_prompt(context: str, tone: str = "professional") -> str:
    """Build prompt for AI Reply Drafting."""
    tone_guidance = {
        ReplyTone.PROFESSIONAL.value: "Warm, authoritative, courteous, clear, and reassuring.",
        ReplyTone.FRIENDLY.value: "Conversational, approachable, enthusiastic, and empathetic.",
        ReplyTone.TECHNICAL.value: "Precise, code/log focused, analytical, step-by-step diagnostic.",
        ReplyTone.EMPATHETIC.value: "Deeply apologetic for inconvenience, understanding, validating frustration, highly attentive.",
        ReplyTone.CONCISE.value: "Extremely direct, bulleted, no fluff, immediate resolution focus.",
    }.get(tone.lower(), "Professional and courteous.")

    return f"""You are an expert Customer Support Specialist drafting an email response to a customer.
Analyze the ticket history and write a response draft.

### Tone Style:
{tone_guidance}

### Rules:
1. NEVER send or imply the message has already been delivered.
2. Address all questions the customer raised.
3. Acknowledge commitments and provide realistic expectations.
4. Output strictly valid JSON matching this schema:
{{
  "ticket_id": 0,
  "drafts": [
    {{
      "tone": "{tone}",
      "draft_text": "Dear [Customer Name],\\n\\n...",
      "key_points_covered": ["Acknowledged outage", "Provided workaround"],
      "requires_agent_review": true
    }}
  ],
  "recommended_draft": {{
    "tone": "{tone}",
    "draft_text": "...",
    "key_points_covered": ["..."],
    "requires_agent_review": true
  }}
}}

### Ticket Context:
{context}

### JSON Output:"""


def build_ticket_classification_prompt(context: str) -> str:
    """Build prompt for Ticket Classification and Routing."""
    return f"""You are a Customer Support Triage Specialist.
Analyze the ticket conversation and classify it for routing and prioritization.

### Output JSON Schema:
{{
  "issue_category": "e.g. Authentication | Billing | Bug | Feature Request | Infrastructure | Integration",
  "subcategory": "e.g. SAML SSO / Invoice Discrepancy / Webhook Timeout",
  "product": "Product name or component",
  "integration": "3rd party integration name (or null)",
  "priority_recommendation": "low | normal | high | urgent",
  "customer_impact": "e.g. Single User | Multiple Users | Mission-Critical Production Outage",
  "technical_complexity": "low | medium | high",
  "required_department": "Tier 1 Support | Tier 2 Escalations | DevOps | Billing | Security",
  "confidence": 0.95,
  "rationale": "Brief reason for classification"
}}

### Ticket Context:
{context}

### JSON Output:"""


def build_sentiment_analysis_prompt(context: str) -> str:
    """Build prompt for Customer Frustration & Sentiment Radar."""
    return f"""You are a Customer Experience and Churn Risk Analyst.
Analyze customer messages in this ticket to estimate sentiment and frustration trajectory.

### Output JSON Schema:
{{
  "overall_sentiment": "positive | neutral | negative | urgent",
  "sentiment_score": 0.0,
  "frustration_level": "none | low | moderate | severe | escalating",
  "repeated_unresolved_concerns": ["..."],
  "customer_dissatisfaction_triggers": ["..."],
  "potential_churn_risk": "low | medium | high",
  "churn_risk_indicators": ["..."],
  "explanation": "Clear explanation distinguishing facts from model estimates."
}}

### Ticket Context:
{context}

### JSON Output:"""


def build_escalation_brief_prompt(context: str) -> str:
    """Build prompt for Engineering Escalation Brief."""
    return f"""You are an Escalation Management Specialist.
Produce a comprehensive Escalation Brief for Engineering/Product on this unresolved ticket.

### Output JSON Schema:
{{
  "ticket_id": 0,
  "overview": "High level escalation summary",
  "customer_impact": "Operational impact on customer",
  "technical_evidence": ["Log snippets", "Error codes", "API requests"],
  "previous_investigation": ["Steps tier-1 support already executed"],
  "outstanding_questions": ["Specific engineering queries"],
  "timeline_milestones": [{{"time": "...", "event": "..."}}],
  "required_engineering_assistance": "Exact action requested from engineering",
  "urgency_level": "high",
  "markdown_brief": "Complete formatted Markdown brief"
}}

### Ticket Context:
{context}

### JSON Output:"""


def build_shift_handover_prompt(context: str) -> str:
    """Build prompt for Shift Handover Notes."""
    return f"""You are an Operations Lead preparing Shift Handover Notes for a re-assigned ticket.

### Output JSON Schema:
{{
  "ticket_id": 0,
  "summary_what_happened": "Summary of events up to this moment",
  "what_has_been_investigated": ["..."],
  "what_is_resolved": ["..."],
  "what_remains_unresolved": ["..."],
  "next_action_owner": "Name or team",
  "instructions_for_next_agent": ["Step 1...", "Step 2..."],
  "promised_commitments_and_deadlines": ["Promised follow-up by 4 PM UTC"],
  "markdown_note": "Scannable Markdown note for agent handover"
}}

### Ticket Context:
{context}

### JSON Output:"""
