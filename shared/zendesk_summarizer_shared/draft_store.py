"""Draft storage for automated AI summaries awaiting agent review.

Allows storing pre-drafted summaries created by automated triggers (e.g. ticket solve webhooks),
querying them for the sidebar app, and marking them as posted once approved.
"""

from datetime import datetime
from typing import Dict, List, Optional
from zendesk_summarizer_shared.models import PendingDraft, SummaryStructured


class DraftStore:
    """In-memory store for pending ticket summary drafts."""

    def __init__(self):
        self._drafts: Dict[int, PendingDraft] = {}

    def save_draft(
        self,
        ticket_id: int,
        summary: SummaryStructured,
        markdown_note: str,
        source_trigger: str = "zendesk_webhook_solved",
    ) -> PendingDraft:
        """Store or update a pending review draft for a ticket."""
        draft = PendingDraft(
            ticket_id=ticket_id,
            status="pending_review",
            summary=summary,
            markdown_note=markdown_note,
            source_trigger=source_trigger,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._drafts[ticket_id] = draft
        return draft

    def get_pending_draft(self, ticket_id: int) -> Optional[PendingDraft]:
        """Retrieve active pending_review draft for a ticket if one exists."""
        draft = self._drafts.get(ticket_id)
        if draft and draft.status == "pending_review":
            return draft
        return None

    def mark_draft_posted(self, ticket_id: int) -> Optional[PendingDraft]:
        """Mark draft as posted after an agent reviews and posts the internal note."""
        draft = self._drafts.get(ticket_id)
        if draft:
            draft.status = "posted"
            draft.updated_at = datetime.utcnow()
        return draft

    def mark_draft_dismissed(self, ticket_id: int) -> Optional[PendingDraft]:
        """Mark draft as dismissed if agent explicitly rejects or discards it."""
        draft = self._drafts.get(ticket_id)
        if draft:
            draft.status = "dismissed"
            draft.updated_at = datetime.utcnow()
        return draft

    def list_all_pending(self) -> List[PendingDraft]:
        """List all currently pending drafts."""
        return [d for d in self._drafts.values() if d.status == "pending_review"]

    def clear(self):
        """Clear all drafts (primarily for unit tests)."""
        self._drafts.clear()


# Global default store instance
_global_draft_store = DraftStore()


def get_draft_store() -> DraftStore:
    """Retrieve singleton instance of DraftStore."""
    return _global_draft_store
