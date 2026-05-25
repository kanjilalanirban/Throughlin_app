"""OpenTelemetry setup.

In AWS we export via ADOT (the OTLP endpoint is set by ECS env vars).
Locally we skip exporter setup unless OTEL_EXPORTER_OTLP_ENDPOINT is set —
this keeps `pnpm dev` from spamming the console with export errors.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import get_settings
from app.core.db import engine

logger = logging.getLogger(__name__)


def setup_otel(app: FastAPI) -> None:
    """Configure OTel tracer + auto-instrument FastAPI, SQLAlchemy, httpx."""
    s = get_settings()

    resource = Resource.create({SERVICE_NAME: s.otel_service_name})
    provider = TracerProvider(resource=resource)

    if s.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=s.otel_exporter_otlp_endpoint))
        )
        logger.info(f"OTel exporter configured: {s.otel_exporter_otlp_endpoint}")
    else:
        logger.info("OTel exporter not configured (no OTEL_EXPORTER_OTLP_ENDPOINT); spans dropped")

    trace.set_tracer_provider(provider)

    # Auto-instrument
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    # SQLAlchemy needs the sync engine handle; AsyncEngine exposes it via .sync_engine.
    SQLAlchemyInstrumentor().instrument(engine=engine().sync_engine)


def get_tracer(name: str) -> trace.Tracer:
    """Get a named tracer for manual spans (LLM calls, retrieval, etc.)."""
    return trace.get_tracer(name)
