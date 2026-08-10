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
    # Connection poolers in front of Postgres do not support prepared statement
    # caching; disabling it costs little and works everywhere.
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


# Columns added to an existing table after the first release. `create_all`
# creates absent TABLES and nothing else -- it will not add a column to a table
# that already exists, so a database provisioned before one of these landed
# comes up and then fails on the first query that selects it.
#
# Each entry is (table, column, DDL type). Adding a nullable column is safe to
# replay, which is what keeps this idempotent rather than a migration history.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("sessions", "cheque_sizes", "JSON"),
)


async def _add_missing_columns(conn) -> None:
    from sqlalchemy import inspect, text

    def _existing(sync_conn, table: str) -> set[str]:
        inspector = inspect(sync_conn)
        if table not in inspector.get_table_names():
            return set()
        return {c["name"] for c in inspector.get_columns(table)}

    for table, column, ddl_type in _ADDED_COLUMNS:
        columns = await conn.run_sync(_existing, table)
        if not columns or column in columns:
            continue
        # Both SQLite and Postgres accept plain ADD COLUMN for a nullable
        # column; only the type spelling differs, and JSON is common to both.
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


async def init_db() -> None:
    """Create tables if absent, then add any columns a later release introduced.

    This is what provisions the schema on Render -- the first boot against an
    empty Postgres creates every table. schema.sql remains the reference for
    setting a database up by hand.
    """
    from . import models  # noqa: F401  -- registers mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn)
