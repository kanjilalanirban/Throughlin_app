"""Smoke test: /health returns 200 with the expected shape.

Does not touch the database — only verifies routing + lifespan startup.
"""

from __future__ import annotations

import httpx


async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body
    # Correlation id is echoed back by middleware
    assert resp.headers.get("X-Correlation-Id")
