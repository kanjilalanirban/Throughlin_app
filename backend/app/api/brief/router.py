"""Brief surface — placeholder until the LLM-backed brief generator lands.

Returns a synthesized markdown brief based on current DB state so the
frontend has real content to render and a stable response shape.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.auth import OptionalUserDep
from app.core.db import DbSession
from app.core.tenant import current_org_id
from app.domain import Decision, Initiative, Person, Signal

router = APIRouter(prefix="/api/brief", tags=["brief"])


class BriefRequest(BaseModel):
    period: Literal["last_week", "last_month"] = "last_week"


class BriefResponse(BaseModel):
    generated_at: datetime
    period_start: date
    period_end: date
    markdown: str
    placeholder: bool = True


@router.post("", response_model=BriefResponse)
async def generate_brief(
    payload: BriefRequest, db: DbSession, user: OptionalUserDep
) -> BriefResponse:
    now = datetime.now(UTC)
    days = 7 if payload.period == "last_week" else 30
    since = now - timedelta(days=days)
    org = current_org_id()

    # Quick counts to weave into the brief
    init_total = (
        await db.execute(select(func.count()).select_from(Initiative).where(Initiative.org_id == org))
    ).scalar_one()
    init_active = (
        await db.execute(
            select(func.count())
            .select_from(Initiative)
            .where(Initiative.org_id == org, Initiative.status == "active")
        )
    ).scalar_one()
    new_signals = (
        await db.execute(
            select(func.count())
            .select_from(Signal)
            .where(Signal.org_id == org, Signal.observed_at >= since)
        )
    ).scalar_one()
    people_count = (
        await db.execute(select(func.count()).select_from(Person).where(Person.org_id == org))
    ).scalar_one()
    decisions_at_risk = (
        await db.execute(
            select(func.count())
            .select_from(Decision)
            .join(Initiative, Decision.initiative_id == Initiative.id)
            .where(Initiative.org_id == org, Decision.still_valid.is_(False))
        )
    ).scalar_one()

    # Top active initiatives by recent signal volume
    top = (
        await db.execute(
            select(Initiative.name, func.count(Signal.id).label("signal_count"))
            .join(Signal, Signal.links_to_initiative_id == Initiative.id, isouter=True)
            .where(Initiative.org_id == org, Initiative.status == "active")
            .group_by(Initiative.id, Initiative.name)
            .order_by(func.count(Signal.id).desc())
            .limit(5)
        )
    ).all()

    top_lines = (
        "\n".join(f"- **{name}** — {count} recent signals" for name, count in top)
        if top
        else "_No active initiatives with recent signals._"
    )

    markdown = f"""# Executive briefing — {payload.period.replace('_', ' ')}

**Period:** {since.date().isoformat()} → {now.date().isoformat()}

## Headline numbers

- {init_active}/{init_total} initiatives active
- {new_signals} new signals in the period
- {people_count} people tracked
- {decisions_at_risk} decisions flagged as no-longer-valid

## Top initiatives by signal volume

{top_lines}

## Risks & open questions

_This section will be populated by the LLM-backed brief generator when it lands.
Today's placeholder shows you the wire shape and gives you something to look
at on the page._

---
*Generated {now.isoformat()} (placeholder — LLM coming soon).*
"""

    return BriefResponse(
        generated_at=now,
        period_start=since.date(),
        period_end=now.date(),
        markdown=markdown,
        placeholder=True,
    )
