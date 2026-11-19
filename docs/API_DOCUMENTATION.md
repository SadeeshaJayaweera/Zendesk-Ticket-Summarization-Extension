# REST API Documentation: Zendesk Support Intelligence Platform

## 1. Overview & Base URLs

The Zendesk Support Intelligence Platform exposes an asynchronous REST API built with FastAPI. All endpoints return and accept JSON unless otherwise noted.

* **Base URL (Local Development)**: `http://localhost:8000`
* **Base URL (Production)**: `https://api.support-intel.yourdomain.com`
* **Interactive OpenAPI Swagger Docs**: `http://localhost:8000/docs`
* **Redoc Specification**: `http://localhost:8000/redoc`

---

## 2. Authentication & Security Headers

### Bearer Token Authentication
Agent Workspace and administrative requests can provide a JSON Web Token (JWT) in the `Authorization` header:
```http
Authorization: Bearer <eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...>
```

### Webhook Verification Headers
Inbound Zendesk webhooks must include:
* `X-Zendesk-Webhook-Signature`: Hex-encoded HMAC-SHA256 signature calculated over `<timestamp>.<request_body>` using `ZENDESK_WEBHOOK_SECRET`.
* `X-Zendesk-Webhook-Timestamp`: Unix epoch timestamp in seconds. Requests with timestamps older than 300 seconds are rejected to prevent replay attacks.

### Rate Limiting Headers
Every response includes sliding-window rate limit metadata:
* `X-RateLimit-Limit`: Maximum requests permitted per 60-second window (default: 60 or 120).
* `X-RateLimit-Remaining`: Requests remaining in the current window.
* `X-RateLimit-Reset`: Seconds remaining until quota reset.

---

## 3. Endpoints Catalog

### A. Health & System

#### `GET /health`
Returns system health, database readiness, and active AI model configurations.
* **Response `200 OK`**:
```json
{
  "status": "healthy",
  "service": "zendesk-ticket-summarizer-backend",
  "version": "1.0.0",
  "zendesk_configured": true,
  "gemini_configured": true,
  "groq_configured": true,
  "llm_provider": "gemini",
  "gemini_model": "gemini-1.5-flash",
  "active_model": "gemini-1.5-flash",
  "database_connected": true
}
```

#### `GET /metrics`
Returns operational metrics and counters (Prometheus-style telemetry).
* **Response `200 OK`**:
```json
{
  "total_summaries_generated": 142,
  "total_notes_posted": 118,
  "total_webhooks_processed": 49,
  "rate_limit_hits": 0,
  "uptime_seconds": 18450.2
}
```

---

### B. Ticket Intelligence Endpoints

#### `POST /api/tickets/{ticket_id}/summarize`
Generates a structured AI summary based on conversation history and selected profile.
* **Request Body**:
```json
{
  "summary_style": "standard",
  "custom_instructions": "Focus specifically on VPN connection drops and client operating system"
}
```
* **Supported Styles**: `standard`, `technical`, `complaint`, `handover`, `escalation`, `bug`, `billing`, `integration`, `success`, `management`, `brief`, `action_only`, `detailed`.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "subject": "VPN connection drops every 10 minutes",
  "model_used": "gemini-1.5-flash",
  "summary": {
    "executive_summary": "Customer VPN disconnects periodically due to MTU size mismatch on WAN interface.",
    "customer_issue": "VPN drops every 10 minutes while working remotely.",
    "actions_taken": [
      "Customer tested wired and Wi-Fi connections.",
      "Agent reviewed firewall session logs and identified fragmented UDP packets."
    ],
    "current_status": "Awaiting customer testing with MTU set to 1400",
    "commitments": [
      "Check in with customer within 24 hours if no reply received"
    ],
    "action_items": [
      "Verify packet logs after customer MTU modification"
    ],
    "sentiment": "frustrated",
    "summary_profile": "standard"
  },
  "markdown_note": "### 🤖 AI Ticket Summary\n**Executive Summary:** Customer VPN disconnects periodically...",
  "generated_at": "2026-11-19T12:00:00Z"
}
```

#### `POST /api/tickets/{ticket_id}/troubleshoot`
Analyzes conversation evidence and generates structured diagnostic steps.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "suggestions": [
    {
      "step_number": 1,
      "problem_identified": "Packet Fragmentation on WireGuard/IPsec Tunnel",
      "supporting_evidence": ["ping -s 1500 returns Message too long error in client terminal log"],
      "recommended_investigation": "Run path MTU discovery using 'ping -D -s 1400 gateway.vpn.corp'",
      "expected_result": "0% packet loss and no fragmentation errors",
      "alternative_investigation": "Temporarily clamp TCP MSS to 1360 in client adapter settings",
      "escalation_criteria": "Escalate to Network Operations if MTU reduction does not prevent tunnel renegotiation"
    }
  ],
  "confidence_score": 0.92,
  "disclaimer": "Recommendations generated based on ticket evidence. Actions have NOT been executed automatically."
}
```

#### `POST /api/tickets/{ticket_id}/draft-reply`
Drafts a context-grounded customer response with specified tone.
* **Request Body**:
```json
{
  "tone": "empathetic"
}
```
* **Supported Tones**: `professional`, `friendly`, `technical`, `empathetic`, `concise`.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "drafts": [
    {
      "tone": "empathetic",
      "draft_text": "Hello Alex,\n\nI understand how disruptive it is to have your VPN connection drop every 10 minutes while trying to work...",
      "key_points_covered": ["Acknowledged frustration", "Provided MTU instructions"],
      "requires_agent_review": true
    }
  ],
  "recommended_draft": {
    "tone": "empathetic",
    "draft_text": "Hello Alex,\n\nI understand how disruptive it is to have your VPN connection drop every 10 minutes while trying to work...",
    "requires_agent_review": true
  }
}
```

#### `POST /api/tickets/{ticket_id}/classify`
Classifies category, subcategory, product, complexity, and recommended priority.
* **Response `200 OK`**:
```json
{
  "issue_category": "Network & Connectivity",
  "subcategory": "Corporate VPN (WireGuard)",
  "product": "Desktop VPN Client v3.4",
  "priority_recommendation": "high",
  "customer_impact": "High (Customer unable to access internal code repositories)",
  "technical_complexity": "moderate",
  "required_department": "Tier 2 Network Operations",
  "confidence": 0.94,
  "rationale": "Directly impacts core work connectivity; symptom isolated to network layer MTU limits."
}
```

#### `POST /api/tickets/{ticket_id}/sentiment`
Evaluates customer frustration level, grievances, and churn risk.
* **Response `200 OK`**:
```json
{
  "overall_sentiment": "frustrated",
  "sentiment_score": -0.65,
  "frustration_level": "severe",
  "repeated_unresolved_concerns": [
    "VPN has dropped 8 times today",
    "Customer mentioned deadline on quarterly release"
  ],
  "customer_dissatisfaction_triggers": ["Repeated disconnects during video meetings"],
  "potential_churn_risk": "medium",
  "explanation": "Customer is blocked on critical deliverables; frustration has escalated over 2 days."
}
```

#### `POST /api/tickets/{ticket_id}/escalation-brief`
Generates a structured engineering escalation brief.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "overview": "Persistent MTU renegotiation drop across macOS Sonoma client fleet",
  "customer_impact": "Multiple engineers reporting disconnections during active SSH sessions",
  "technical_evidence": ["Client log dumps showing ICMP Type 3 Code 4 drops"],
  "previous_investigation": ["Verified endpoint certs; clamped TCP MSS on router"],
  "outstanding_questions": ["Did latest ISP transit provider alter backbone MTU?"],
  "required_engineering_assistance": "NetOps SRE inspection of transit tunnel MSS clamping",
  "markdown_brief": "### 🚨 Engineering Escalation Brief\n\n**Overview:** Persistent MTU renegotiation drop..."
}
```

#### `POST /api/tickets/{ticket_id}/shift-handover`
Generates shift handover notes with actions taken, pending items, and customer commitments.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "summary_what_happened": "Customer experienced frequent VPN drops; provided MTU reduction instructions.",
  "what_has_been_investigated": ["Log analysis completed", "MSS clamping verified"],
  "what_is_resolved": ["Configuration script provided to customer"],
  "what_remains_unresolved": ["Awaiting customer confirmation after applying script"],
  "next_action_owner": "APAC Shift Support Lead",
  "instructions_for_next_agent": ["Follow up with customer if no response by 04:00 UTC"],
  "promised_commitments_and_deadlines": ["Guaranteed resolution update within 4 hours"],
  "markdown_note": "### 📋 Shift Handover Note\n\n**Summary:** Customer experienced frequent VPN drops..."
}
```

#### `GET /api/tickets/{ticket_id}/knowledge-base`
Retrieves relevant Zendesk Help Center documentation articles.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "query_extracted": "WireGuard VPN MTU packet fragmentation troubleshooting",
  "recommendations": [
    {
      "article_id": 360012345,
      "title": "Configuring MTU Settings for Corporate VPN Connections",
      "url": "https://support.example.com/hc/en-us/articles/360012345",
      "relevance_explanation": "Provides step-by-step instructions on adjusting client MTU values for macOS and Windows.",
      "confidence_score": 0.95,
      "snippet": "Learn how to diagnose MTU packet drops and adjust network adapter settings."
    }
  ]
}
```

#### `GET /api/tickets/{ticket_id}/similar-tickets`
Finds historical resolved tickets sharing symptoms and identifies potential duplicates.
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "similar_tickets": [
    {
      "ticket_id": 84,
      "subject": "VPN connection drops every few minutes on fiber connection",
      "status": "solved",
      "similarity_score": 0.91,
      "shared_symptoms": ["Frequent VPN disconnects", "Jumbo frame packet drops"],
      "resolution_summary": "Set WAN adapter MTU to 1420.",
      "url": "https://example.zendesk.com/agent/tickets/84"
    }
  ],
  "potential_duplicates": []
}
```

---

### C. Note Publication & Staging

#### `POST /api/tickets/{ticket_id}/notes`
Posts a private internal note or public comment directly to the Zendesk ticket.
* **Request Body**:
```json
{
  "body": "### 🤖 AI Ticket Summary\nCustomer confirmed VPN issue resolved.",
  "public": false
}
```
* **Response `200 OK`**:
```json
{
  "ticket_id": 101,
  "is_public": false,
  "status": "success",
  "message": "Internal note posted successfully to ticket #101"
}
```

---

### D. Authentication & Administration

#### `POST /api/auth/register`
Registers a new user account within an organization.
* **Request Body**:
```json
{
  "email": "agent@example.com",
  "password": "StrongPassword123!",
  "full_name": "Jordan Smith",
  "organization_id": "org_default",
  "role": "support_agent"
}
```

#### `POST /api/auth/login`
Authenticates credentials and returns a signed JWT access token.
* **Request Body**:
```json
{
  "email": "agent@example.com",
  "password": "StrongPassword123!"
}
```
* **Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "user_id": "usr_998811aa",
  "role": "support_agent",
  "organization_id": "org_default"
}
```

---

### E. Analytics & Reporting

#### `GET /api/analytics/overview`
Retrieves aggregated operational metrics, cost estimates, and trend analytics.

#### `GET /api/analytics/export/csv`
Streams a comma-separated value (CSV) file containing operational intelligence metrics.
