# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the FastAPI backend.
# Builder stage uses uv to install deps into a venv; runtime stage copies
# only the venv + app code into a slim Python image.

FROM python:3.12-slim AS builder

# uv: fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install deps first (cached across code changes)
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv pip install --no-deps fastapi uvicorn[standard] && \
    uv pip install fastapi uvicorn[standard]

# Copy application code
COPY app ./app

# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 app

WORKDIR /app

# Copy venv + code from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/app /app/app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

# Health check inside the container — defense in depth alongside the ALB
# target-group health check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
