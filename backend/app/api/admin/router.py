"""Admin surface — integration status + HRIS CSV upload.

Phase 0:
- Jira/GitHub status reports whether the secret container has a value set.
  Actual OAuth setup + GitHub App install flow is on the Phase 0 tail.
- HRIS CSV upload accepts a file and upserts rows into `people`. The full
  S3-trigger-Lambda pipeline (docs/integrations.md) lands later; right now
  this is a direct upload-to-DB path so the See pages have real data.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, UploadFile
from sqlalchemy import select

from app.api.admin.schemas import (
    HrisCsvUploadResult,
    IntegrationsResponse,
    IntegrationStatus,
)
from app.core.auth import OptionalUserDep
from app.core.config import get_settings
from app.core.db import DbSession
from app.core.errors import BadRequest
from app.core.tenant import current_org_id
from app.domain import IngestionRun, Person

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _secret_is_populated(arn: str, region: str) -> bool:
    """Returns True if the secret container has a current value set."""
    if not arn:
        return False
    client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = client.describe_secret(SecretId=arn)
    except ClientError:
        return False
    return "AWSCURRENT" in (
        s for stages in resp.get("VersionIdsToStages", {}).values() for s in stages
    )


@router.get("/integrations", response_model=IntegrationsResponse)
async def integrations_status(db: DbSession, user: OptionalUserDep) -> IntegrationsResponse:
    s = get_settings()

    # Look up the most recent ingestion run per source
    last_runs: dict[str, IngestionRun] = {}
    rows = (await db.execute(select(IngestionRun))).scalars().all()
    for run in rows:
        prior = last_runs.get(run.source)
        if prior is None or run.started_at > prior.started_at:
            last_runs[run.source] = run

    def status(name, label, arn_attr, description):  # type: ignore[no-untyped-def]
        run = last_runs.get(name)
        return IntegrationStatus(
            name=name,
            label=label,
            configured=_secret_is_populated(getattr(s, arn_attr) or "", s.aws_region)
            if name != "hris"
            else True,  # HRIS doesn't use a secret; it's CSV upload
            description=description,
            last_run_at=run.started_at if run else None,
            last_run_status=run.status if run else None,
            records_processed_last_run=run.records_processed if run else None,
        )

    return IntegrationsResponse(
        integrations=[
            status(
                "jira",
                "Jira",
                "jira_oauth_secret_arn",  # may not exist on Settings yet
                "Issues, epics, sprints, comments. Polled every 30 min.",
            ),
            status(
                "github",
                "GitHub",
                "github_app_secret_arn",
                "Commits, PRs, reviews, members. Polled every 30 min.",
            ),
            status(
                "hris",
                "HRIS (CSV)",
                "hris_secret_arn",
                "People + reporting lines. Upload a CSV; rows upsert into the people table.",
            ),
        ]
    )


_REQUIRED_CSV_COLUMNS = {"employee_id", "name", "email", "role", "team", "status"}


@router.post("/integrations/hris/upload", response_model=HrisCsvUploadResult)
async def upload_hris_csv(
    file: UploadFile,
    db: DbSession,
    user: OptionalUserDep,
) -> HrisCsvUploadResult:
    if not file.filename or not file.filename.endswith(".csv"):
        raise BadRequest("expected a .csv file")

    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    if reader.fieldnames is None or not _REQUIRED_CSV_COLUMNS.issubset(reader.fieldnames):
        missing = _REQUIRED_CSV_COLUMNS - set(reader.fieldnames or [])
        raise BadRequest(f"CSV is missing required columns: {sorted(missing)}")

    org = current_org_id()
    started_at = datetime.now(tz=None)
    upserted = 0
    errors: list[str] = []

    # Read all CSV rows, then upsert
    emails_in_file: set[str] = set()
    for i, row in enumerate(reader, start=2):  # row 1 = header
        try:
            email = (row.get("email") or "").strip().lower()
            if not email:
                errors.append(f"row {i}: missing email")
                continue
            emails_in_file.add(email)

            existing = (
                await db.execute(
                    select(Person).where(Person.org_id == org, Person.email == email)
                )
            ).scalar_one_or_none()

            start_date_raw = (row.get("start_date") or "").strip()
            start_date_parsed: date | None = None
            if start_date_raw:
                try:
                    start_date_parsed = date.fromisoformat(start_date_raw)
                except ValueError:
                    errors.append(f"row {i}: invalid start_date '{start_date_raw}'")

            fields = dict(
                employee_id=(row.get("employee_id") or "").strip() or None,
                name=(row.get("name") or "").strip(),
                email=email,
                role=(row.get("role") or "").strip() or None,
                team=(row.get("team") or "").strip() or None,
                status=((row.get("status") or "active").strip() or "active"),
                github_handle=(row.get("github_handle") or "").strip() or None,
                jira_account_id=(row.get("jira_account_id") or "").strip() or None,
                start_date=start_date_parsed,
            )

            if existing is None:
                p = Person(id=uuid4(), org_id=org, **fields)
                db.add(p)
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)
            upserted += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"row {i}: {e}")

    # Mark anyone not in this CSV as "departed"
    all_people = (await db.execute(select(Person).where(Person.org_id == org))).scalars().all()
    departed_flagged = 0
    for p in all_people:
        if p.email not in emails_in_file and p.status != "departed":
            p.status = "departed"
            departed_flagged += 1

    # Record the ingestion run
    db.add(
        IngestionRun(
            source="hris",
            started_at=started_at,
            completed_at=datetime.now(tz=None),
            status="success" if not errors else "partial",
            records_processed=upserted,
            errors=[{"message": e} for e in errors],
        )
    )

    return HrisCsvUploadResult(
        upserted=upserted, departed_flagged=departed_flagged, errors=errors
    )
