"""Signals — continuous evidence from Jira, GitHub, HRIS. With pgvector embeddings.

Matches docs/data-model.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import TIMESTAMP, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base, timestamp_now, uuid_pk


# 1536 dims = text-embedding-3-small. The exact model is config-driven (see
# data-model.md); the column width is fixed at table creation time.
EMBEDDING_DIM = 1536


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("signals_org_observed_idx", "org_id", "observed_at"),
        Index("signals_source_idx", "source", "source_entity_id"),
        Index(
            "signals_initiative_idx",
            "links_to_initiative_id",
            postgresql_where=text("links_to_initiative_id IS NOT NULL"),
        ),
        Index(
            "signals_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid_pk]
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # jira | github | hris
    source_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    links_to_initiative_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("initiatives.id"), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    created_at: Mapped[timestamp_now]
