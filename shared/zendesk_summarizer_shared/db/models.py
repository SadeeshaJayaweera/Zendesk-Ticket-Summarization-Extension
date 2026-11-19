"""SQLAlchemy 2.x Async Data Models for Enterprise SaaS Architecture.

Entities:
- Organization (Multi-tenant partition)
- User & Role (Authentication and RBAC)
- SummaryTemplate (Customizable organization-specific templates)
- TicketReference (Zendesk ticket reference)
- SummaryRecord (Historical generated summaries)
- PendingDraft (Persistent drafts awaiting agent review)
- WebhookEvent (Durable webhook processing & replay prevention)
- AuditLog (Operational audit trail)
- UsageRecord (Token economics and cost tracking)
"""

from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zendesk_summarizer_shared.db.base import Base


def generate_uuid() -> str:
    """Generate string UUID."""
    return str(uuid.uuid4())


class Organization(Base):
    """Tenant organization record."""
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    zendesk_subdomain: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    zendesk_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    zendesk_api_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # AI Config
    primary_ai_provider: Mapped[str] = mapped_column(String(32), default="gemini", nullable=False)
    primary_model: Mapped[str] = mapped_column(String(64), default="gemini-1.5-flash", nullable=False)
    fallback_ai_provider: Mapped[str] = mapped_column(String(32), default="groq", nullable=False)
    fallback_model: Mapped[str] = mapped_column(String(64), default="llama-3.3-70b-versatile", nullable=False)
    default_summary_style: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)

    # Privacy & Governance policies
    allow_internal_notes_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_attachments_to_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    templates: Mapped[List["SummaryTemplate"]] = relationship("SummaryTemplate", back_populates="organization", cascade="all, delete-orphan")
    drafts: Mapped[List["PendingDraft"]] = relationship("PendingDraft", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """User account within an organization."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="support_agent", nullable=False)  # super_admin, org_admin, manager, team_lead, support_agent, analyst
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")

    __table_args__ = (
        Index("idx_user_org_email", "organization_id", "email", unique=True),
    )


class SummaryTemplate(Base):
    """Configurable summary instructions and custom templates."""
    __tablename__ = "summary_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    style_key: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    custom_system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guidance_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="templates")


class TicketReference(Base):
    """Zendesk ticket reference and classification snapshot."""
    __tablename__ = "ticket_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    zendesk_ticket_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detected_sentiment: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    requester_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    assignee_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ticket_org_tid", "organization_id", "zendesk_ticket_id", unique=True),
    )


class SummaryRecord(Base):
    """Persistent archive of generated AI summaries and metrics."""
    __tablename__ = "summary_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    ticket_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    style: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    provider_used: Mapped[str] = mapped_column(String(32), nullable=False)
    model_used: Mapped[str] = mapped_column(String(64), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    customer_issue: Mapped[str] = mapped_column(Text, nullable=False)
    structured_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    was_posted_to_zendesk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="agent_request", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class PendingDraft(Base):
    """Persistent pending review draft generated by triggers or background agents."""
    __tablename__ = "pending_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    ticket_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)  # pending_review, posted, dismissed
    summary_style: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    structured_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    markdown_note: Mapped[str] = mapped_column(Text, nullable=False)
    source_trigger: Mapped[str] = mapped_column(String(64), default="zendesk_webhook_solved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="drafts")

    __table_args__ = (
        Index("idx_draft_org_ticket", "organization_id", "ticket_id"),
    )


class WebhookEvent(Base):
    """Durable record of incoming Zendesk webhooks for deduplication and replay safety."""
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="received", nullable=False)  # received, processing, completed, failed, ignored
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class AuditLog(Base):
    """Enterprise audit trail tracking all actions, note posts, and configurations."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class UsageRecord(Base):
    """Detailed token usage and billing ledger."""
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)
