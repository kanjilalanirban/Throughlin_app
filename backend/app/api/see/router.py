"""See surface — read-only API over the four primitives.

Phase 0: uses optional_user (no enforcement) so the frontend can be built
before the login flow lands. Tighten to require_user in the next pass.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.see.schemas import (
    DashboardStats,
    DecisionOut,
    InitiativeDetail,
    InitiativeOut,
    PersonInitiativeOut,
    PersonOut,
    SignalOut,
)
from app.core.auth import OptionalUserDep
from app.core.db import DbSession
from app.core.errors import NotFound
from app.core.tenant import current_org_id
from app.domain import Decision, Initiative, Person, PersonInitiative, Signal

router = APIRouter(prefix="/api/see", tags=["see"])


# ----------------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------------
@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: DbSession, user: OptionalUserDep) -> DashboardStats:
    org = current_org_id()
    last_24h = datetime.now(UTC) - timedelta(hours=24)

    async def scalar(stmt) -> int:  # type: ignore[no-untyped-def]
        return (await db.execute(stmt)).scalar_one()

    return DashboardStats(
        initiatives_total=await scalar(
            select(func.count()).select_from(Initiative).where(Initiative.org_id == org)
        ),
        initiatives_active=await scalar(
            select(func.count())
            .select_from(Initiative)
            .where(Initiative.org_id == org, Initiative.status == "active")
        ),
        initiatives_proposed=await scalar(
            select(func.count())
            .select_from(Initiative)
            .where(Initiative.org_id == org, Initiative.status == "proposed")
        ),
        people_total=await scalar(
            select(func.count()).select_from(Person).where(Person.org_id == org)
        ),
        people_active=await scalar(
            select(func.count())
            .select_from(Person)
            .where(Person.org_id == org, Person.status == "active")
        ),
        decisions_total=await scalar(
            select(func.count())
            .select_from(Decision)
            .join(Initiative, Decision.initiative_id == Initiative.id)
            .where(Initiative.org_id == org)
        ),
        decisions_still_valid=await scalar(
            select(func.count())
            .select_from(Decision)
            .join(Initiative, Decision.initiative_id == Initiative.id)
            .where(Initiative.org_id == org, Decision.still_valid.is_(True))
        ),
        decisions_invalid=await scalar(
            select(func.count())
            .select_from(Decision)
            .join(Initiative, Decision.initiative_id == Initiative.id)
            .where(Initiative.org_id == org, Decision.still_valid.is_(False))
        ),
        signals_total=await scalar(
            select(func.count()).select_from(Signal).where(Signal.org_id == org)
        ),
        signals_last_24h=await scalar(
            select(func.count())
            .select_from(Signal)
            .where(Signal.org_id == org, Signal.observed_at >= last_24h)
        ),
    )


# ----------------------------------------------------------------------------
# Initiatives
# ----------------------------------------------------------------------------
@router.get("/initiatives", response_model=list[InitiativeOut])
async def list_initiatives(db: DbSession, user: OptionalUserDep) -> list[InitiativeOut]:
    org = current_org_id()
    stmt = (
        select(Initiative)
        .where(Initiative.org_id == org)
        .order_by(Initiative.updated_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [InitiativeOut.model_validate(r) for r in rows]


@router.get("/initiatives/{initiative_id}", response_model=InitiativeDetail)
async def get_initiative(
    initiative_id: UUID, db: DbSession, user: OptionalUserDep
) -> InitiativeDetail:
    org = current_org_id()
    stmt = (
        select(Initiative)
        .where(Initiative.id == initiative_id, Initiative.org_id == org)
        .options(
            selectinload(Initiative.decisions),
            selectinload(Initiative.person_links).selectinload(PersonInitiative.person),
        )
    )
    init = (await db.execute(stmt)).scalar_one_or_none()
    if init is None:
        raise NotFound(f"initiative {initiative_id} not found")

    return InitiativeDetail(
        id=init.id,
        name=init.name,
        description=init.description,
        status=init.status,
        owner_id=init.owner_id,
        confidence_score=init.confidence_score,
        confirmed_by_user_at=init.confirmed_by_user_at,
        created_at=init.created_at,
        updated_at=init.updated_at,
        inferred_from=init.inferred_from,
        decisions=[DecisionOut.model_validate(d) for d in init.decisions],
        people=[
            PersonInitiativeOut(
                person_id=pl.person_id,
                person_name=pl.person.name,
                role_in_initiative=pl.role_in_initiative,
                ownership_strength=pl.ownership_strength,
                knowledge_concentration_score=pl.knowledge_concentration_score,
            )
            for pl in init.person_links
        ],
    )


# ----------------------------------------------------------------------------
# People
# ----------------------------------------------------------------------------
@router.get("/people", response_model=list[PersonOut])
async def list_people(db: DbSession, user: OptionalUserDep) -> list[PersonOut]:
    org = current_org_id()
    stmt = (
        select(Person).where(Person.org_id == org).order_by(Person.name.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [PersonOut.model_validate(r) for r in rows]


@router.get("/people/{person_id}", response_model=PersonOut)
async def get_person(person_id: UUID, db: DbSession, user: OptionalUserDep) -> PersonOut:
    org = current_org_id()
    stmt = select(Person).where(Person.id == person_id, Person.org_id == org)
    p = (await db.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise NotFound(f"person {person_id} not found")
    return PersonOut.model_validate(p)


# ----------------------------------------------------------------------------
# Decisions
# ----------------------------------------------------------------------------
@router.get("/decisions", response_model=list[DecisionOut])
async def list_decisions(db: DbSession, user: OptionalUserDep) -> list[DecisionOut]:
    org = current_org_id()
    stmt = (
        select(Decision)
        .join(Initiative, Decision.initiative_id == Initiative.id)
        .where(Initiative.org_id == org)
        .order_by(Decision.decided_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [DecisionOut.model_validate(r) for r in rows]


# ----------------------------------------------------------------------------
# Signals
# ----------------------------------------------------------------------------
@router.get("/signals", response_model=list[SignalOut])
async def list_signals(
    db: DbSession,
    user: OptionalUserDep,
    initiative_id: UUID | None = None,
    limit: int = 100,
) -> list[SignalOut]:
    org = current_org_id()
    stmt = select(Signal).where(Signal.org_id == org)
    if initiative_id is not None:
        stmt = stmt.where(Signal.links_to_initiative_id == initiative_id)
    stmt = stmt.order_by(Signal.observed_at.desc()).limit(max(1, min(limit, 500)))
    rows = (await db.execute(stmt)).scalars().all()
    return [SignalOut.model_validate(r) for r in rows]
