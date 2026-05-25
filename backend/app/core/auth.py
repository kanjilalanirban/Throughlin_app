"""Cognito JWT verification.

Validates the `Authorization: Bearer <token>` header against the configured
Cognito user pool's JWKS. Returns a CurrentUser with extracted claims.

Two FastAPI dependencies:
- require_user:  401 if no/invalid token.
- optional_user: returns None if no token; validates if present. Use for
                 Phase 0 endpoints we want to keep open while the frontend
                 login flow is still being built. Tighten to require_user
                 later by swapping the dependency.
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

    id: UUID
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
    return PyJWKClient(jwks_url)


def _verify_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
    except (jwt.PyJWKClientError, httpx.HTTPError) as e:
        raise Unauthorized("failed to fetch signing key") from e

    # Cognito issues two token types:
    #   - ID token:     `aud` = app client id
    #   - Access token: `client_id` in claims, no `aud`
    # We accept either; verify accordingly.
    unverified = jwt.decode(token, options={"verify_signature": False})
    is_access = unverified.get("token_use") == "access"

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=None if is_access else (s.cognito_client_id or None),
            options={"verify_aud": (not is_access) and bool(s.cognito_client_id)},
            issuer=(
                f"https://cognito-idp.{s.aws_region}.amazonaws.com/{s.cognito_user_pool_id}"
            ),
        )
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("token expired") from e
    except jwt.PyJWTError as e:
        raise Unauthorized(f"invalid token: {e}") from e

    if is_access and s.cognito_client_id and claims.get("client_id") != s.cognito_client_id:
        raise Unauthorized("token client_id mismatch")
    return claims


def _user_from_claims(claims: dict[str, Any]) -> CurrentUser:
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


async def require_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Strict: requires a valid bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("missing bearer token")
    token = authorization.split(None, 1)[1].strip()
    claims = _verify_token(token)
    return _user_from_claims(claims)


async def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser | None:
    """Permissive: returns None when no/invalid token. Use during Phase 0
    bring-up while the frontend login flow is still being wired."""
    if not authorization or not authorization.lower().startswith("bearer "):
        # Still set the default org so org_scoped() works.
        s = get_settings()
        set_current_org(UUID(s.default_org_id))
        return None
    token = authorization.split(None, 1)[1].strip()
    try:
        claims = _verify_token(token)
    except Unauthorized:
        s = get_settings()
        set_current_org(UUID(s.default_org_id))
        return None
    return _user_from_claims(claims)


CurrentUserDep = Annotated[CurrentUser, Depends(require_user)]
OptionalUserDep = Annotated[CurrentUser | None, Depends(optional_user)]
