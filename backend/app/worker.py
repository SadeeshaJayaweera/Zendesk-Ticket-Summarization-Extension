"""Celery background worker and task orchestration for asynchronous jobs.

Handles:
- Asynchronous webhook event processing
- Pre-draft generation on ticket solve events
- Batch ticket intelligence generation
- Asynchronous metrics and usage persistence
"""

import asyncio
from typing import Any, Dict, Optional
from celery import Celery

from zendesk_summarizer_shared.config import get_settings
from zendesk_summarizer_shared.service import TicketSummarizerService
from zendesk_summarizer_shared.db.base import get_session_factory
from zendesk_summarizer_shared.db.repository import PlatformRepository

settings = get_settings()

celery_app = Celery(
    "zendesk_intelligence_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes maximum
)


def run_async(coro):
    """Run an async coroutine inside synchronous Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="worker.process_webhook_event", bind=True, max_retries=3)
def process_webhook_event_task(self, event_id: str, ticket_id: int, organization_id: Optional[str] = None):
    """Celery task: process ticket solved webhook asynchronously."""
    async def _async_process():
        session_factory = get_session_factory()
        async with session_factory() as session:
            repo = PlatformRepository(session)
            service = TicketSummarizerService()

            try:
                # 1. Fetch ticket and summarize
                summary_resp = await service.summarize_ticket(
                    ticket_id=ticket_id,
                    summary_style=settings.default_summary_style,
                )

                # 2. Store persistent pending draft
                if organization_id:
                    await repo.create_pending_draft(
                        organization_id=organization_id,
                        ticket_id=ticket_id,
                        summary_style=settings.default_summary_style,
                        structured_data=summary_resp.summary.model_dump(),
                        markdown_note=summary_resp.markdown_note,
                        source_trigger="celery_webhook_solved",
                    )
                else:
                    service.draft_store.save_draft(
                        ticket_id=ticket_id,
                        draft=summary_resp,
                        source="celery_webhook_solved",
                    )

                # 3. Update webhook event status
                await repo.update_webhook_status(
                    event_id=event_id,
                    status="completed",
                )
                await session.commit()
                return {"status": "success", "ticket_id": ticket_id}
            except Exception as exc:
                await repo.update_webhook_status(
                    event_id=event_id,
                    status="failed",
                    error_message=str(exc),
                )
                await session.commit()
                raise exc

    try:
        return run_async(_async_process())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))


@celery_app.task(name="worker.generate_summary_async")
def generate_summary_task(ticket_id: int, summary_style: str = "standard", organization_id: Optional[str] = None):
    """Celery task: generate summary asynchronously."""
    async def _async_generate():
        service = TicketSummarizerService()
        return await service.summarize_ticket(ticket_id=ticket_id, summary_style=summary_style)

    return run_async(_async_generate())
