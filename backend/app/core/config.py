"""Application configuration.

Sources, in order of precedence:
1. Environment variables (always wins — used by local dev and overrides in ECS).
2. AWS Secrets Manager (for DB credentials + Anthropic key in deployed env).
3. Defaults coded here.

Loaded once at app startup via `get_settings()`. Do NOT re-fetch per request.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration. All fields are read from env at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # Environment
    # -------------------------------------------------------------------------
    environment: Literal["local", "phase0"] = "local"
    aws_region: str = "ca-central-1"
    log_level: str = "INFO"

    # -------------------------------------------------------------------------
    # Database
    #
    # For local dev: set DATABASE_URL directly (e.g. via .env), e.g.
    #   postgresql+asyncpg://companybrain:companybrain@localhost:5432/companybrain
    #
    # In AWS: leave DATABASE_URL empty and supply RDS_SECRET_ARN; we'll
    # fetch host/port/user/password from Secrets Manager and construct the URL.
    # -------------------------------------------------------------------------
    database_url: str = ""
    rds_secret_arn: str = ""
    rds_database_name: str = "companybrain"

    # -------------------------------------------------------------------------
    # LLM (Anthropic)
    #
    # Local: set ANTHROPIC_API_KEY directly.
    # AWS:   set ANTHROPIC_SECRET_ARN to a Secrets Manager secret whose value
    #        is the raw API key string (no JSON wrapper).
    # -------------------------------------------------------------------------
    anthropic_api_key: str = ""
    anthropic_secret_arn: str = ""
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"

    # -------------------------------------------------------------------------
    # Auth (Cognito)
    # -------------------------------------------------------------------------
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    # -------------------------------------------------------------------------
    # OpenTelemetry
    # -------------------------------------------------------------------------
    otel_service_name: str = "companybrain-backend"
    otel_exporter_otlp_endpoint: str = ""  # set in ECS via ADOT sidecar

    # -------------------------------------------------------------------------
    # Single-tenant Phase 0 org_id (every row carries this).
    # Phase 1: replaced by JWT-claim-derived org_id.
    # -------------------------------------------------------------------------
    default_org_id: str = "00000000-0000-0000-0000-000000000001"


def _fetch_secret_string(secret_arn: str, region: str) -> str:
    """Read a Secrets Manager secret as a raw string. Raises on failure."""
    client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = client.get_secret_value(SecretId=secret_arn)
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"failed to read secret {secret_arn}: {e}") from e
    value = resp.get("SecretString")
    if not value:
        raise RuntimeError(f"secret {secret_arn} has no SecretString")
    return value


def _fetch_ssm_parameter(name: str, region: str) -> str:
    """Read an SSM parameter as a string. Raises on failure."""
    client = boto3.client("ssm", region_name=region)
    try:
        resp = client.get_parameter(Name=name)
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"failed to read SSM parameter {name}: {e}") from e
    return resp["Parameter"]["Value"]


def _resolve_database_url(s: Settings) -> str:
    """Resolve the final database URL, fetching pieces from AWS if needed.

    The RDS-managed master user secret only contains {"username", "password"} —
    the host and port come from SSM (the cross-repo contract), or from the
    RDS_HOST / RDS_PORT env vars if you want to bypass SSM.
    """
    if s.database_url:
        return s.database_url
    if not s.rds_secret_arn:
        raise RuntimeError(
            "either DATABASE_URL or RDS_SECRET_ARN must be set; got neither"
        )
    raw = _fetch_secret_string(s.rds_secret_arn, s.aws_region)
    creds = json.loads(raw)
    username = quote_plus(creds["username"])
    password = quote_plus(creds["password"])

    # Host + port: prefer env vars, fall back to SSM (the cross-repo contract).
    import os

    host = os.environ.get("RDS_HOST") or _fetch_ssm_parameter(
        "/companybrain/phase0/rds/address", s.aws_region
    )
    port_str = os.environ.get("RDS_PORT") or _fetch_ssm_parameter(
        "/companybrain/phase0/rds/port", s.aws_region
    )
    port = int(port_str)
    dbname = s.rds_database_name
    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{dbname}"


def _resolve_anthropic_api_key(s: Settings) -> str:
    """Resolve the Anthropic API key, fetching from Secrets Manager if needed."""
    if s.anthropic_api_key:
        return s.anthropic_api_key
    if not s.anthropic_secret_arn:
        return ""  # tolerated for /health-only deployments
    return _fetch_secret_string(s.anthropic_secret_arn, s.aws_region).strip()


def _ssm_or_empty(name: str, region: str) -> str:
    """Best-effort SSM read; returns empty string if the parameter is absent."""
    try:
        return _fetch_ssm_parameter(name, region)
    except RuntimeError:
        return ""


def _populate_ssm_fallbacks(s: Settings) -> None:
    """If a secret/identifier field is unset, try the well-known SSM path.

    Means the Fargate task def only needs ENVIRONMENT + AWS_REGION; everything
    else gets discovered at startup via the cross-repo SSM contract.
    """
    if s.environment != "phase0":
        return  # Local dev uses env vars; don't reach for SSM.

    prefix = "/companybrain/phase0"
    if not s.rds_secret_arn:
        s.rds_secret_arn = _ssm_or_empty(f"{prefix}/rds/secret_arn", s.aws_region)
    if not s.anthropic_secret_arn and not s.anthropic_api_key:
        s.anthropic_secret_arn = _ssm_or_empty(f"{prefix}/secrets/anthropic_arn", s.aws_region)
    if not s.cognito_user_pool_id:
        s.cognito_user_pool_id = _ssm_or_empty(f"{prefix}/cognito/user_pool_id", s.aws_region)
    if not s.cognito_client_id:
        s.cognito_client_id = _ssm_or_empty(f"{prefix}/cognito/client_id", s.aws_region)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings. Call at startup; do not re-call per request."""
    s = Settings()
    _populate_ssm_fallbacks(s)
    s.database_url = _resolve_database_url(s)
    s.anthropic_api_key = _resolve_anthropic_api_key(s)
    logger.info(
        "settings loaded",
        extra={
            "environment": s.environment,
            "region": s.aws_region,
            "db_host": s.database_url.split("@", 1)[-1].split("/", 1)[0],
            "anthropic_key_set": bool(s.anthropic_api_key),
            "cognito_configured": bool(s.cognito_user_pool_id and s.cognito_client_id),
        },
    )
    return s
