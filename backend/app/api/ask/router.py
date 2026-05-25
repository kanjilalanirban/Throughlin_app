"""Ask surface — placeholder until the LLM client + retrieval land.

For now, returns a synthesized response that lists initiative names matching
the query (simple ILIKE), so the frontend has something real to render and
the request/response shape is fixed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.auth import OptionalUserDep
from app.core.db import DbSession
from app.core.tenant import current_org_id
from app.domain import Initiative

router = APIRouter(prefix="/api/ask", tags=["ask"])


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


class AskCitation(BaseModel):
    kind: str
    id: str
    name: str


class AskResponse(BaseModel):
    answer: str
    citations: list[AskCitation]
    model: str
    latency_ms: int
    placeholder: bool = True


@router.post("", response_model=AskResponse)
async def ask(payload: AskRequest, db: DbSession, user: OptionalUserDep) -> AskResponse:
    """PLACEHOLDER. The real implementation calls retrieval.py → llm_client.py.

    For now: ILIKE on initiative names + descriptions; return them as citations
    and a canned answer string. Good enough to exercise the wire format.
    """
    started = datetime.now(UTC)
    org = current_org_id()
    q = f"%{payload.query.strip()}%"

    inits = (
        await db.execute(
            select(Initiative)
            .where(Initiative.org_id == org)
            .where((Initiative.name.ilike(q)) | (Initiative.description.ilike(q)))
            .limit(5)
        )
    ).scalars().all()

    citations = [
        AskCitation(kind="initiative", id=str(i.id), name=i.name) for i in inits
    ]

    if citations:
        names = ", ".join(c.name for c in citations)
        answer = (
            f"I found {len(citations)} initiative(s) that look related to "
            f'"{payload.query}": {names}. '
            "[This is a placeholder response — the LLM-backed Ask pipeline "
            "lands in the next milestone.]"
        )
    else:
        answer = (
            f"No initiatives matched \"{payload.query}\" by name or description. "
            "Once the embedding pipeline is wired, semantic search will widen "
            "the recall here."
        )

    latency = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return AskResponse(
        answer=answer,
        citations=citations,
        model="placeholder",
        latency_ms=latency,
        placeholder=True,
    )
