"""Ingestion runs — operational record per integration fetch.

Not org-scoped (operational/admin data).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base, uuid_pk


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (Index("ingestion_runs_source_started_idx", "source", "started_at"),)

    id: Mapped[uuid_pk]
    source: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # running | success | failed | partial
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
