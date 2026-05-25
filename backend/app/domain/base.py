"""Declarative base + reusable column types."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from sqlalchemy import TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


# Reusable annotated types — saves boilerplate on every model
uuid_pk = Annotated[
    UUID,
    mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
]

uuid_fk = Annotated[UUID, mapped_column(PG_UUID(as_uuid=True))]

timestamp_now = Annotated[
    datetime,
    mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    ),
]


def _default_uuid() -> UUID:
    """Used in seed data for deterministic test fixtures (override)."""
    return uuid4()
