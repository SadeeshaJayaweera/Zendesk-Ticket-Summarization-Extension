# Zendesk App Installation & Deployment Guide

This guide walks through packaging, uploading, configuring, and testing the **Zendesk Ticket Summarizer** sidebar application (`zendesk-app/`) in your Zendesk Support instance.

---

## 1. Architecture Overview

The Zendesk App is a thin client sidebar iframe powered by the **Zendesk Apps Framework (ZAF v2)**.

```
┌─────────────────────────────────────────────────────────────┐
│ Zendesk Agent Workspace (Ticket Sidebar)                    │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ AI Ticket Summarizer (ZAF v2 Iframe)                  │  │
│  │                                                       │  │
│  │ 1. Reads active ticket ID via ZAF SDK                │  │
│  │ 2. Sends request to Backend Service                  │  │
│  │ 3. Displays editable draft AI summary note            │  │
│  │ 4. Posts private internal note back to ticket         │  │
│  │ 5. Loads past AI summary history                      │  │
│  └───────────────┬───────────────────────────────────────┘  │
└──────────────────┼──────────────────────────────────────────┘
                   │ HTTPS JSON REST API
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Backend Service (/api/tickets/{id}/summarize)       │
│                                                             │
│  • Fetches comments via Zendesk API client                  │
│  • Builds structured context with speaker labels            │
│  • Executes AI Summarizer (Gemini 1.5 Flash / Groq)        │
│  • Posts internal notes with strict `public: false`         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

1. **Zendesk Admin Privileges**: You must have Admin permissions to upload private apps in Zendesk Admin Center.
2. **Backend Service Running**: The FastAPI backend service (`backend/`) must be deployed or accessible via a public HTTPS tunnel (e.g. ngrok, Cloudflare Tunnel, or production server).
3. **Python 3.10+ / Node.js 18+**: For running the packaging script.

---

## 3. Packaging the Zendesk App

Run the automated packager to validate files and build the release ZIP bundle:

```bash
cd zendesk-app
python3 package_app.py
```

Or using npm:

```bash
npm run package
```

The script produces:
```
zendesk-app/dist/zendesk-ticket-summarizer.zip
```

### Archive Structure Verification
The zip archive conforms strictly to Zendesk's app package schema:
```
zendesk-ticket-summarizer.zip
├── manifest.json
├── assets/
│   ├── index.html
│   ├── main.js
│   └── style.css
└── translations/
    └── en.json
```

---

## 4. Installing in Zendesk Admin Center

### Step 1: Open Admin Center
1. Log into your Zendesk instance: `https://<your-subdomain>.zendesk.com`.
2. Click the **Zendesk Products** icon in the top-right and select **Admin Center** (or go to `https://<your-subdomain>.zendesk.com/admin`).

### Step 2: Navigate to Support Apps
1. In the left navigation menu, click **Apps and integrations**.
2. Under **Apps**, select **Zendesk Support apps**.

### Step 3: Upload the Private App
1. Click the **Upload private app** button in the upper right corner.
2. Enter the **App Name**: `AI Ticket Summarizer`.
3. In **App file**, click **Choose file** and select `zendesk-app/dist/zendesk-ticket-summarizer.zip`.
4. Click **Upload**.

### Step 4: Configure App Settings
1. In the installation dialog, configure the **Backend Service URL** (`backendUrl`):
   - **Local Testing / Tunnel**: `https://<your-subdomain>.ngrok-free.app`
   - **Production Backend**: `https://api.yourdomain.com`
2. Configure role-based or group-based restrictions if desired (or allow all agents).
3. Click **Install**.

---

## 5. Local Development & Sandbox Testing

### Method A: Standalone Browser Preview
To test the UI layout, tabs, editor, and fallback mock behavior directly without running Zendesk:
1. Open `zendesk-app/assets/index.html` in any web browser.
2. The app detects the absence of ZAF and initializes **Standalone Dev Preview Mode**.

### Method B: Testing with ngrok Tunnel
When testing against a real Zendesk sandbox instance:
1. Start your FastAPI backend:
   ```bash
   cd backend
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Start an ngrok tunnel:
   ```bash
   ngrok http 8000
   ```
3. In Zendesk Admin Center > Zendesk Support apps > AI Ticket Summarizer > Change Settings:
   - Set **Backend Service URL** to your HTTPS ngrok URL (e.g. `https://xxxx.ngrok-free.app`).

### Method C: Testing with Zendesk Apps Tools (ZCLI)
If you have `@zendesk/zcli` installed:
```bash
cd zendesk-app
npx @zendesk/zcli apps:server
```
In your Zendesk Agent Workspace URL, append `?zat=true` (e.g., `https://<subdomain>.zendesk.com/agent/tickets/123?zat=true`) to load local assets.

---

## 6. End-to-End Verification Checklist

Verify the entire agent workflow:

1. **Open a Ticket**: Open any existing ticket in the Zendesk Agent Workspace.
2. **Open Sidebar App**: Click the **Apps** icon in the right-hand panel to view `AI Summarizer`.
3. **Verify Context**: Confirm the app correctly displays the Ticket ID `#<id>`, Status, Subject, and Requester.
4. **Choose Format & Summarize**:
   - Select a summary format (**Standard**, **Brief**, **Actions**, **Detailed**).
   - Click **Summarize Ticket**.
   - Confirm the loading skeleton and spinner appear during processing.
5. **Review & Edit Draft**:
   - Inspect the generated summary in the **Edit & Post Note** textarea.
   - Edit wording or adjust action items directly in the textarea.
   - Switch to **Visual Breakdown** tab to view structured sentiment and timeline cards.
6. **Post as Internal Note**:
   - Click **Post as Internal Note** (direct API submission) or **Insert Note** (injects into composer).
   - Verify that a success confirmation toast appears.
   - Confirm the internal note is added to the ticket conversation in **yellow background** (marked strictly as **Internal note**).
7. **Check History**:
   - Click the **Past AI Summaries** accordion below the main card.
   - Verify that previously posted AI summaries appear with timestamp badges and a **Load into Editor** button.
