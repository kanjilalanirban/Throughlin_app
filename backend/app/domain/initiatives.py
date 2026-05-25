"""Initiatives — long-lived strategic bets. The unit of executive attention.

Matches docs/data-model.md.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, timestamp_now, uuid_pk

if TYPE_CHECKING:
    from app.domain.decisions import Decision
    from app.domain.people import PersonInitiative


class Initiative(Base):
    __tablename__ = "initiatives"
    __table_args__ = (
        Index("initiatives_org_idx", "org_id"),
        Index("initiatives_status_idx", "org_id", "status"),
    )

    id: Mapped[uuid_pk]
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # proposed | active | on_hold | completed | cancelled
    status: Mapped[str] = mapped_column(String, nullable=False)

    owner_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id"), nullable=True
    )

    # List of {signal_id, source, weight, reason} — see data-model.md
    inferred_from: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    confirmed_by_user_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[timestamp_now]
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
        onupdate=text("now()"),
    )

    decisions: Mapped[list["Decision"]] = relationship(
        "Decision", back_populates="initiative", cascade="all, delete-orphan"
    )
    person_links: Mapped[list["PersonInitiative"]] = relationship(
        "PersonInitiative", back_populates="initiative", cascade="all, delete-orphan"
    )
