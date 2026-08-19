# Zendesk Ticketing REST API & Gemini Integration Notes

This document provides verified API specifications and contracts for Zendesk REST API endpoints and Gemini API calls used in `zendesk-ticket-summarizer`.

---

## 1. Zendesk API Authentication

Zendesk Ticketing API endpoints require authentication on all requests.

### Basic Authentication Scheme (API Token)
* **Username Format:** `{email_address}/token`
* **Password:** `{api_token}`
* **Header Format:**
  ```http
  Authorization: Basic <base64(email/token:api_token)>
  Content-Type: application/json
  Accept: application/json
  ```

### Base URL
All API requests are sent to the Zendesk instance domain:
```
https://{subdomain}.zendesk.com
```

### Python Header Construction Example
```python
import base64

auth_str = f"{email}/token:{api_token}"
auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
headers = {
    "Authorization": f"Basic {auth_bytes}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
```

---

## 2. Core Zendesk Endpoints

### 2.1 List Tickets
* **Method:** `GET`
* **Path:** `/api/v2/tickets.json`
* **Query Parameters:**
  * `per_page`: Number of tickets per page (e.g. `?per_page=5` or `?per_page=1`)
  * `page`: Page number (offset-based) or cursor pagination (`page[size]=10`)
* **Sample Response:**
```json
{
  "tickets": [
    {
      "id": 12345,
      "url": "https://example.zendesk.com/api/v2/tickets/12345.json",
      "subject": "Help with account login",
      "description": "I cannot sign into my portal...",
      "status": "open",
      "priority": "normal",
      "requester_id": 987654,
      "submitter_id": 987654,
      "assignee_id": 112233,
      "created_at": "2026-08-18T10:00:00Z",
      "updated_at": "2026-08-18T10:15:00Z"
    }
  ],
  "count": 1,
  "next_page": null,
  "previous_page": null
}
```

---

### 2.2 List Ticket Comments
* **Method:** `GET`
* **Path:** `/api/v2/tickets/{ticket_id}/comments.json`
* **Description:** Retrieves all comments (conversation history) associated with a ticket, in chronological order.
* **Key Fields Returned:**
  * `id`: Comment unique ID.
  * `type`: "Comment".
  * `author_id`: User ID of who wrote the comment.
  * `body`: Plain text body.
  * `html_body`: HTML representation.
  * `plain_body`: Plain text with formatting removed.
  * `public`: Boolean indicating comment visibility.
  * `attachments`: List of attachment objects.
  * `created_at`: Timestamp.

* **Sample Response:**
```json
{
  "comments": [
    {
      "id": 1001,
      "type": "Comment",
      "author_id": 987654,
      "body": "I am having trouble resetting my password.",
      "public": true,
      "created_at": "2026-08-18T10:00:00Z"
    },
    {
      "id": 1002,
      "type": "Comment",
      "author_id": 112233,
      "body": "Verified account ownership. Generating reset link.",
      "public": false,
      "created_at": "2026-08-18T10:10:00Z"
    }
  ],
  "count": 2
}
```

---

### 2.3 Create Ticket Comment / Internal Note
* **Method:** `PUT`
* **Path:** `/api/v2/tickets/{ticket_id}.json`
* **Headers:** `Content-Type: application/json`

#### Public Reply vs Internal Note (CRITICAL DISTINCTION)
The `public` boolean parameter on the `comment` payload strictly dictates visibility:

| `public` Value | Comment Type | Visibility | Use Case |
|---|---|---|---|
| `false` | **Internal Note (Private)** | Visible **ONLY** to agents and admins. Customer never sees this. | AI Summary posting, internal triage notes, agent collaboration. |
| `true` | **Public Reply** | Visible to the end-user (ticket requester) via email / portal. | Customer-facing responses. |

> **IMPORTANT:** For AI ticket summarization, notes MUST always be posted with `"public": false` so that the internal summary is never inadvertently exposed to the customer.

#### Request Payload for Internal Note (AI Summary):
```json
{
  "ticket": {
    "comment": {
      "body": "🤖 **AI Ticket Summary**:\n- **Issue**: User locked out after 3 failed password attempts.\n- **Resolution**: Reset token issued.\n- **Status**: Awaiting customer confirmation.",
      "public": false
    }
  }
}
```

#### Request Payload for Public Reply:
```json
{
  "ticket": {
    "comment": {
      "body": "Hello, we have sent password reset instructions to your email.",
      "public": true
    }
  }
}
```

#### API Constraints:
* **Single Comment Limit:** Only one comment object can be submitted per `PUT` request.
* **Maximum Comments:** A ticket supports up to 5,000 comments. Beyond that, the API responds with HTTP 422.

---

## 3. Gemini API Endpoint Specification

For generating ticket summaries, the project calls Google Gemini's REST API.

### Endpoint
* **Method:** `POST`
* **URL:** `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}`
* **Default Model:** `gemini-1.5-flash` or `gemini-2.0-flash`
* **Headers:** `Content-Type: application/json`

### Request Payload
```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "You are a Zendesk support assistant. Summarize the following customer support ticket history into concise bullet points..."
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.2,
    "maxOutputTokens": 500
  }
}
```

### Response Structure
```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "Summary text here..."
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP"
    }
  ]
}
```

---

## 4. Rate Limiting and Error Handling

1. **Zendesk API Rate Limits:**
   * Standard accounts: 700 requests/minute.
   * Rate limit response header: `Retry-After: <seconds>`, HTTP 429 Too Many Requests.
2. **Gemini API Rate Limits:**
   * Pay-as-you-go / Free tier RPM/TPM limits according to Google AI Studio quotas.
3. **Error Status Codes to Handle:**
   * `401 Unauthorized`: Invalid Zendesk API token or `{email}/token` format.
   * `403 Forbidden`: Insufficient permissions or agent role restrictions.
   * `404 Not Found`: Subdomain or ticket ID does not exist.
   * `422 Unprocessable Entity`: Maximum comment limit reached or invalid field values.
   * `429 Too Many Requests`: Rate limit exceeded, back off with `Retry-After`.
