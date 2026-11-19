"""Unit & integration tests for PlatformRepository using in-memory Async SQLite."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zendesk_summarizer_shared.db.base import Base
from zendesk_summarizer_shared.db.repository import PlatformRepository


@pytest_asyncio.fixture
async def async_session():
    """Create a temporary in-memory SQLite database and return an active AsyncSession."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_organization_crud(async_session: AsyncSession):
    """Test creating and querying organizations with tenant subdomain lookups."""
    repo = PlatformRepository(async_session)

    org = await repo.create_organization(
        name="Acme Corp Support",
        slug="acme",
        zendesk_subdomain="acme-help",
        zendesk_email="support@acme.com",
    )
    await async_session.commit()

    assert org.id is not None
    assert org.slug == "acme"

    # Query by subdomain
    found = await repo.get_organization_by_subdomain("acme-help")
    assert found is not None
    assert found.id == org.id
    assert found.name == "Acme Corp Support"

    # Non-existent subdomain
    none_found = await repo.get_organization_by_subdomain("non-existent")
    assert none_found is None


@pytest.mark.asyncio
async def test_user_tenant_isolation(async_session: AsyncSession):
    """Test user creation and tenant isolation."""
    repo = PlatformRepository(async_session)

    org1 = await repo.create_organization(name="Org One", slug="org1", zendesk_subdomain="org1-sub")
    org2 = await repo.create_organization(name="Org Two", slug="org2", zendesk_subdomain="org2-sub")
    await async_session.commit()

    user1 = await repo.create_user(
        organization_id=org1.id,
        email="agent@org1.com",
        full_name="Agent Org1",
        hashed_password="hashed_pw_1",
        role="support_agent",
    )
    await async_session.commit()

    # Query with matching org_id
    found = await repo.get_user_by_email("agent@org1.com", org_id=org1.id)
    assert found is not None
    assert found.email == "agent@org1.com"

    # Query with different org_id should return None (Tenant isolation)
    wrong_org = await repo.get_user_by_email("agent@org1.com", org_id=org2.id)
    assert wrong_org is None


@pytest.mark.asyncio
async def test_pending_draft_lifecycle(async_session: AsyncSession):
    """Test saving, retrieving, and marking pending review drafts as posted."""
    repo = PlatformRepository(async_session)

    org = await repo.create_organization(name="Draft Org", slug="draft-org", zendesk_subdomain="draft-sub")
    await async_session.commit()

    draft = await repo.save_pending_draft(
        organization_id=org.id,
        ticket_id=888,
        summary_style="standard",
        structured_data={"executive_summary": "Password reset resolved."},
        markdown_note="### 🤖 AI Ticket Summary\nPassword reset resolved.",
    )
    await async_session.commit()

    assert draft.id is not None
    assert draft.status == "pending_review"

    # Fetch active draft
    active = await repo.get_pending_draft(org.id, 888)
    assert active is not None
    assert active.ticket_id == 888
    assert "Password reset" in active.markdown_note

    # Mark as posted
    marked = await repo.mark_draft_status(org.id, 888, new_status="posted")
    await async_session.commit()
    assert marked is True

    # After marked posted, should no longer be pending_review
    re_check = await repo.get_pending_draft(org.id, 888)
    assert re_check is None


@pytest.mark.asyncio
async def test_webhook_event_deduplication(async_session: AsyncSession):
    """Test webhook event recording and status update."""
    repo = PlatformRepository(async_session)

    event = await repo.record_webhook_event(
        event_id="evt_unique_12345",
        event_type="ticket_solved",
        ticket_id=999,
        payload={"ticket": {"id": 999, "status": "solved"}},
    )
    await async_session.commit()

    assert event.id is not None
    assert event.status == "received"

    # Check deduplication helper
    is_seen = await repo.is_duplicate_webhook_event("evt_unique_12345")
    assert is_seen is True

    is_new = await repo.is_duplicate_webhook_event("evt_never_seen")
    assert is_new is False

    # Update status to completed
    await repo.mark_webhook_event_completed("evt_unique_12345")
    await async_session.commit()


@pytest.mark.asyncio
async def test_analytics_aggregation(async_session: AsyncSession):
    """Test recording summary & usage records and calculating analytics totals."""
    repo = PlatformRepository(async_session)

    org = await repo.create_organization(name="Metrics Org", slug="metrics-org", zendesk_subdomain="metrics-sub")
    await async_session.commit()

    await repo.save_summary_record(
        organization_id=org.id,
        ticket_id=101,
        style="standard",
        provider_used="gemini",
        model_used="gemini-1.5-flash",
        executive_summary="Summary 1",
        customer_issue="Issue 1",
        structured_json={"issue": "login"},
        markdown_content="### Summary",
        prompt_tokens=400,
        completion_tokens=150,
        estimated_cost_usd=0.0001,
        latency_seconds=1.2,
    )
    await repo.record_usage(
        organization_id=org.id,
        provider="gemini",
        model="gemini-1.5-flash",
        operation="summarize",
        prompt_tokens=400,
        completion_tokens=150,
        estimated_cost_usd=0.0001,
    )
    await async_session.commit()

    analytics = await repo.get_analytics_metrics(org.id)
    assert analytics["total_summaries_generated"] == 1
    assert analytics["total_tokens_consumed"] == 550
    assert analytics["estimated_ai_expenditure_usd"] > 0.0
