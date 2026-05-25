"""Tenant scoping (Phase 0 single-tenant; Phase 1 multi-tenant via Postgres RLS).

Every read/write against an org-scoped table MUST be filtered by `org_id`.
Helpers:

    `current_org_id()`  — returns the org for the current request (contextvar).
    `set_current_org()` — sets it (called by the auth dependency in main.py).
    `org_scoped(stmt)`  — adds the `org_id = :current` predicate to a Select.

In Phase 0 there is only one org, populated from `settings.default_org_id`.
In Phase 1, set_current_org() is called from a JWT claim (org).
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import Select

from app.core.errors import Forbidden

_current_org: ContextVar[UUID | None] = ContextVar("current_org", default=None)


def set_current_org(org_id: UUID) -> None:
    _current_org.set(org_id)


def current_org_id() -> UUID:
    """Return the org_id for this request. Raises Forbidden if not set."""
    org = _current_org.get()
    if org is None:
        raise Forbidden("no org_id in request context")
    return org


def org_scoped(stmt: Select, column) -> Select:  # type: ignore[no-untyped-def]
    """Add a `column == current_org_id()` predicate to a Select.

    Use as:
        stmt = select(Initiative)
        stmt = org_scoped(stmt, Initiative.org_id)
    """
    return stmt.where(column == current_org_id())
