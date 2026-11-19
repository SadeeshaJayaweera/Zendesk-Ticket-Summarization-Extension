"""Database layer for Zendesk Ticket Summarizer."""

from zendesk_summarizer_shared.db.base import (
    Base,
    get_engine,
    get_sessionmaker,
    init_db,
)
from zendesk_summarizer_shared.db.models import (
    AuditLog,
    Organization,
    PendingDraft,
    SummaryRecord,
    SummaryTemplate,
    TicketReference,
    UsageRecord,
    User,
    WebhookEvent,
)
from zendesk_summarizer_shared.db.repository import PlatformRepository
from zendesk_summarizer_shared.db.session import get_db_session

__all__ = [
    "Base",
    "get_engine",
    "get_sessionmaker",
    "init_db",
    "get_db_session",
    "Organization",
    "User",
    "SummaryTemplate",
    "TicketReference",
    "SummaryRecord",
    "PendingDraft",
    "WebhookEvent",
    "AuditLog",
    "UsageRecord",
    "PlatformRepository",
]
