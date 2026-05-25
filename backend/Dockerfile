# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the FastAPI backend.
# Builder installs all production deps (from uv.lock) into a venv.
# Runtime copies only the venv + app + alembic + seed into a slim base.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install deps first (cached across code changes that don't touch lock/pyproject)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv sync --frozen --no-dev --no-install-project

# Application code
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY seed ./seed

# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# Entrypoint: run alembic upgrade head before serving. Idempotent — subsequent
# task starts (after the first applies the migrations) see "already at head".
COPY --chown=app:app entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
