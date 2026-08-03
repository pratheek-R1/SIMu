from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=not settings.is_sqlite,
    # Supabase's pooler does not support prepared statement caching.
    connect_args={"statement_cache_size": 0} if not settings.is_sqlite else {},
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables if absent.

    Production uses the checked-in schema.sql against Supabase; this exists so a
    developer can run the API against SQLite with no setup at all.
    """
    from . import models  # noqa: F401  -- registers mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
