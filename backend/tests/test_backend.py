"""Tests for FastAPI backend application."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_root_endpoint():
    """Test the root endpoint status payload."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "zendesk-ticket-summarizer-backend"
    assert data["status"] == "online"


def test_health_endpoint():
    """Test health check endpoint structure."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "zendesk_configured" in data
    assert "gemini_configured" in data
    assert "gemini_model" in data
