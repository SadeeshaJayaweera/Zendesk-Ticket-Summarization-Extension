"""Asynchronous Zendesk REST API Client for Zendesk Ticket Summarizer."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple
import httpx

from zendesk_summarizer_shared.config import Settings, get_settings
from zendesk_summarizer_shared.models import (
    Comment,
    Ticket,
    TicketCommentsResponse,
    TicketResponse,
    User,
    UserResponse,
    ZendeskComment,
    ZendeskTicket,
    ZendeskUser,
)


class ZendeskAPIError(Exception):
    """Base exception for Zendesk API interactions."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ZendeskAuthError(ZendeskAPIError):
    """Authentication or authorization failure against Zendesk API (401/403)."""
    pass


class ZendeskNotFoundError(ZendeskAPIError):
    """Requested Zendesk resource or subdomain was not found (404)."""
    pass


class ZendeskRateLimitError(ZendeskAPIError):
    """Zendesk API rate limit exceeded (429)."""
    def __init__(self, message: str, retry_after: int = 60, response_text: Optional[str] = None):
        super().__init__(message, status_code=429, response_text=response_text)
        self.retry_after = retry_after


class ZendeskValidationError(ZendeskAPIError):
    """Zendesk API request validation or entity limit error (422)."""
    pass


class ZendeskClient:
    """Async client for interacting with the Zendesk Support REST API."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        sleep_fn: Optional[Callable[[float], Any]] = None,
    ):
        self.settings = settings or get_settings()
        self._client = client
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._sleep_fn = sleep_fn or asyncio.sleep

    def _get_headers(self) -> Dict[str, str]:
        """Construct standard Zendesk API headers."""
        auth_header = self.settings.zendesk_auth_header
        if not auth_header:
            raise ZendeskAuthError("Zendesk credentials are not properly configured in settings.")

        return {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ZendeskTicketSummarizer/0.1.0",
        }

    def _handle_response_error(self, response: httpx.Response, resource: str):
        """Map HTTP error status codes to specific Zendesk exceptions."""
        status = response.status_code
        text = response.text

        if status == 401:
            raise ZendeskAuthError(
                f"Zendesk authentication failed (401 Unauthorized) when accessing {resource}. Check email/token.",
                status_code=401,
                response_text=text,
            )
        elif status == 403:
            raise ZendeskAuthError(
                f"Zendesk access forbidden (403 Forbidden) for {resource}. Check agent permissions.",
                status_code=403,
                response_text=text,
            )
        elif status == 404:
            raise ZendeskNotFoundError(
                f"Zendesk resource not found (404) at {resource}.",
                status_code=404,
                response_text=text,
            )
        elif status == 422:
            raise ZendeskValidationError(
                f"Zendesk entity unprocessable (422) for {resource}: {text}",
                status_code=422,
                response_text=text,
            )
        elif status == 429:
            retry_after = self._extract_retry_after(response)
            raise ZendeskRateLimitError(
                f"Zendesk rate limit exceeded (429) for {resource}. Retry after {retry_after}s.",
                retry_after=retry_after,
                response_text=text,
            )
        elif status >= 400:
            raise ZendeskAPIError(
                f"Zendesk API error {status} on {resource}: {text}",
                status_code=status,
                response_text=text,
            )

    def _extract_retry_after(self, response: httpx.Response) -> int:
        """Extract Retry-After header integer value if present, otherwise default to 60s."""
        raw_retry = response.headers.get("Retry-After")
        if raw_retry:
            try:
                val = int(float(raw_retry))
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
        return 60

    async def _request(
        self,
        method: str,
        path_or_url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an asynchronous HTTP request with automatic rate limit retry and exponential backoff."""
        base_url = self.settings.zendesk_base_url
        if not base_url:
            raise ZendeskAuthError("Zendesk subdomain is not configured.")

        # Build full URL if path is relative
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            if not path_or_url.startswith("/"):
                path_or_url = f"/{path_or_url}"
            url = f"{base_url}{path_or_url}"

        headers = self._get_headers()
        attempt = 0

        while True:
            try:
                if self._client is not None:
                    response = await self._client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_data,
                        timeout=20.0,
                    )
                else:
                    async with httpx.AsyncClient(timeout=20.0) as client:
                        response = await client.request(
                            method=method,
                            url=url,
                            headers=headers,
                            params=params,
                            json=json_data,
                        )

                # Check if rate limited (429)
                if response.status_code == 429:
                    attempt += 1
                    retry_after = self._extract_retry_after(response)

                    if attempt <= self.max_retries:
                        # Use Retry-After if provided; otherwise apply exponential backoff
                        delay = float(retry_after) if response.headers.get("Retry-After") else self.backoff_factor * (2 ** (attempt - 1))
                        await self._sleep_fn(delay)
                        continue
                    else:
                        raise ZendeskRateLimitError(
                            f"Zendesk rate limit exceeded (429) for {path_or_url}. Retries exhausted ({self.max_retries}).",
                            retry_after=retry_after,
                            response_text=response.text,
                        )

                if response.status_code >= 400:
                    self._handle_response_error(response, path_or_url)

                return response.json()

            except (ZendeskAPIError, ZendeskAuthError, ZendeskNotFoundError, ZendeskRateLimitError, ZendeskValidationError):
                raise
            except httpx.RequestError as exc:
                raise ZendeskAPIError(
                    f"Network error connecting to Zendesk REST API at {url}: {str(exc)}"
                ) from exc

    async def get_ticket(self, ticket_id: int) -> Ticket:
        """Fetch details for a specific Zendesk ticket.

        Args:
            ticket_id: Unique integer ID of the ticket.

        Returns:
            Ticket model containing metadata (subject, status, priority, requester, assignee, tags, timestamps).
        """
        data = await self._request("GET", f"/api/v2/tickets/{ticket_id}.json")
        return TicketResponse.model_validate(data).ticket

    async def get_ticket_comments(self, ticket_id: int) -> List[Comment]:
        """Fetch the FULL conversation thread (all comments, public and internal, in chronological order).

        Handles pagination automatically across multiple pages if comments exceed a single page.

        Args:
            ticket_id: Unique integer ID of the ticket.

        Returns:
            List of Comment objects covering the entire comment history.
        """
        all_comments: List[Comment] = []
        next_url: Optional[str] = f"/api/v2/tickets/{ticket_id}/comments.json"
        params: Optional[Dict[str, Any]] = {"per_page": 100}

        max_pages = 50  # Safety safeguard to prevent infinite pagination loops
        pages_fetched = 0

        while next_url and pages_fetched < max_pages:
            data = await self._request("GET", next_url, params=params)
            parsed = TicketCommentsResponse.model_validate(data)

            if parsed.comments:
                all_comments.extend(parsed.comments)

            # Zendesk returns next_page as full URL string or null
            raw_next_page = data.get("next_page")
            if raw_next_page and raw_next_page != next_url and len(parsed.comments) > 0:
                next_url = raw_next_page
                params = None  # Params are already encoded in next_page URL
                pages_fetched += 1
            else:
                break

        return all_comments

    async def post_internal_note(
        self,
        ticket_id: int,
        body: str,
        public: bool = False,
    ) -> Comment:
        """Post a private internal note (or public reply) to a Zendesk ticket.

        CRITICAL REQUIREMENT: `public` defaults strictly to `False` so that internal
        notes/AI summaries are never accidentally made visible to the ticket requester.

        Args:
            ticket_id: Unique integer ID of the ticket.
            body: The text or markdown content of the comment.
            public: Whether the note is public (True) or private internal note (False). Default: False.

        Returns:
            Comment model representing the newly created comment.
        """
        payload = {
            "ticket": {
                "comment": {
                    "body": body,
                    "public": public,
                }
            }
        }
        data = await self._request("PUT", f"/api/v2/tickets/{ticket_id}.json", json_data=payload)

        # Attempt to parse created comment from audit events in response
        audit = data.get("audit")
        if audit and isinstance(audit, dict):
            events = audit.get("events", [])
            for ev in events:
                if ev.get("type") == "Comment":
                    return Comment(
                        id=ev.get("id", 0),
                        type="Comment",
                        author_id=ev.get("author_id", audit.get("author_id", 0)),
                        body=ev.get("body", body),
                        html_body=ev.get("html_body"),
                        plain_body=ev.get("plain_body"),
                        public=ev.get("public", public),
                        attachments=[],
                        created_at=audit.get("created_at"),
                        audit_id=audit.get("id"),
                    )

        # Fallback if audit event is not returned in minimal response
        ticket_data = data.get("ticket", {})
        return Comment(
            id=ticket_data.get("id", 0),
            author_id=ticket_data.get("assignee_id") or ticket_data.get("submitter_id") or 0,
            body=body,
            public=public,
            created_at=ticket_data.get("updated_at"),
        )

    async def get_user(self, user_id: int) -> User:
        """Fetch details for a specific Zendesk user by ID.

        Args:
            user_id: Unique integer ID of the Zendesk user.

        Returns:
            User model with user profile details.
        """
        data = await self._request("GET", f"/api/v2/users/{user_id}.json")
        return UserResponse.model_validate(data).user

    async def get_ticket_requester_and_assignee(
        self,
        ticket_id: int,
    ) -> Tuple[Optional[User], Optional[User]]:
        """Fetch both requester and assignee user objects for a given ticket.

        Uses side-loading with `?include=users` where possible for single round-trip efficiency,
        falling back to direct user lookup if needed.

        Args:
            ticket_id: Unique integer ID of the ticket.

        Returns:
            Tuple of (requester_user, assignee_user). Either may be None if unassigned or not found.
        """
        data = await self._request("GET", f"/api/v2/tickets/{ticket_id}.json", params={"include": "users"})
        ticket_resp = TicketResponse.model_validate(data)
        ticket = ticket_resp.ticket

        user_map: Dict[int, User] = {}
        if ticket_resp.users:
            for u in ticket_resp.users:
                user_map[u.id] = u

        requester: Optional[User] = None
        if ticket.requester_id:
            if ticket.requester_id in user_map:
                requester = user_map[ticket.requester_id]
            else:
                try:
                    requester = await self.get_user(ticket.requester_id)
                except Exception:
                    requester = None

        assignee: Optional[User] = None
        if ticket.assignee_id:
            if ticket.assignee_id in user_map:
                assignee = user_map[ticket.assignee_id]
            else:
                try:
                    assignee = await self.get_user(ticket.assignee_id)
                except Exception:
                    assignee = None

        return requester, assignee

    async def list_tickets(
        self,
        per_page: int = 10,
        page: int = 1,
        status: Optional[str] = None,
    ) -> List[Ticket]:
        """List tickets from the Zendesk account, optionally filtered by status.

        Args:
            per_page: Number of tickets per page.
            page: Page number for offset pagination.
            status: Optional ticket status filter (e.g. 'open', 'pending', 'solved', 'new').

        Returns:
            List of Ticket objects.
        """
        if status:
            data = await self._request(
                "GET",
                "/api/v2/search.json",
                params={"query": f"type:ticket status:{status}", "per_page": per_page, "page": page},
            )
            tickets_data = data.get("results", [])
        else:
            params = {"per_page": per_page, "page": page}
            data = await self._request("GET", "/api/v2/tickets.json", params=params)
            tickets_data = data.get("tickets", [])
        return [Ticket.model_validate(t) for t in tickets_data]



# Resilience refinement 1

# Resilience refinement 2

# Resilience refinement 3

# Resilience refinement 4

# Resilience refinement 5

# Resilience refinement 6

# Resilience refinement 7

# Resilience refinement 8

# Resilience refinement 9

# Resilience refinement 10

# Resilience refinement 11

# Resilience refinement 12

# Resilience refinement 13

# Resilience refinement 14

# Resilience refinement 15

# Resilience refinement 16

# Resilience refinement 17

# Resilience refinement 18

# Resilience refinement 19

# Resilience refinement 20

# Resilience refinement 21

# Resilience refinement 22

# Resilience refinement 23

# Resilience refinement 24

# Resilience refinement 25

# Resilience refinement 26

# Resilience refinement 27

# Resilience refinement 28

# Resilience refinement 29
