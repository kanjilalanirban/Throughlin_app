"""Decisions — choices made along the way, with rationale.

Matches docs/data-model.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, timestamp_now, uuid_pk

if TYPE_CHECKING:
    from app.domain.initiatives import Initiative


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (Index("decisions_initiative_idx", "initiative_id"),)

    id: Mapped[uuid_pk]
    initiative_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("initiatives.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    decided_by_person_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id"), nullable=True
    )

    # NULL until the validity job has run for the first time
    still_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence_against: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[timestamp_now]

    initiative: Mapped["Initiative"] = relationship("Initiative", back_populates="decisions")
