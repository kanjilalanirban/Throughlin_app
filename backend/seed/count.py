"""Tiny utility: print row counts for the seed tables. Useful in CI smoke tests."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.db import session_factory


async def main() -> None:
    f = session_factory()
    async with f() as s:
        for t in ("people", "initiatives", "decisions", "signals", "person_initiative"):
            r = await s.execute(text(f"SELECT count(*) FROM {t}"))
            print(f"{t}: {r.scalar_one()}")


if __name__ == "__main__":
    asyncio.run(main())
