"""Audit log — every read/write of org data lands here.

Phase 0: lives in RDS (wiped on each `make down`). Phase 1: moved to a
long-lived store (DynamoDB or S3+Athena).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base, uuid_pk


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("audit_log_user_occurred_idx", "user_id", "occurred_at"),)

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
