"""Tests for Authentication, RBAC, and Analytics endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from zendesk_summarizer_shared.models import UserRole


@pytest.fixture
def client():
    """TestClient instance."""
    return TestClient(app)


def test_register_user_endpoint(client):
    """Test POST /api/auth/register."""
    payload = {
        "email": "agent@example.com",
        "password": "SecurePassword123!",
        "full_name": "Support Agent Alex",
        "organization_id": "org_test",
        "role": UserRole.SUPPORT_AGENT.value,
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "support_agent"
    assert data["organization_id"] == "org_test"


def test_login_user_endpoint(client):
    """Test POST /api/auth/login."""
    payload = {
        "email": "agent@example.com",
        "password": "SecurePassword123!",
    }
    resp = client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "support_agent"


def test_get_current_user_profile_unauthenticated(client):
    """Test GET /api/auth/me without authorization token."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert "summarize" in data["permissions"]


def test_get_current_user_profile_authenticated(client):
    """Test GET /api/auth/me with bearer access token."""
    login_resp = client.post("/api/auth/login", json={"email": "lead@example.com", "password": "pass"})
    token = login_resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["email"] == "lead@example.com"


def test_analytics_overview_endpoint(client):
    """Test GET /api/analytics/overview."""
    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_summaries_generated" in data
    assert "estimated_ai_expenditure_usd" in data
    assert "top_categories" in data
    assert "escalation_trends" in data
    assert data["ai_provider_availability_pct"] >= 99.0


def test_analytics_export_csv_endpoint(client):
    """Test GET /api/analytics/export/csv."""
    resp = client.get("/api/analytics/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in resp.headers["content-disposition"]
    text = resp.text
    assert "Metric,Value,Unit" in text
    assert "Total Summaries Generated" in text
    assert "Notes Posted to Zendesk" in text
