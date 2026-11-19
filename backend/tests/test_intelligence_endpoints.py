"""Unit & integration tests for AI Support Intelligence REST endpoints."""

from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from zendesk_summarizer_shared.models import (
    EscalationBrief,
    KnowledgeBaseRecommendation,
    KnowledgeBaseResponse,
    ReplyDraft,
    ReplyDraftResponse,
    SentimentFrustrationAnalysis,
    ShiftHandoverNote,
    SimilarTicket,
    SimilarTicketsResponse,
    TicketClassification,
    TroubleshootingResponse,
    TroubleshootingSuggestion,
)


@pytest.fixture
def mock_service():
    """Mock TicketSummarizerService dependency."""
    return AsyncMock()


@pytest.fixture
def client(mock_service):
    """TestClient with overridden get_service dependency."""
    app.dependency_overrides[get_service] = lambda: mock_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_troubleshoot_endpoint(client, mock_service):
    """Test POST /api/tickets/{id}/troubleshoot."""
    mock_service.suggest_troubleshooting.return_value = TroubleshootingResponse(
        ticket_id=42,
        suggestions=[
            TroubleshootingSuggestion(
                step_number=1,
                problem_identified="Invalid SSL Handshake",
                supporting_evidence=["Error SEC_ERROR_EXPIRED_CERTIFICATE in client log"],
                recommended_investigation="Check cert-manager deployment and renew domain TLS cert.",
                expected_result="TLS certificate status shows valid and not expired.",
                alternative_investigation="Inspect ingress reverse proxy configuration.",
                escalation_criteria="Escalate to DevOps if cert renewal fails after 15 minutes."
            )
        ]
    )

    resp = client.post("/api/tickets/42/troubleshoot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == 42
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["problem_identified"] == "Invalid SSL Handshake"
    mock_service.suggest_troubleshooting.assert_called_once_with(42)


def test_draft_reply_endpoint(client, mock_service):
    """Test POST /api/tickets/{id}/draft-reply."""
    draft = ReplyDraft(
        tone="empathetic",
        draft_text="Hello Alex, I understand how frustrating this login blocker must be...",
        key_points_covered=["Apologized for disruption", "Provided cert status update"],
        requires_agent_review=True,
    )
    mock_service.draft_reply.return_value = ReplyDraftResponse(
        ticket_id=42,
        drafts=[draft],
        recommended_draft=draft,
    )

    resp = client.post("/api/tickets/42/draft-reply", json={"tone": "empathetic"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == 42
    assert len(data["drafts"]) == 1
    assert "frustrating" in data["recommended_draft"]["draft_text"]
    assert data["recommended_draft"]["requires_agent_review"] is True
    mock_service.draft_reply.assert_called_once_with(42, tone="empathetic")


def test_classify_endpoint(client, mock_service):
    """Test POST /api/tickets/{id}/classify."""
    mock_service.classify_ticket.return_value = TicketClassification(
        issue_category="Authentication",
        subcategory="SSO/SAML",
        product="Admin Portal",
        priority_recommendation="urgent",
        customer_impact="High",
        technical_complexity="moderate",
        required_department="Identity Support",
        confidence=0.95,
        rationale="Customer locked out after password reset.",
    )

    resp = client.post("/api/tickets/42/classify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["issue_category"] == "Authentication"
    assert data["priority_recommendation"] == "urgent"
    assert data["confidence"] == 0.95
    mock_service.classify_ticket.assert_called_once_with(42)


def test_sentiment_endpoint(client, mock_service):
    """Test POST /api/tickets/{id}/sentiment."""
    mock_service.analyze_sentiment_and_frustration.return_value = SentimentFrustrationAnalysis(
        overall_sentiment="frustrated",
        sentiment_score=-0.7,
        frustration_level="severe",
        repeated_unresolved_concerns=["Unable to work for 4 hours", "No response from previous ticket"],
        customer_dissatisfaction_triggers=["Repeated auth errors"],
        potential_churn_risk="high",
        explanation="Customer express urgent frustration regarding blocking issues.",
    )

    resp = client.post("/api/tickets/42/sentiment")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_sentiment"] == "frustrated"
    assert data["frustration_level"] == "severe"
    assert len(data["repeated_unresolved_concerns"]) == 2
    mock_service.analyze_sentiment_and_frustration.assert_called_once_with(42)


def test_escalation_brief_endpoint(client, mock_service):
    """Test POST /api/tickets/{id}/escalation-brief."""
    mock_service.generate_escalation_brief.return_value = EscalationBrief(
        ticket_id=42,
        overview="Critical database deadlock affecting transaction writes.",
        customer_impact="Operations completely blocked for Enterprise tier tenant.",
        technical_evidence=["Deadlock graph in Postgres pg_stat_activity logs."],
        previous_investigation=["Attempted restart of read-replica; issue persists on primary."],
        outstanding_questions=["Has migration 042 acquired exclusive locks?"],
        required_engineering_assistance="Database SRE intervention to kill blocked sessions.",
        markdown_brief="### 🚨 Engineering Escalation Brief\n\nCritical database deadlock...",
    )

    resp = client.post("/api/tickets/42/escalation-brief")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == 42
    assert "Escalation Brief" in data["markdown_brief"]
    mock_service.generate_escalation_brief.assert_called_once_with(42)


def test_shift_handover_endpoint(client, mock_service):
    """Test POST /api/tickets/{id}/shift-handover."""
    mock_service.generate_shift_handover.return_value = ShiftHandoverNote(
        ticket_id=42,
        summary_what_happened="Customer awaiting verification of restored access token.",
        what_has_been_investigated=["Refreshed tenant signing secret", "Validated LDAP user record"],
        what_is_resolved=["Certificate updated"],
        what_remains_unresolved=["User has not confirmed login from their workstation"],
        next_action_owner="US Shift Tier 2 Support",
        instructions_for_next_agent=["Follow up at 18:00 UTC if no reply received"],
        promised_commitments_and_deadlines=["Promise update before end of business"],
        markdown_note="### 📋 Shift Handover Note\n\n**Current Situation:** Customer awaiting...",
    )

    resp = client.post("/api/tickets/42/shift-handover")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == 42
    assert "Shift Handover Note" in data["markdown_note"]
    mock_service.generate_shift_handover.assert_called_once_with(42)


def test_knowledge_base_endpoint(client, mock_service):
    """Test GET /api/tickets/{id}/knowledge-base."""
    mock_service.recommend_knowledge_base.return_value = KnowledgeBaseResponse(
        ticket_id=42,
        query_extracted="SAML 403 Forbidden Error",
        recommendations=[
            KnowledgeBaseRecommendation(
                title="Resolving SAML 403 Forbidden Errors",
                url="https://support.example.com/hc/articles/123",
                snippet="Guide on SAML certificate updates.",
                relevance_explanation="Addresses 403 Forbidden on SSO authentication.",
            )
        ]
    )

    resp = client.get("/api/tickets/42/knowledge-base")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == 42
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["title"] == "Resolving SAML 403 Forbidden Errors"
    mock_service.recommend_knowledge_base.assert_called_once_with(42)


def test_similar_tickets_endpoint(client, mock_service):
    """Test GET /api/tickets/{id}/similar-tickets."""
    mock_service.find_similar_tickets.return_value = SimilarTicketsResponse(
        ticket_id=42,
        similar_tickets=[
            SimilarTicket(
                ticket_id=20,
                subject="User locked out with 403",
                status="solved",
                similarity_score=0.92,
                shared_symptoms=["Same 403 Forbidden symptom"],
                resolution_summary="Renewed SAML certificate in IdP console.",
            )
        ]
    )

    resp = client.get("/api/tickets/42/similar-tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == 42
    assert len(data["similar_tickets"]) == 1
    assert data["similar_tickets"][0]["ticket_id"] == 20
    mock_service.find_similar_tickets.assert_called_once_with(42)


def test_summary_profiles_endpoint(client):
    """Test GET /api/summary-profiles listing all standard profiles."""
    resp = client.get("/api/summary-profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    keys = [p["id"] for p in data]
    assert "standard" in keys
    assert "technical" in keys
    assert "complaint" in keys
    assert "handover" in keys
    assert "escalation" in keys
    assert "bug" in keys
    assert "billing" in keys
    assert "integration" in keys
    assert "success" in keys
    assert "management" in keys
