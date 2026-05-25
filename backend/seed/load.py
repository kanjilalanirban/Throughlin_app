"""Phase 0 seed data loader.

Refuses to run unless ENVIRONMENT in {"phase0", "local"} per data-model.md.

Run from `backend/`:
    uv run python -m seed.load
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.db import session_factory
from app.domain import (
    AuditLog,
    Decision,
    IngestionRun,
    Initiative,
    Person,
    PersonInitiative,
    Signal,
)

logger = logging.getLogger(__name__)

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

# Hand-picked engineering team — small but realistic for Phase 0 demos.
PEOPLE_FIXTURES = [
    ("E0001", "Priya Shah", "priya.shah@example.com", "Senior Engineer", "Payments", "priyashah", "5f4b001"),
    ("E0002", "Carlos Ruiz", "carlos.ruiz@example.com", "Engineering Manager", "Payments", "carlos-r", "8a2e002"),
    ("E0003", "Ana Ng", "ana.ng@example.com", "VP Engineering", "Leadership", "anang", "1b3c003"),
    ("E0004", "Marcus Chen", "marcus.chen@example.com", "Senior Engineer", "Platform", "mchen", "9d8e004"),
    ("E0005", "Aisha Patel", "aisha.patel@example.com", "Engineer", "Platform", "aishapatel", "2f4a005"),
    ("E0006", "Jonas Weber", "jonas.weber@example.com", "Staff Engineer", "Data", "jweber", "7c1d006"),
    ("E0007", "Lin Wei", "lin.wei@example.com", "Engineer", "Data", "linwei", "3e5b007"),
    ("E0008", "Sara Okonkwo", "sara.okonkwo@example.com", "Engineering Manager", "Data", "saraok", "6a9f008"),
    ("E0009", "David Kim", "david.kim@example.com", "Senior Engineer", "Platform", "dkim", "4d2c009"),
    ("E0010", "Maya Singh", "maya.singh@example.com", "Engineer", "Payments", "mayasingh", "8b7e010"),
]


async def _wipe(session) -> None:  # type: ignore[no-untyped-def]
    """Order matters — child rows first."""
    for model in (AuditLog, IngestionRun, Signal, PersonInitiative, Decision, Initiative, Person):
        await session.execute(delete(model))


async def _load_people(session) -> dict[str, Person]:  # type: ignore[no-untyped-def]
    people_by_email: dict[str, Person] = {}
    for emp_id, name, email, role, team, gh, jira in PEOPLE_FIXTURES:
        p = Person(
            id=uuid4(),
            org_id=ORG_ID,
            employee_id=emp_id,
            name=name,
            email=email,
            role=role,
            team=team,
            start_date=date(2022, 1, 1) + timedelta(days=random.randint(0, 1000)),
            status="active",
            github_handle=gh,
            jira_account_id=jira,
        )
        session.add(p)
        people_by_email[email] = p

    await session.flush()  # populates p.id

    # Manager hierarchy: Ana Ng → top; the 2 EMs → her; ICs → their EM
    ana = people_by_email["ana.ng@example.com"]
    carlos = people_by_email["carlos.ruiz@example.com"]
    sara = people_by_email["sara.okonkwo@example.com"]

    carlos.manager_id = ana.id
    sara.manager_id = ana.id

    for email in ("priya.shah@example.com", "maya.singh@example.com"):
        people_by_email[email].manager_id = carlos.id
    for email in ("jonas.weber@example.com", "lin.wei@example.com"):
        people_by_email[email].manager_id = sara.id
    # Platform team has no EM in this seed — IC-led, reports to Ana
    for email in ("marcus.chen@example.com", "aisha.patel@example.com", "david.kim@example.com"):
        people_by_email[email].manager_id = ana.id

    return people_by_email


async def _load_initiatives(session, people: dict[str, Person]) -> list[Initiative]:  # type: ignore[no-untyped-def]
    initiatives = [
        Initiative(
            id=uuid4(),
            org_id=ORG_ID,
            name="Payments platform v2",
            description="Replace legacy gateway with provider-agnostic abstraction; cut payment ops from 4 vendors to 1.",
            status="active",
            owner_id=people["carlos.ruiz@example.com"].id,
            inferred_from=[],
            confirmed_by_user_at=datetime.now(UTC),
        ),
        Initiative(
            id=uuid4(),
            org_id=ORG_ID,
            name="Data warehouse migration",
            description="Move from on-prem Vertica to Snowflake; deprecate the legacy ETL jobs.",
            status="active",
            owner_id=people["sara.okonkwo@example.com"].id,
            inferred_from=[],
            confirmed_by_user_at=datetime.now(UTC),
        ),
        Initiative(
            id=uuid4(),
            org_id=ORG_ID,
            name="Service mesh rollout",
            description="Migrate microservices to Istio. Inferred from cluster of repo activity.",
            status="proposed",
            owner_id=None,
            inferred_from=[
                {"signal_id": str(uuid4()), "source": "github", "weight": 0.7, "reason": "repo activity spike in platform-mesh"},
            ],
            confidence_score=0.72,
        ),
    ]
    for i in initiatives:
        session.add(i)
    await session.flush()
    return initiatives


async def _load_decisions(session, initiatives: list[Initiative], people: dict[str, Person]) -> None:  # type: ignore[no-untyped-def]
    decisions = [
        Decision(
            initiative_id=initiatives[0].id,
            title="Use Stripe Connect as the default provider",
            rationale="Lower per-tx fees at our scale; richer SDK; we already have a contract with Stripe via the marketplace product.",
            decided_at=datetime.now(UTC) - timedelta(days=30),
            decided_by_person_id=people["carlos.ruiz@example.com"].id,
        ),
        Decision(
            initiative_id=initiatives[1].id,
            title="Snowflake over BigQuery for the warehouse",
            rationale="Easier multi-region replication; team has Snowflake experience from prior co.",
            decided_at=datetime.now(UTC) - timedelta(days=45),
            decided_by_person_id=people["sara.okonkwo@example.com"].id,
        ),
    ]
    for d in decisions:
        session.add(d)


async def _load_person_initiative(session, initiatives: list[Initiative], people: dict[str, Person]) -> None:  # type: ignore[no-untyped-def]
    # Payments v2: Carlos owner; Priya + Maya contributors
    payments = initiatives[0]
    for email, role, strength in [
        ("carlos.ruiz@example.com", "owner", 1.0),
        ("priya.shah@example.com", "contributor", 0.6),
        ("maya.singh@example.com", "contributor", 0.4),
    ]:
        # `insert(...).on_conflict_do_nothing` is overkill here but documents the
        # right pattern for idempotent upserts.
        stmt = (
            insert(PersonInitiative)
            .values(
                person_id=people[email].id,
                initiative_id=payments.id,
                role_in_initiative=role,
                ownership_strength=strength,
            )
            .on_conflict_do_nothing(index_elements=["person_id", "initiative_id"])
        )
        await session.execute(stmt)

    # Data warehouse: Sara owner; Jonas + Lin contributors
    warehouse = initiatives[1]
    for email, role, strength in [
        ("sara.okonkwo@example.com", "owner", 1.0),
        ("jonas.weber@example.com", "contributor", 0.8),
        ("lin.wei@example.com", "contributor", 0.3),
    ]:
        stmt = (
            insert(PersonInitiative)
            .values(
                person_id=people[email].id,
                initiative_id=warehouse.id,
                role_in_initiative=role,
                ownership_strength=strength,
            )
            .on_conflict_do_nothing(index_elements=["person_id", "initiative_id"])
        )
        await session.execute(stmt)


async def _load_signals(session, initiatives: list[Initiative]) -> None:  # type: ignore[no-untyped-def]
    """Realistic-ish signals from each source. Embeddings left NULL — the
    real pipeline fills these via the embedding job."""
    now = datetime.now(UTC)
    samples = [
        ("github", "commits/abc123", "github_commit",
         {"sha": "abc123", "message": "feat(payments): wire stripe connect", "author_email": "priya.shah@example.com"},
         initiatives[0].id),
        ("github", "prs/42", "github_pr",
         {"number": 42, "title": "Stripe Connect: end-to-end happy path", "state": "merged"},
         initiatives[0].id),
        ("jira", "PAY-101", "jira_issue",
         {"key": "PAY-101", "summary": "Migrate refund flow to Connect", "status": "In Progress"},
         initiatives[0].id),
        ("jira", "DW-7", "jira_issue",
         {"key": "DW-7", "summary": "Snowflake account setup", "status": "Done"},
         initiatives[1].id),
        ("github", "commits/d4e5f6", "github_commit",
         {"sha": "d4e5f6", "message": "etl: deprecate vertica writers", "author_email": "jonas.weber@example.com"},
         initiatives[1].id),
    ]
    for source, entity_id, signal_type, payload, init_id in samples:
        session.add(
            Signal(
                org_id=ORG_ID,
                source=source,
                source_entity_id=entity_id,
                signal_type=signal_type,
                payload=payload,
                observed_at=now - timedelta(hours=random.randint(1, 48)),
                links_to_initiative_id=init_id,
                embedding=None,
            )
        )


async def seed() -> None:
    s = get_settings()
    if s.environment not in {"local", "phase0"}:
        raise RuntimeError(
            f"seed loader refuses to run with ENVIRONMENT={s.environment!r}; "
            "expected 'local' or 'phase0'"
        )

    factory = session_factory()
    async with factory() as session:
        # Sanity: hit the DB once; this also surfaces auth/network errors early.
        await session.execute(text("SELECT 1"))

        logger.info("wiping existing seed data")
        await _wipe(session)

        logger.info("loading people")
        people = await _load_people(session)

        logger.info("loading initiatives")
        initiatives = await _load_initiatives(session, people)

        logger.info("loading decisions + person_initiative + signals")
        await _load_decisions(session, initiatives, people)
        await _load_person_initiative(session, initiatives, people)
        await _load_signals(session, initiatives)

        await session.commit()
        logger.info(
            "seed complete: %d people, %d initiatives",
            len(people),
            len(initiatives),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(seed())
