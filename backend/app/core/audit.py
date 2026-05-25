"""Audit logging — write to the audit_log table on every org-data read/write.

Phase 0 rule from security.md: "Audit log every read and write of organizational
data. No exceptions." Records metadata only; never the query content.

Usage as a decorator on FastAPI endpoint functions:

    @router.get("/initiatives/{initiative_id}")
    @audit_logged(action="read_initiative", target_type="initiative")
    async def get_initiative(initiative_id: UUID, db: DbSession, user: CurrentUser):
        ...

The decorator inspects path/query params for a `{target_type}_id` and uses
it as `target_id`. To pin a different param name, pass `target_id_param`.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_log import AuditLog

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def audit_logged(
    action: str,
    *,
    target_type: str | None = None,
    target_id_param: str | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator: record an audit_log row after the wrapped endpoint succeeds.

    Requires the endpoint to have a `db: AsyncSession` kwarg (via FastAPI's
    Depends(get_db)) and a `user_id: UUID | None` resolvable from the
    `user` kwarg (via CurrentUser dependency). Both are looked up by name.
    """
    inferred_param = target_id_param or (f"{target_type}_id" if target_type else None)

    def decorator(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await fn(*args, **kwargs)
            try:
                db: AsyncSession | None = kwargs.get("db")  # type: ignore[assignment]
                user: Any = kwargs.get("user")
                user_id: UUID | None = getattr(user, "id", None) if user is not None else None

                target_id: UUID | None = None
                if inferred_param and inferred_param in kwargs:
                    raw = kwargs[inferred_param]
                    target_id = raw if isinstance(raw, UUID) else None

                if db is not None:
                    db.add(
                        AuditLog(
                            user_id=user_id,
                            action=action,
                            target_type=target_type,
                            target_id=target_id,
                            payload=None,
                        )
                    )
                    # `get_db` commits on successful exit, so we don't commit here.
            except Exception:
                # An audit-log failure must not break the user-facing response.
                logger.exception("audit_log write failed", extra={"action": action})
            return result

        return wrapper

    return decorator
