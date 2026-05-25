"""Alembic environment.

Loads the URL from app.core.config (which fetches RDS creds from Secrets
Manager in AWS, or uses DATABASE_URL locally). Uses the SYNC psycopg
driver for migrations — alembic's offline/online flows are sync, so we
swap `+asyncpg` for `+psycopg` at runtime if needed.

For Phase 0 we don't have psycopg installed in production. Migrations
are run from a developer machine (or a one-shot CI job) where psycopg
is in the dev deps. Production app uses asyncpg only.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app.*` importable from `alembic/`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.domain import Base  # noqa: E402  (imports all models)

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """Return a sync-driver version of the configured URL."""
    url = get_settings().database_url
    # Migrations run synchronously; swap asyncpg → psycopg.
    return url.replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _sync_url()
    # Force SSL when targeting RDS (anything not localhost)
    if "localhost" not in cfg["sqlalchemy.url"] and "127.0.0.1" not in cfg["sqlalchemy.url"]:
        os.environ.setdefault("PGSSLMODE", "require")

    engine = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
