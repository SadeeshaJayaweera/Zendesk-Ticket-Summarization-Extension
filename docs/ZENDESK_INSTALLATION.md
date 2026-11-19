# Zendesk Integration & Installation Guide

This guide covers end-to-end deployment of the **Zendesk Support Intelligence Platform** within your Zendesk instance, including ZAF v2 sidebar app installation, API credential provisioning, and automated ticket solve trigger webhooks.

---

## 1. Zendesk API Credentials Provisioning

To enable the backend to read tickets, comments, and publish internal notes:

1. In Zendesk Admin Center, navigate to **Apps and integrations** > **Zendesk API**.
2. Under the **Settings** tab:
   * Enable **Token Access**.
   * Click **Add API token**.
   * Label: `Support Intelligence Backend`.
   * Copy the token value immediately (it is only shown once).
3. Set your environment variables:
   ```env
   ZENDESK_SUBDOMAIN=yourcompany
   ZENDESK_EMAIL=admin@yourcompany.com
   ZENDESK_API_TOKEN=your_copied_api_token
   ```

---

## 2. Packaging the ZAF v2 Sidebar App

The sidebar extension is packaged using the validated packager script:

```bash
cd zendesk-app
python3 package_app.py
```
This generates the compliant ZIP archive:
`zendesk-app/dist/zendesk-ticket-summarizer.zip`

---

## 3. Uploading to Zendesk Admin Center

1. Navigate to **Admin Center** > **Apps and integrations** > **Zendesk Support apps**.
2. Click **Upload private app** (top right).
3. **App Name**: `AI Support Intelligence Platform`.
4. **App file**: Choose `zendesk-app/dist/zendesk-ticket-summarizer.zip`.
5. In installation parameters:
   * **Backend Service URL (`backendUrl`)**: Enter the public HTTPS URL of your deployed backend (e.g. `https://api.support-intel.yourdomain.com`).
6. Click **Install**.

---

## 4. Automated Solve Webhook & Trigger Setup

To automatically draft AI summaries when tickets are solved:

### Step 1: Create the Webhook Target
1. Go to **Admin Center** > **Apps and integrations** > **Webhooks**.
2. Click **Create webhook**.
3. **Name**: `Support Intelligence Solved Trigger`.
4. **Endpoint URL**: `https://api.support-intel.yourdomain.com/webhooks/zendesk/ticket-status-changed`.
5. **Request method**: `POST`.
6. **Request format**: `JSON`.
7. **Authentication**: None or Bearer Token.

### Step 2: Create the Trigger
1. Go to **Admin Center** > **Objects and rules** > **Business rules** > **Triggers**.
2. Click **Add trigger**.
3. **Trigger Name**: `AI Support Intelligence: Pre-Draft Summary on Solved`.
4. **Conditions**:
   * *Status Changed to Solved*
5. **Actions**:
   * *Notify webhook*: `Support Intelligence Solved Trigger`.
   * **JSON Body**:
```json
{
  "ticket": {
    "id": "{{ticket.id}}",
    "subject": "{{ticket.subject}}",
    "status": "{{ticket.status}}",
    "priority": "{{ticket.priority}}",
    "requester": {
      "name": "{{ticket.requester.name}}",
      "email": "{{ticket.requester.email}}"
    }
  },
  "event_id": "{{ticket.id}}-{{ticket.updated_at_with_timestamp}}"
}
```
6. Click **Save**.
