"""Unit tests for zendesk_summarizer_shared.config."""

import base64
import os
import pytest
from zendesk_summarizer_shared.config import Settings


def test_settings_default():
    """Test default settings initialization without env vars."""
    s = Settings(
        ZENDESK_SUBDOMAIN="",
        ZENDESK_EMAIL="",
        ZENDESK_API_TOKEN="",
        GEMINI_API_KEY="",
    )
    assert s.is_zendesk_configured is False
    assert s.is_gemini_configured is False
    assert s.zendesk_base_url == ""
    assert s.zendesk_auth_header == ""
    assert s.gemini_model == "gemini-1.5-flash"


def test_settings_zendesk_auth_header():
    """Test Zendesk Basic Auth base64 formatting."""
    s = Settings(
        ZENDESK_SUBDOMAIN="mycompany",
        ZENDESK_EMAIL="support@mycompany.com",
        ZENDESK_API_TOKEN="token12345",
        GEMINI_API_KEY="gemini-test-key",
    )
    assert s.is_zendesk_configured is True
    assert s.is_gemini_configured is True
    assert s.zendesk_base_url == "https://mycompany.zendesk.com"
    
    # Expected auth: support@mycompany.com/token:token12345
    expected_creds = "support@mycompany.com/token:token12345"
    expected_header = "Basic " + base64.b64encode(expected_creds.encode("utf-8")).decode("utf-8")
    assert s.zendesk_auth_header == expected_header


def test_settings_subdomain_trimming():
    """Test subdomain trimming and lowercasing."""
    s = Settings(
        ZENDESK_SUBDOMAIN="  ACME-CORP  ",
        ZENDESK_EMAIL="agent@acme.com",
        ZENDESK_API_TOKEN="secret",
    )
    assert s.zendesk_base_url == "https://acme-corp.zendesk.com"
