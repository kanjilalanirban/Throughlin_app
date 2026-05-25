"""Pytest fixtures.

Tests don't hit a real DB by default — those are gated on TEST_DATABASE_URL
being set (integration tests). Unit tests use the in-app dependency
overrides and don't need network.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest

# Ensure config loads with a sensible default before app import.
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://nope:nope@localhost/nope")

from app.main import app  # noqa: E402


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
