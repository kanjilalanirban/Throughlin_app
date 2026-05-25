"""Async SQLAlchemy engine + session factory + FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def _build_connect_args(database_url: str) -> dict[str, object]:
    """Connect args for asyncpg.

    In AWS we encrypt the connection (RDS parameter group sets
    `rds.force_ssl = 1`) but skip cert verification — matches the
    Alembic psycopg path (PGSSLMODE=require). We're inside the VPC,
    so MITM risk is acceptably low for Phase 0. Phase 1 hardening
    pins the RDS CA bundle and switches to verify-full.

    Locally we don't (docker-compose Postgres doesn't have SSL).
    """
    if "localhost" in database_url or "127.0.0.1" in database_url:
        return {}
    return {"ssl": "require"}


def _make_engine() -> AsyncEngine:
    s = get_settings()
    return create_async_engine(
        s.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args=_build_connect_args(s.database_url),
        echo=False,
    )


# Lazily created on first use so test fixtures can stub get_settings() first.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session, rolls back on exception."""
    session = session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Typed dependency for endpoint signatures: `db: DbSession = Depends(get_db)`.
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def dispose_engine() -> None:
    """Called on app shutdown to cleanly close all pooled connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
