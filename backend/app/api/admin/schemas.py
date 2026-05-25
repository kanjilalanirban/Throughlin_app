"""Admin API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    name: Literal["jira", "github", "hris"]
    label: str
    configured: bool
    description: str
    last_run_at: datetime | None
    last_run_status: str | None
    records_processed_last_run: int | None


class IntegrationsResponse(BaseModel):
    integrations: list[IntegrationStatus]


class HrisCsvUploadResult(BaseModel):
    upserted: int
    departed_flagged: int
    errors: list[str]
