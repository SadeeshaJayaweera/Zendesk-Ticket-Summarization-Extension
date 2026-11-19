"""Database Base Configuration and Async Engine."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from zendesk_summarizer_shared.config import Settings, get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities."""
    pass


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create or return existing SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        db_url = cfg.database_url

        # Normalize sqlite url for aiosqlite driver
        if db_url.startswith("sqlite://"):
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")

        # Connection pool arguments: SQLite doesn't use pool_size
        connect_args = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False

        _engine = create_async_engine(
            db_url,
            echo=False,
            future=True,
            connect_args=connect_args,
        )
    return _engine


def get_sessionmaker(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """Create or return existing async sessionmaker."""
    global _sessionmaker
    if _sessionmaker is None:
        engine = get_engine(settings)
        _sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def init_db(settings: Settings | None = None):
    """Initialize database tables for development/testing."""
    engine = get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
