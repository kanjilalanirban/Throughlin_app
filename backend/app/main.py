"""Company Brain backend entry point."""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import dispose_engine, session_factory
from app.core.errors import register_exception_handlers
from app.core.otel import setup_otel

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Load + cache settings once (touches Secrets Manager in AWS)
    get_settings()
    # OTel setup needs the DB engine, which needs settings — keep order.
    setup_otel(app)
    logger.info("backend started")
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("backend shut down cleanly")


app = FastAPI(title="Company Brain", version="0.1.2", lifespan=lifespan)

# Phase 0: allow any origin (the frontend is on S3, the API on rotating ALB DNS).
# Phase 1: tighten to the production domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Attach a correlation id to every request — used by error responses."""
    cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    request.state.correlation_id = cid
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = cid
    return response


register_exception_handlers(app)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Does NOT touch the DB — kept cheap for the ALB."""
    return {
        "status": "ok",
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "region": os.environ.get("AWS_REGION", "unknown"),
        "version": app.version,
    }


@app.get("/readiness")
async def readiness() -> dict[str, str]:
    """Readiness probe. Pings the DB to confirm we can serve traffic.

    Use this from internal tooling; the ALB target group still watches /health.
    """
    factory = session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()
    return {"status": "ready", "db": "ok"}
