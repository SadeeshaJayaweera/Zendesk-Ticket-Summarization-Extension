# Privacy & Data Retention Policy

## 1. Data Classification Matrix

| Data Category | Examples | Storage Location | Retention Window | Encryption |
| :--- | :--- | :--- | :--- | :--- |
| **Customer Conversations** | Ticket bodies, public comments, attachments | Transient memory / Zendesk API | Not stored persistently beyond prompt generation | In-transit (TLS 1.3) |
| **Generated AI Summaries** | Structured JSON summaries, Markdown notes | `summary_records` table | Configurable (Default: 90 days) | At-rest (AES-256) |
| **Pending Review Drafts** | Staged summaries from solve triggers | `pending_drafts` table | 14 days or until review/posting | At-rest (AES-256) |
| **Audit Logs** | Note posts, agent logins, API calls | `audit_logs` table | 365 days (Enterprise compliance) | At-rest (AES-256) |
| **Operational Telemetry** | Token counts, latency, USD expenditure | `usage_records` table | Indefinite (Aggregated analytics) | At-rest (AES-256) |

---

## 2. GDPR & CCPA Compliance

### Right to Erasure ("Right to be Forgotten")
When an organization receives a customer deletion request:
1. The tenant administrator issues a deletion request for the associated ticket reference.
2. The platform purges all corresponding entries in `summary_records`, `pending_drafts`, and `ticket_references`.
3. Inbound webhooks do not cache raw customer messages permanently.

### Zero-Training Commitments
The platform exclusively leverages enterprise APIs:
* **Google Gemini API**: Data sent to Gemini enterprise endpoints is not used to train foundation models.
* **OpenAI API**: Enterprise API terms enforce a 30-day zero-data-retention policy for model training.
* **Anthropic Claude API**: Customer inputs are not retained or utilized for model training.
* **Groq Cloud**: Real-time inference without training on customer prompts.

---

## 3. Data Retention Lifecycle & Automated Pruning

Tenant organizations configure data retention policies via the `data_retention_days` attribute in the `organizations` table.
* Default retention: **90 days**.
* An automated background job prunes summary records older than the designated retention threshold:
```sql
DELETE FROM summary_records 
WHERE organization_id = :org_id 
  AND created_at < NOW() - INTERVAL '90 days';
```
