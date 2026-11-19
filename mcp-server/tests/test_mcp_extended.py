"""Extended unit tests for new Support Intelligence MCP tools."""

from datetime import datetime
from unittest.mock import AsyncMock, patch
import pytest

from mcp_server.server import (
    analyze_sentiment,
    classify_ticket,
    draft_customer_reply,
    find_similar_tickets,
    generate_escalation_brief,
    generate_handover,
    generate_technical_summary,
    get_summary_history,
    get_ticket_conversation,
    get_ticket_details,
    search_knowledge_base,
    suggest_troubleshooting,
)
from zendesk_summarizer_shared.models import (
    EscalationBrief,
    KnowledgeBaseRecommendation,
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


@pytest.mark.asyncio
async def test_get_ticket_details_mcp():
    """Test get_ticket_details MCP tool."""
    mock_service = AsyncMock()
    ticket = Ticket(
        id=77,
        subject="VPN Auth Drop",
        description="User drops every 10 mins",
        status="open",
        priority="high",
        requester_id=12,
        assignee_id=34,
        organization_id=1,
        tags=["vpn", "network"],
        created_at=datetime(2026, 11, 1, 10, 0),
        updated_at=datetime(2026, 11, 1, 11, 0),
    )
    mock_service.get_ticket_details.return_value = TicketDetailResponse(
        ticket=ticket,
        comments=[],
        total_comments=0,
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await get_ticket_details("77")
        assert '"id": 77' in res
        assert '"subject": "VPN Auth Drop"' in res
        assert '"priority": "high"' in res


@pytest.mark.asyncio
async def test_generate_technical_summary_mcp():
    """Test generate_technical_summary MCP tool."""
    mock_service = AsyncMock()
    mock_service.summarize_ticket.return_value = SummarizeResponse(
        ticket_id=77,
        summary=SummaryStructured(
            executive_summary="VPN MTU mismatch.",
            customer_issue="Packets dropped on jumbo frames.",
            actions_taken=["Lowered MTU to 1420."],
            current_status="Testing connectivity",
            commitments=[],
            action_items=[],
            sentiment="neutral",
        ),
        markdown_note="### 🤖 AI Technical Troubleshooting Summary\nVPN MTU mismatch.",
        model_used="gemini-1.5-flash",
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await generate_technical_summary("77")
        assert "Technical Troubleshooting Summary" in res
        assert "VPN MTU mismatch" in res


@pytest.mark.asyncio
async def test_suggest_troubleshooting_mcp():
    """Test suggest_troubleshooting MCP tool."""
    mock_service = AsyncMock()
    mock_service.suggest_troubleshooting.return_value = TroubleshootingResponse(
        ticket_id=77,
        suggestions=[
            TroubleshootingSuggestion(
                step_number=1,
                problem_identified="Packet Fragmentation",
                supporting_evidence=["ping -s 1500 fails"],
                recommended_investigation="Set interface MTU to 1400",
                expected_result="Ping succeeds without fragmentation",
                alternative_investigation=None,
                escalation_criteria="Escalate to NetOps if interface driver drops packets",
            )
        ]
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await suggest_troubleshooting("77")
        assert "DIAGNOSTIC PROCEDURES FOR TICKET #77" in res
        assert "Packet Fragmentation" in res
        assert "Set interface MTU to 1400" in res


@pytest.mark.asyncio
async def test_draft_customer_reply_mcp():
    """Test draft_customer_reply MCP tool."""
    mock_service = AsyncMock()
    draft = ReplyDraft(
        tone="friendly",
        draft_text="Hey Alex! We adjusted your MTU settings. Could you try connecting now?",
        requires_agent_review=True,
    )
    mock_service.draft_reply.return_value = ReplyDraftResponse(
        ticket_id=77,
        drafts=[draft],
        recommended_draft=draft,
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await draft_customer_reply("77", tone="friendly")
        assert "DRAFT CUSTOMER REPLY (FRIENDLY)" in res
        assert "Could you try connecting now?" in res


@pytest.mark.asyncio
async def test_classify_and_sentiment_mcp():
    """Test classify_ticket and analyze_sentiment MCP tools."""
    mock_service = AsyncMock()
    mock_service.classify_ticket.return_value = TicketClassification(
        issue_category="Network",
        subcategory="VPN",
        product="Client",
        priority_recommendation="high",
        customer_impact="Medium",
        technical_complexity="complex",
        required_department="NetOps",
        confidence=0.91,
        rationale="MTU failure.",
    )
    mock_service.analyze_sentiment_and_frustration.return_value = SentimentFrustrationAnalysis(
        overall_sentiment="frustrated",
        sentiment_score=-0.5,
        frustration_level="moderate",
        repeated_unresolved_concerns=["Cannot connect remotely"],
        potential_churn_risk="low",
        explanation="User needs remote connectivity for work.",
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        c_res = await classify_ticket("77")
        assert '"issue_category": "Network"' in c_res
        assert '"required_department": "NetOps"' in c_res

        s_res = await analyze_sentiment("77")
        assert '"overall_sentiment": "frustrated"' in s_res
        assert '"frustration_level": "moderate"' in s_res


@pytest.mark.asyncio
async def test_search_knowledge_base_mcp():
    """Test search_knowledge_base MCP tool."""
    mock_service = AsyncMock()
    mock_service.zendesk.search_help_center.return_value = [
        KnowledgeBaseRecommendation(
            title="Optimizing VPN MTU Settings",
            url="https://help.example.com/vpn-mtu",
            snippet="Resolve packet drop issues by configuring client MTU.",
            relevance_explanation="Directly explains MTU troubleshooting.",
        )
    ]

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await search_knowledge_base("vpn mtu packet drop")
        assert "Found 1 article(s)" in res
        assert "Optimizing VPN MTU Settings" in res
        assert "https://help.example.com/vpn-mtu" in res


@pytest.mark.asyncio
async def test_get_summary_history_mcp():
    """Test get_summary_history MCP tool."""
    mock_service = AsyncMock()
    mock_service.get_ticket_history.return_value = TicketHistoryResponse(
        ticket_id=77,
        total=1,
        summaries=[
            TicketHistorySummaryItem(
                id=1,
                body="### Past Summary\nInitial report.",
                created_at=datetime(2026, 11, 1, 10, 30),
                author_id=10,
                is_internal=True,
            )
        ]
    )

    with patch("mcp_server.server._get_service", return_value=mock_service):
        res = await get_summary_history("77")
        assert "PAST SUMMARIES FOR TICKET #77" in res
        assert "Initial report." in res
