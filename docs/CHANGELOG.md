# Changelog

All notable changes to the **Zendesk Support Intelligence Platform** are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-19

### 🚀 Major Platform Transformation (Commercial SaaS Release)
Transformed the Zendesk Ticket Summarizer prototype into a complete, secure, scalable, and commercially competitive **AI Support Intelligence Platform**.

### ✨ Added
* **10 Specialized Summary Profiles**:
  * Standard Ticket Summary
  * Technical Troubleshooting Summary
  * Customer Complaint & De-escalation Summary
  * Shift Handover Briefing
  * Engineering Escalation Summary
  * Software Bug Investigation Summary
  * Billing & Payment Dispute Summary
  * Integration / Webhook Failure Summary
  * Customer Success Health Summary
  * Executive Management Summary
* **Advanced Support Intelligence Subsystems**:
  * **AI Troubleshooting Assistant**: Diagnoses issues from conversation evidence with steps, expected outcomes, alternatives, and escalation criteria.
  * **AI Reply Drafting**: Generates context-grounded response drafts across 5 tones (`professional`, `friendly`, `technical`, `empathetic`, `concise`) with human review enforcement.
  * **Ticket Classification & Triage**: Predicts issue category, subcategory, product, complexity, department, and priority with confidence scores.
  * **Customer Sentiment & Frustration Radar**: Estimates customer frustration level, unresolved grievances, and churn risk.
  * **Engineering Escalation Briefs**: Produces structured briefs with technical evidence, reproduction data, and requested engineering actions.
  * **Shift Handover Briefings**: Generates handover notes tracking what's resolved, what's open, customer commitments, and next-agent ownership.
  * **Knowledge Base Recommendations**: Connects to Zendesk Help Center to surface relevant articles with relevance explanations.
  * **Similar & Duplicate Ticket Discovery**: Discovers past resolved tickets sharing symptoms and highlights potential duplicate requests.
* **Multi-Provider AI Orchestration**:
  * Provider adapters for Google Gemini (1.5 Flash/Pro, 2.0 Flash), OpenAI (GPT-4o, GPT-4o-mini), Anthropic Claude (3.5 Sonnet, 3.5 Haiku), and Groq Cloud (LLaMA 3.3 70B, LLaMA 3.1 8B).
  * Automated failover chain with retry backoff and token budgeting.
  * Exact per-request token usage economics and USD cost tracking.
* **Intelligent Conversation Context Engine**:
  * Strict prompt injection quarantine delimiters (`<<<UNTRUSTED_CONTENT>>>`).
  * Automatic HTML stripping and entity decoding.
  * Automated email signature removal and quoted reply thread pruning.
  * Automated PII redaction for credit cards, SSNs, and passwords/API keys.
* **Enterprise Persistence & Database Architecture**:
  * PostgreSQL 16 (`asyncpg`) and SQLite (`aiosqlite`) support via async SQLAlchemy 2.0.
  * Strict multi-tenant logical isolation using indexed `organization_id` foreign keys.
  * Alembic migration environment with initial migration `001_initial_schema`.
  * Celery background worker fleet with Redis 7 message broker.
* **Authentication & RBAC**:
  * Bcrypt password hashing and JWT access token issuance.
  * Role-based permissions (`super_admin`, `org_admin`, `manager`, `support_agent`, `analyst`).
  * Analytics overview and streaming CSV export.
* **Native Zendesk Agent Workspace App (ZAF v2)**:
  * Full 9-tab navigation interface styled with Zendesk Garden tokens.
  * Direct insertion into Zendesk Internal Note and Public Reply composers.
  * Confirmation modals safeguarding note publication against accidental posting.
* **Expanded Model Context Protocol (MCP) Server**:
  * 13 standardized tools exposing ticket inspection, summarization, troubleshooting, and draft generation to Claude Desktop, Cursor, Antigravity, and Gemini CLI.
* **Testing & DevOps**:
  * Automated test suite expanded to 123 passing tests (100% pass rate) with ~81% code coverage.
  * Multi-stage production `Dockerfile` with unprivileged `appuser:appgroup`.
  * Production `docker-compose.yml` orchestrating PostgreSQL 16, Redis 7, FastAPI, and Celery worker.
  * GitHub Actions CI/CD workflow (`.github/workflows/ci.yml`).

---

## [0.1.0] - 2026-11-18
### Initial Prototype Release
* Basic FastAPI backend for ticket summarization.
* Basic Gemini 1.5 Flash integration.
* Basic ZAF v2 sidebar widget.
* Basic SQLite audit logger.
