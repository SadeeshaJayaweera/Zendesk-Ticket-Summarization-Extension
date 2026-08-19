# Zendesk Trigger & Webhook Automation Setup Guide

This guide details how to configure an automated **Zendesk Trigger + Webhook** to pre-draft AI ticket summaries when a ticket's status changes to **Solved** (or another status).

---

## 1. How the Automated Workflow Operates

```
Agent Solves Ticket (#1001)
       │
       ▼
Zendesk Trigger fires Webhook
       │  POST /webhooks/zendesk/ticket-status-changed
       │  (Signed with HMAC-SHA256 Secret)
       ▼
FastAPI Backend
       ├─ 1. Verifies X-Zendesk-Webhook-Signature
       ├─ 2. Fetches comment thread & generates structured summary
       └─ 3. Saves draft with status = "pending_review" in DraftStore
              ⚠️ DOES NOT auto-post to Zendesk (Preserves Human Review)
       │
       ▼
Agent opens Ticket #1001 in Sidebar App
       ├─ App detects pre-drafted summary waiting for review
       ├─ Shows "⚡ Pre-Drafted on Ticket Solve" notification banner
       ├─ Pre-fills editable draft note in markdown textarea
       └─ Agent performs one-click review & clicks "Post as Internal Note"
```

---

## 2. Step 1: Create the Webhook Target in Zendesk Admin Center

1. Log into your Zendesk instance as an administrator (`https://<subdomain>.zendesk.com/admin`).
2. Navigate to **Apps and integrations** > **Webhooks** > **Webhooks**.
3. Click **Create webhook** in the top right.
4. Select **Trigger or automation** and click **Next**.
5. Fill in the webhook settings:
   - **Name**: `AI Summarizer Solve Webhook`
   - **Endpoint URL**: `https://<your-backend-domain>/webhooks/zendesk/ticket-status-changed`
     *(For local development/testing, use your HTTPS ngrok tunnel URL, e.g. `https://xxxx.ngrok-free.app/webhooks/zendesk/ticket-status-changed`)*
   - **Request method**: `POST`
   - **Request format**: `JSON`
   - **Authentication**: `None`
6. Click **Create webhook**.
7. In the resulting webhook details page, click the **Secret key** tab (or copy the generated **Webhook Secret**).
8. Add the secret key to your backend `.env` file:
   ```bash
   ZENDESK_WEBHOOK_SECRET=your_copied_signing_secret_here
   ```
9. Restart/reload your backend service so it enforces HMAC-SHA256 signature verification.

---

## 3. Step 2: Create the Zendesk Trigger

1. In Zendesk Admin Center, navigate to **Objects and rules** > **Business rules** > **Triggers**.
2. Click **Add trigger**.
3. Configure the trigger details:
   - **Trigger name**: `AI Summarizer: Pre-draft Summary on Solved`
   - **Description**: `Triggers the AI summarization backend when a ticket status changes to Solved.`
4. **Conditions** (Meet ALL of the following conditions):
   - `Ticket` > `Status` | `Changed to` | `Solved`
   - `Ticket` > `Update via` | `Is not` | `Web service (API)` *(Prevents any potential recursion)*
5. **Actions**:
   - Select **Notify active webhook**.
   - Choose your webhook: `AI Summarizer Solve Webhook`.
   - In **JSON payload**, paste the following template:
     ```json
     {
       "ticket": {
         "id": "{{ticket.id}}",
         "status": "{{ticket.status}}",
         "subject": "{{ticket.title}}"
       }
     }
     ```
6. Click **Save**.

---

## 4. Step 3: Test and Verify the Automated Flow

### A. Simulate Ticket Solve in Zendesk
1. Open an active test ticket with existing customer and agent conversation history.
2. In the ticket bottom bar, change the status dropdown from `Open` to `Solved` and submit.
3. Zendesk executes the trigger and sends an HMAC-signed POST request to your backend.

### B. Inspect Backend Logs
The backend logs will show:
```
INFO: Verified Zendesk webhook signature for ticket #1001
INFO: Generated AI summary (model: gemini-1.5-flash)
INFO: Stored draft with status='pending_review' in DraftStore
```

### C. Verify in Zendesk Sidebar App
1. Refresh or reopen the solved ticket in Zendesk Agent Workspace.
2. Open the **AI Summarizer** sidebar app.
3. The app automatically detects the pending draft and displays:
   - **"⚡ Pre-Drafted Summary (Pending Review)"** banner.
   - Pre-filled editable markdown draft in the textarea.
   - Structured visual timeline and sentiment analysis.
4. Click **Post as Internal Note**.
5. The note is posted to the ticket thread as a private yellow internal note, and the draft is marked as resolved.

---

## 5. Security & Signature Verification Details

Every incoming webhook request is verified against the Zendesk signature headers:
- `X-Zendesk-Webhook-Signature`: Base64-encoded HMAC-SHA256 signature.
- `X-Zendesk-Webhook-Signature-Timestamp`: UTC timestamp of the request.

The backend computes:
```python
expected_sig = base64(hmac_sha256(secret, timestamp + raw_body))
```
If the signature fails verification or headers are missing, the endpoint rejects the request with **HTTP 401 Unauthorized** to protect against spoofing.
