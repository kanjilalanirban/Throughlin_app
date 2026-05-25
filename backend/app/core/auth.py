"""Cognito JWT verification.

Validates the `Authorization: Bearer <token>` header against the configured
Cognito user pool's JWKS (cached at startup). Returns a `CurrentUser`
pydantic model with the extracted claims.

In Phase 0 with a single tenant, every authenticated user is mapped to
`settings.default_org_id`. Phase 1: org comes from a custom JWT claim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, Header
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.errors import Unauthorized
from app.core.tenant import set_current_org

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CurrentUser:
    """The authenticated principal for a request."""

    id: UUID  # the `sub` claim parsed as UUID (Cognito stores it as a UUID string)
    username: str
    email: str | None
    org_id: UUID
    claims: dict[str, Any]


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    s = get_settings()
    if not s.cognito_user_pool_id:
        raise Unauthorized("Cognito user pool not configured")
    jwks_url = (
        f"https://cognito-idp.{s.aws_region}.amazonaws.com/"
        f"{s.cognito_user_pool_id}/.well-known/jwks.json"
    )
    # PyJWKClient caches keys in-process by `kid`.
    return PyJWKClient(jwks_url)


def _verify_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
    except (jwt.PyJWKClientError, httpx.HTTPError) as e:
        raise Unauthorized("failed to fetch signing key") from e

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=s.cognito_client_id or None,
            options={"verify_aud": bool(s.cognito_client_id)},
            issuer=(
                f"https://cognito-idp.{s.aws_region}.amazonaws.com/{s.cognito_user_pool_id}"
            ),
        )
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("token expired") from e
    except jwt.PyJWTError as e:
        raise Unauthorized(f"invalid token: {e}") from e
    return claims


async def require_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """FastAPI dependency: validates the bearer token, returns the principal."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("missing bearer token")
    token = authorization.split(None, 1)[1].strip()
    claims = _verify_token(token)

    s = get_settings()
    try:
        sub = UUID(claims["sub"])
    except (KeyError, ValueError) as e:
        raise Unauthorized("token missing valid 'sub' claim") from e

    org_id = UUID(s.default_org_id)
    set_current_org(org_id)

    return CurrentUser(
        id=sub,
        username=claims.get("cognito:username") or claims.get("username") or str(sub),
        email=claims.get("email"),
        org_id=org_id,
        claims=claims,
    )


# Convenience typed dependency
CurrentUserDep = Annotated[CurrentUser, Depends(require_user)]
