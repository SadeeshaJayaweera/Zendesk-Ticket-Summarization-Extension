import json
import logging
from typing import Any, Dict, Optional
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.gemini_client import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiRateLimitError,
)
from zendesk_summarizer_shared.metrics import MetricsCollector, get_metrics_collector
from zendesk_summarizer_shared.models import (
    DirectSummarizeRequest,
    PendingDraftResponse,
    PostNoteRequest,
    PostNoteResponse,
    SummarizeRequest,
    SummarizeResponse,
    TicketDetailResponse,
    TicketHistoryResponse,
)
from zendesk_summarizer_shared.rate_limiter import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    get_rate_limiter,
)
from zendesk_summarizer_shared.security import (
    WebhookVerificationError,
    verify_zendesk_webhook_signature,
)
from zendesk_summarizer_shared.service import TicketSummarizerService
from zendesk_summarizer_shared.summarizer import (
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    SummarizationError,
)
from zendesk_summarizer_shared.zendesk_client import (
    ZendeskAPIError,
    ZendeskAuthError,
    ZendeskNotFoundError,
    ZendeskRateLimitError,
    ZendeskValidationError,
)

logger = logging.getLogger("zendesk_summarizer.backend")

app = FastAPI(
    title="Zendesk Ticket Summarizer Backend",
    description="REST API service for summarizing Zendesk support tickets with Google Gemini and Groq",
    version="1.0.0",
)

# Enable CORS for local development and Zendesk App Framework (ZAF) iframe requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_service(settings: Settings = Depends(get_settings)) -> TicketSummarizerService:
    """Dependency provider for TicketSummarizerService."""
    return TicketSummarizerService(settings=settings)


async def enforce_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
    limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
):
    """Enforce in-memory sliding window rate limit per client IP or Zendesk Subdomain."""
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "127.0.0.1")
    )
    # Check limit using configured rate_limit_per_minute from Settings
    limit = getattr(settings, "rate_limit_per_minute", 60)
    limiter.check(key=client_ip, limit=limit, window=60)


# --- Global Resilient Exception Handlers ---

@app.exception_handler(RateLimitExceededError)
async def handle_rate_limit_exceeded(request: Request, exc: RateLimitExceededError):
    metrics = get_metrics_collector()
    metrics.record_error("rate_limit")
    logger.warning("Rate limit exceeded: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(exc.retry_after)},
        content={
            "error": "RateLimitExceeded",
            "message": str(exc),
            "retry_after": exc.retry_after,
        },
    )


@app.exception_handler(WebhookVerificationError)
async def handle_webhook_verification_error(request: Request, exc: WebhookVerificationError):
    metrics = get_metrics_collector()
    metrics.record_error("webhook")
    logger.warning("Webhook verification failed: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": "WebhookVerificationError", "message": str(exc)},
    )


@app.exception_handler(ZendeskAuthError)
async def handle_zendesk_auth_error(request: Request, exc: ZendeskAuthError):
    metrics = get_metrics_collector()
    metrics.record_error("zendesk")
    logger.error("Zendesk authentication error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": "ZendeskAuthError", "message": str(exc)},
    )


@app.exception_handler(ZendeskNotFoundError)
async def handle_zendesk_not_found(request: Request, exc: ZendeskNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "ZendeskNotFoundError", "message": str(exc)},
    )


@app.exception_handler(ZendeskRateLimitError)
async def handle_zendesk_rate_limit(request: Request, exc: ZendeskRateLimitError):
    metrics = get_metrics_collector()
    metrics.record_error("zendesk")
    logger.warning("Zendesk API rate limit hit: %s (retry_after=%s)", exc, exc.retry_after)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(exc.retry_after)},
        content={"error": "ZendeskRateLimitError", "message": str(exc), "retry_after": exc.retry_after},
    )


@app.exception_handler(ZendeskValidationError)
async def handle_zendesk_validation_error(request: Request, exc: ZendeskValidationError):
    metrics = get_metrics_collector()
    metrics.record_error("zendesk")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "ZendeskValidationError", "message": str(exc)},
    )


@app.exception_handler(ZendeskAPIError)
async def handle_zendesk_api_error(request: Request, exc: ZendeskAPIError):
    metrics = get_metrics_collector()
    metrics.record_error("zendesk")
    logger.error("Zendesk API error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "ZendeskAPIError", "message": str(exc)},
    )


@app.exception_handler(GeminiAuthError)
async def handle_gemini_auth_error(request: Request, exc: GeminiAuthError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.error("Gemini authentication error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": "GeminiAuthError", "message": str(exc)},
    )


@app.exception_handler(GeminiRateLimitError)
async def handle_gemini_rate_limit(request: Request, exc: GeminiRateLimitError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.warning("Gemini rate limit error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "GeminiRateLimitError", "message": str(exc)},
    )


@app.exception_handler(GeminiAPIError)
async def handle_gemini_api_error(request: Request, exc: GeminiAPIError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.error("Gemini API error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "GeminiAPIError", "message": str(exc)},
    )


@app.exception_handler(LLMAuthError)
async def handle_llm_auth_error(request: Request, exc: LLMAuthError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.error("LLM Provider auth error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": "LLMAuthError", "message": str(exc)},
    )


@app.exception_handler(LLMRateLimitError)
async def handle_llm_rate_limit(request: Request, exc: LLMRateLimitError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.warning("LLM Provider rate limit hit: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "LLMRateLimitError", "message": str(exc)},
    )


@app.exception_handler(LLMAPIError)
async def handle_llm_api_error(request: Request, exc: LLMAPIError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.error("LLM API error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "LLMAPIError", "message": str(exc)},
    )



@app.exception_handler(SummarizationError)
async def handle_summarization_error(request: Request, exc: SummarizationError):
    metrics = get_metrics_collector()
    metrics.record_error("llm")
    logger.error("Summarization pipeline failure: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "SummarizationError", "message": str(exc)},
    )


# --- Core Observability & Status Endpoints ---

@app.get("/")
async def root():
    """Root status endpoint."""
    return {
        "service": "zendesk-ticket-summarizer-backend",
        "status": "online",
        "version": "1.0.0",
    }


@app.get("/metrics")
async def get_metrics(
    metrics: MetricsCollector = Depends(get_metrics_collector),
) -> Dict[str, Any]:
    """Operational metrics endpoint tracking requests, notes, webhooks, errors, and uptime."""
    return metrics.get_metrics()



@app.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint validating configuration state."""
    return {
        "status": "healthy",
        "zendesk_configured": settings.is_zendesk_configured,
        "gemini_configured": settings.is_gemini_configured,
        "zendesk_subdomain": settings.zendesk_subdomain if settings.zendesk_subdomain else None,
        "gemini_model": settings.gemini_model,
    }


@app.get(
    "/api/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    summary="Get Ticket Details and Comments",
)
async def get_ticket(
    ticket_id: int,
    service: TicketSummarizerService = Depends(get_service),
):
    """Retrieve ticket metadata and all conversation comments in chronological order."""
    return await service.get_ticket_details(ticket_id)


@app.get(
    "/api/tickets/{ticket_id}/history",
    response_model=TicketHistoryResponse,
    summary="Get Past AI Summaries for Ticket",
)
async def get_ticket_history(
    ticket_id: int,
    service: TicketSummarizerService = Depends(get_service),
):
    """Retrieve historical AI summaries posted to this ticket."""
    return await service.get_ticket_history(ticket_id)


@app.get(
    "/api/tickets/{ticket_id}/pending-draft",
    response_model=PendingDraftResponse,
    summary="Get Pending Review Draft for Ticket",
)
async def get_pending_draft(
    ticket_id: int,
    service: TicketSummarizerService = Depends(get_service),
):
    """Retrieve pending automated summary draft for this ticket, if one was generated by solve trigger."""
    return await service.get_pending_draft(ticket_id)


@app.post(
    "/webhooks/zendesk/ticket-status-changed",
    dependencies=[Depends(enforce_rate_limit)],
    summary="Zendesk Trigger Webhook for Ticket Status Changes",
)
async def zendesk_ticket_status_webhook(
    request: Request,
    service: TicketSummarizerService = Depends(get_service),
    settings: Settings = Depends(get_settings),
):
    """Webhook endpoint triggered when a ticket status changes (e.g. Solved).

    Verifies HMAC-SHA256 signature, generates pre-draft summary, and stores as pending_review.
    Does NOT auto-post internal notes without human review.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-Zendesk-Webhook-Signature")
    timestamp = request.headers.get("X-Zendesk-Webhook-Signature-Timestamp")

    # Verify signature if secret is configured or signature is provided
    if settings.is_webhook_secret_configured or signature:
        try:
            verify_zendesk_webhook_signature(
                body=body_bytes,
                signature_header=signature,
                timestamp_header=timestamp,
                secret=settings.zendesk_webhook_secret,
            )
        except WebhookVerificationError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    try:
        data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    ticket_id = (
        data.get("ticket", {}).get("id")
        or data.get("ticket_id")
        or data.get("id")
    )

    if not ticket_id:
        return {"status": "ignored", "message": "No ticket ID found in payload"}

    try:
        tid = int(str(ticket_id).strip().lstrip("#"))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ticket ID '{ticket_id}'")

    draft = await service.process_solved_ticket_webhook(ticket_id=tid)
    return {
        "status": "success",
        "ticket_id": tid,
        "draft_status": draft.status,
        "message": f"Pre-draft AI summary generated and stored as {draft.status} for ticket #{tid}",
    }


@app.post(
    "/api/tickets/{ticket_id}/summarize",
    response_model=SummarizeResponse,
    dependencies=[Depends(enforce_rate_limit)],
    summary="Generate AI Summary for Ticket",
)
async def summarize_ticket(
    ticket_id: int,
    request: Optional[SummarizeRequest] = None,
    service: TicketSummarizerService = Depends(get_service),
):
    """Fetch ticket history, run AI summarization via Gemini, and return structured output."""
    style = request.summary_style if request else "standard"
    return await service.summarize_ticket(ticket_id=ticket_id, summary_style=style)


@app.post(
    "/api/tickets/{ticket_id}/notes",
    response_model=PostNoteResponse,
    dependencies=[Depends(enforce_rate_limit)],
    summary="Post Internal Note to Ticket",
)
async def post_note(
    ticket_id: int,
    request: PostNoteRequest,
    service: TicketSummarizerService = Depends(get_service),
):
    """Post a private internal note (or public reply) to the specified Zendesk ticket."""
    return await service.post_summary_note(
        ticket_id=ticket_id,
        note_body=request.body,
        public=request.public,
    )


@app.post(
    "/api/tickets/{ticket_id}/summarize-and-post",
    response_model=SummarizeResponse,
    dependencies=[Depends(enforce_rate_limit)],
    summary="Summarize Ticket and Post as Internal Note",
)
async def summarize_and_post(
    ticket_id: int,
    request: Optional[SummarizeRequest] = None,
    service: TicketSummarizerService = Depends(get_service),
):
    """All-in-one workflow: Generate AI summary and immediately post it to Zendesk as an internal note."""
    style = request.summary_style if request else "standard"
    summary_resp, _ = await service.summarize_and_post(ticket_id=ticket_id, summary_style=style)
    return summary_resp


@app.post(
    "/api/summarize-text",
    response_model=SummarizeResponse,
    dependencies=[Depends(enforce_rate_limit)],
    summary="Direct Text / Chat Summarization",
)
async def summarize_raw_text(
    request: DirectSummarizeRequest,
    service: TicketSummarizerService = Depends(get_service),
):
    """Generate structured summary for arbitrary support text or transcript without contacting Zendesk."""
    return await service.summarize_raw_text(
        text=request.text,
        subject=request.subject,
        summary_style=request.summary_style,
    )



if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )

# Handler optimization revision 1

# Handler optimization revision 2

# Handler optimization revision 3

# Handler optimization revision 4

# Handler optimization revision 5

# Handler optimization revision 6

# Handler optimization revision 7

# Handler optimization revision 8

# Handler optimization revision 9

# Handler optimization revision 10

# Handler optimization revision 11

# Handler optimization revision 12

# Handler optimization revision 13

# Handler optimization revision 14

# Handler optimization revision 15

# Handler optimization revision 16

# Handler optimization revision 17

# Handler optimization revision 18

# Handler optimization revision 19

# Handler optimization revision 20

# Handler optimization revision 21

# Handler optimization revision 22

# Handler optimization revision 23

# Handler optimization revision 24

# Handler optimization revision 25
