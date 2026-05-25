"""People + person_initiative (join table with computed fields).

Matches docs/data-model.md.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, timestamp_now, uuid_pk

if TYPE_CHECKING:
    from app.domain.initiatives import Initiative


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="people_org_email_unique"),
        Index("people_github_idx", "github_handle", postgresql_where=text("github_handle IS NOT NULL")),
        Index("people_jira_idx", "jira_account_id", postgresql_where=text("jira_account_id IS NOT NULL")),
    )

    id: Mapped[uuid_pk]
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    employee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    manager_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id"), nullable=True
    )
    team: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'active'")
    )  # active|on_leave|departed
    github_handle: Mapped[str | None] = mapped_column(String, nullable=True)
    jira_account_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[timestamp_now]
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
        onupdate=text("now()"),
    )


class PersonInitiative(Base):
    __tablename__ = "person_initiative"

    person_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    )
    initiative_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("initiatives.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # owner | contributor | reviewer | stakeholder
    role_in_initiative: Mapped[str | None] = mapped_column(String, nullable=True)
    ownership_strength: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    knowledge_concentration_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    last_computed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    person: Mapped["Person"] = relationship("Person")
    initiative: Mapped["Initiative"] = relationship("Initiative", back_populates="person_links")
