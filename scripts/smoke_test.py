#!/usr/bin/env python3
"""Connectivity Smoke Test Script for Zendesk Ticket Summarizer.

Validates:
1. Zendesk REST API authentication (Basic Auth {email}/token:{api_token})
   and ability to query GET /api/v2/tickets.json.
2. Google Gemini API connectivity and ability to generate content with a trivial prompt.

Usage:
  python scripts/smoke_test.py
  or:
  poetry run python scripts/smoke_test.py
"""

import sys
import os
import httpx

# Ensure shared package is importable when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))

from zendesk_summarizer_shared.config import get_settings


def verify_zendesk_connectivity(settings) -> bool:
    """Test connectivity and authentication against Zendesk REST API."""
    print("=" * 60)
    print("🔍 [1/2] Testing Zendesk REST API Connectivity...")
    print("=" * 60)

    if not settings.is_zendesk_configured:
        print("❌ Zendesk configuration is incomplete.")
        print("   Required environment variables or .env keys:")
        print(f"   - ZENDESK_SUBDOMAIN : {'SET' if settings.zendesk_subdomain else 'MISSING'}")
        print(f"   - ZENDESK_EMAIL     : {'SET' if settings.zendesk_email else 'MISSING'}")
        print(f"   - ZENDESK_API_TOKEN : {'SET' if settings.zendesk_api_token.get_secret_value() else 'MISSING'}")
        print("   Please check your .env file or environment variables.")
        return False

    url = f"{settings.zendesk_base_url}/api/v2/tickets.json"
    headers = {
        "Authorization": settings.zendesk_auth_header,
        "Accept": "application/json",
        "User-Agent": "ZendeskTicketSummarizer-SmokeTest/0.1.0",
    }
    params = {"per_page": 1}

    print(f"   Target URL : {url}")
    print(f"   Subdomain  : {settings.zendesk_subdomain}")
    print(f"   Auth User  : {settings.zendesk_email}/token")

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers, params=params)

        print(f"   HTTP Status: {response.status_code} {response.reason_phrase}")

        if response.status_code == 200:
            data = response.json()
            tickets = data.get("tickets", [])
            count = data.get("count", len(tickets))
            print(f"✅ Zendesk API Authentication Succeeded!")
            print(f"   Total Tickets Accessible: {count}")
            if tickets:
                sample = tickets[0]
                print(f"   Sample Ticket ID: #{sample.get('id')} - Subject: '{sample.get('subject')}'")
            else:
                print("   (No tickets currently in Zendesk account, but API query succeeded)")
            return True
        elif response.status_code == 401:
            print("❌ Authentication Failed (401 Unauthorized).")
            print("   Please verify ZENDESK_EMAIL and ZENDESK_API_TOKEN.")
            return False
        elif response.status_code == 404:
            print(f"❌ Subdomain not found (404). Check ZENDESK_SUBDOMAIN: '{settings.zendesk_subdomain}'")
            return False
        else:
            print(f"❌ Unexpected response from Zendesk: {response.status_code}\n   {response.text}")
            return False

    except httpx.RequestError as exc:
        print(f"❌ Network or connection error contacting Zendesk: {exc}")
        return False


def verify_gemini_connectivity(settings) -> bool:
    """Test connectivity and inference against Google Gemini API."""
    print("\n" + "=" * 60)
    print("🤖 [2/2] Testing Google Gemini API Connectivity...")
    print("=" * 60)

    if not settings.is_gemini_configured:
        print("❌ Gemini configuration is missing.")
        print("   Required environment variable / .env key: GEMINI_API_KEY")
        return False

    api_key = settings.gemini_api_key.get_secret_value().strip()
    model = settings.gemini_model or "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": api_key}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Respond with a single word: 'CONNECTED'"}
                ]
            }
        ]
    }

    print(f"   Model      : {model}")
    print(f"   Endpoint   : {url.split('?')[0]}")

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, params=params, json=payload)

        print(f"   HTTP Status: {response.status_code} {response.reason_phrase}")

        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                print(f"✅ Gemini API Call Succeeded!")
                print(f"   Response Output: {text}")
                return True
            else:
                print(f"⚠️ Gemini responded with 200 OK but empty candidates: {data}")
                return False
        elif response.status_code in (400, 403):
            print(f"❌ Gemini API authentication / permission error ({response.status_code}):")
            print(f"   {response.text}")
            return False
        else:
            print(f"❌ Unexpected response from Gemini API: {response.status_code}\n   {response.text}")
            return False

    except httpx.RequestError as exc:
        print(f"❌ Network or connection error contacting Gemini API: {exc}")
        return False


def main():
    """Run both connectivity smoke tests and report overall status."""
    print("🚀 Starting Zendesk Ticket Summarizer Smoke Test Suite")
    settings = get_settings()

    zendesk_ok = verify_zendesk_connectivity(settings)
    gemini_ok = verify_gemini_connectivity(settings)

    print("\n" + "=" * 60)
    print("📊 Smoke Test Summary")
    print("=" * 60)
    print(f"   Zendesk REST API : {'✅ PASS' if zendesk_ok else '❌ FAIL'}")
    print(f"   Gemini API       : {'✅ PASS' if gemini_ok else '❌ FAIL'}")
    print("=" * 60)

    if zendesk_ok and gemini_ok:
        print("🎉 All connectivity smoke tests PASSED successfully!")
        sys.exit(0)
    else:
        print("⚠️ One or more smoke tests failed. Please verify credentials in .env.")
        sys.exit(1)


if __name__ == "__main__":
    main()
