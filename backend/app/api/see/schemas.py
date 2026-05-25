"""Pydantic response models for the See API.

These are read-only projections of the domain models. Keep them flat and
deliberate — don't auto-derive from the SQLAlchemy classes; the wire
contract should be explicit so we can evolve the schema without leaking
internals.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InitiativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: str
    owner_id: UUID | None
    confidence_score: Decimal | None
    confirmed_by_user_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InitiativeDetail(InitiativeOut):
    inferred_from: list[dict[str, Any]]
    decisions: list["DecisionOut"]
    people: list["PersonInitiativeOut"]


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str | None
    team: str | None
    status: str
    manager_id: UUID | None
    github_handle: str | None
    jira_account_id: str | None
    start_date: date | None


class PersonInitiativeOut(BaseModel):
    """A person's relationship to an initiative — surfaced inside InitiativeDetail."""

    person_id: UUID
    person_name: str
    role_in_initiative: str | None
    ownership_strength: Decimal | None
    knowledge_concentration_score: Decimal | None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    initiative_id: UUID
    title: str
    rationale: str
    decided_at: datetime
    decided_by_person_id: UUID | None
    still_valid: bool | None
    last_validated_at: datetime | None


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    source_entity_id: str
    signal_type: str
    payload: dict[str, Any]
    observed_at: datetime
    links_to_initiative_id: UUID | None


class DashboardStats(BaseModel):
    initiatives_total: int
    initiatives_active: int
    initiatives_proposed: int
    people_total: int
    people_active: int
    decisions_total: int
    decisions_still_valid: int
    decisions_invalid: int
    signals_total: int
    signals_last_24h: int


# Forward refs
InitiativeDetail.model_rebuild()
