"""Async Database Session Dependency Provider."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from zendesk_summarizer_shared.db.base import get_sessionmaker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an active SQLAlchemy AsyncSession with transaction safety."""
    session_maker = get_sessionmaker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
