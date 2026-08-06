from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


def _connect_args() -> dict:
    if settings.is_sqlite:
        return {}
    # Supabase's pooler does not support prepared statement caching.
    args: dict = {"statement_cache_size": 0}
    if settings.db_ssl_required:
        # asyncpg takes TLS through connect_args; `sslmode` in the DSN is a
        # libpq spelling it rejects, so config.py strips it and sets this.
        args["ssl"] = True
    return args


_engine_kwargs: dict = {"echo": False, "connect_args": _connect_args()}
if not settings.is_sqlite:
    _engine_kwargs |= {
        "pool_pre_ping": True,
        # Managed Postgres caps connections and a redeploy overlaps the old
        # instance with the new one; a small recycling pool keeps two web
        # workers plus the overlap comfortably under the limit.
        "pool_size": 5,
        "max_overflow": 5,
        "pool_recycle": 1800,
    }

engine = create_async_engine(settings.sqlalchemy_database_url, **_engine_kwargs)

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
