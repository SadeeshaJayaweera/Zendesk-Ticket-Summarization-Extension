# Troubleshooting & Operational Runbook

This runbook documents common operational errors, diagnostic procedures, and resolution playbooks for the **Zendesk Support Intelligence Platform**.

---

## 1. Zendesk API Authentication Errors (HTTP 401 / 403)

### Symptom
Backend logs indicate:
`ZendeskAuthError: [401] Invalid credentials provided for Zendesk API`

### Root Cause
1. `ZENDESK_EMAIL` does not have `/token` suffix or the Zendesk API Token is invalid or expired.
2. The user account does not have Admin or Agent permissions to view the ticket.

### Remediation
1. Verify `ZENDESK_EMAIL` and `ZENDESK_API_TOKEN` in `.env`. The client automatically appends `/token` if omitted.
2. Test credentials using curl:
   ```bash
   curl -u "agent@company.com/token:your_token" "https://yourcompany.zendesk.com/api/v2/users/me.json"
   ```

---

## 2. Webhook Signature Verification Failures (HTTP 401)

### Symptom
Inbound webhook returns `401 Unauthorized` with body:
`{"detail": "Webhook HMAC signature mismatch or timestamp skew"}`

### Root Cause
1. `ZENDESK_WEBHOOK_SECRET` does not match the secret key configured in Zendesk Admin Center.
2. The server clock is out of sync with NTP by more than 300 seconds.

### Remediation
1. Copy the webhook secret key from Zendesk Admin Center > Webhooks > Edit Webhook > Secret Key.
2. Verify system clock synchronization:
   ```bash
   timedatectl status
   ```

---

## 3. AI Provider Quota Exhaustion & Rate Limits (HTTP 429)

### Symptom
Generation requests fail with `AIProviderRateLimitError: Rate limit reached on gemini-1.5-flash`.

### Remediation
1. The platform automatically attempts the next provider in the fallback chain (`Groq`, `OpenAI`, `Claude`).
2. If all providers are exhausted:
   * Verify your billing account in Google Cloud / Google AI Studio.
   * Add a secondary API key for Groq (`GROQ_API_KEY`) or OpenAI (`OPENAI_API_KEY`).
   * Switch the primary provider in `.env`:
     ```env
     LLM_PROVIDER=groq
     GROQ_MODEL=llama-3.3-70b-versatile
     ```

---

## 4. Database Connection & Migration Issues

### Symptom
`OperationalError: Connection to database failed` or `Table does not exist`

### Remediation
1. Verify database service is running:
   ```bash
   docker compose ps postgres
   ```
2. Apply pending migrations:
   ```bash
   alembic upgrade head
   ```

---

## 5. ZAF v2 Sidebar Iframe Rendering / CORS Issues

### Symptom
The sidebar in Zendesk Agent Workspace shows "Backend Offline" or browser console reports:
`Access to fetch at 'http://localhost:8000/health' blocked by CORS policy`

### Remediation
1. Ensure the backend URL in Zendesk App settings uses `https://` (Zendesk requires secure HTTPS origins in Agent Workspace).
2. For local testing, use a secure tunnel such as Cloudflare Tunnel or ngrok:
   ```bash
   ngrok http 8000
   ```
3. Update `backendUrl` in Zendesk Admin Center > Apps > AI Support Intelligence > Settings with the tunnel URL.
