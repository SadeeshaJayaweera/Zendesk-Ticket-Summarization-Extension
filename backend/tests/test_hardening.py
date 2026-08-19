"""Unit and integration tests for production hardening (metrics, rate limiting, audit logging)."""

import asyncio
import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service, get_settings
from zendesk_summarizer_shared.audit_logger import AuditLogger
from zendesk_summarizer_shared.config import Settings
from zendesk_summarizer_shared.metrics import MetricsCollector, get_metrics_collector
from zendesk_summarizer_shared.rate_limiter import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    get_rate_limiter,
)


@pytest.fixture
def client():
    test_client = TestClient(app)
    yield test_client


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset rate limiter and metrics between tests."""
    limiter = get_rate_limiter()
    limiter.clear()
    metrics = get_metrics_collector()
    metrics.reset()
    yield
    limiter.clear()
    metrics.reset()


def test_metrics_endpoint(client):
    """Test GET /metrics returns expected operational counters."""
    metrics = get_metrics_collector()
    metrics.record_summary_generated(style="brief", provider="gemini")
    metrics.record_note_posted()
    metrics.record_webhook_received(status="pending_review")
    metrics.record_error("zendesk")

    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()

    assert data["service"] == "zendesk-ticket-summarizer"
    assert "uptime_seconds" in data
    assert data["summaries_generated"]["total"] >= 1
    assert data["summaries_generated"]["by_style"]["brief"] == 1
    assert data["notes_posted"]["total"] >= 1
    assert data["webhooks"]["total_received"] >= 1
    assert data["errors"]["by_category"]["zendesk"] == 1


def test_sliding_window_rate_limiter_logic():
    """Test SlidingWindowRateLimiter windowing and limit enforcement."""
    limiter = SlidingWindowRateLimiter(default_limit=3, window_seconds=2)

    # 3 allowed
    assert limiter.is_allowed("test-client")[0] is True
    assert limiter.is_allowed("test-client")[0] is True
    assert limiter.is_allowed("test-client")[0] is True

    # 4th blocked
    allowed, remaining, retry_after = limiter.is_allowed("test-client")
    assert allowed is False
    assert remaining == 0
    assert retry_after >= 1


def test_rate_limiting_endpoint_middleware(client):
    """Test endpoint returns HTTP 429 when rate limit exceeded."""
    from unittest.mock import AsyncMock
    from zendesk_summarizer_shared.models import SummarizeResponse, SummaryStructured

    mock_service = AsyncMock()
    mock_service.summarize_raw_text.return_value = SummarizeResponse(
        ticket_id=None,
        subject="Test",
        summary=SummaryStructured(
            executive_summary="Summary",
            customer_issue="Issue",
            actions_taken=[],
            current_status="Open",
            sentiment="neutral",
        ),
        markdown_note="Note",
        model_used="gemini-1.5-flash",
    )

    app.dependency_overrides[get_service] = lambda: mock_service
    app.dependency_overrides[get_settings] = lambda: Settings(
        RATE_LIMIT_PER_MINUTE=2,
        GEMINI_API_KEY="test-key",
    )

    # First 2 direct summarize requests should succeed
    r1 = client.post("/api/summarize-text", json={"text": "Test 1"})
    assert r1.status_code == 200

    r2 = client.post("/api/summarize-text", json={"text": "Test 2"})
    assert r2.status_code == 200

    # 3rd request should hit HTTP 429
    r3 = client.post("/api/summarize-text", json={"text": "Test 3"})
    assert r3.status_code == 429
    data = r3.json()
    assert data["error"] == "RateLimitExceeded"
    assert "Retry-After" in r3.headers

    app.dependency_overrides.clear()



def test_sqlite_audit_logger_wal_concurrency():
    """Test SQLite audit logger with concurrent writes under WAL mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_audit.db")
        audit_logger = AuditLogger(db_path=db_file)

        # Write 20 sequential events
        for i in range(20):
            success = audit_logger.log_event(
                event_type="test_event",
                ticket_id=1000 + i,
                status="success",
                model_used="gemini-1.5-flash",
                details={"iteration": i},
            )
            assert success is True

        logs = audit_logger.query_recent_logs(limit=50)
        assert len(logs) == 20
        assert logs[0]["ticket_id"] == 1019
        assert logs[0]["details"]["iteration"] == 19
