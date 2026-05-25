#!/bin/sh
set -e

# Run DB migrations on every container start. Alembic is idempotent — if the
# schema is already at head, this exits in ~1s without changes.
# Skip with RUN_MIGRATIONS_ON_STARTUP=false if you want manual control.
if [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" = "true" ]; then
  echo "==> alembic upgrade head"
  alembic upgrade head
fi

# Optional one-shot seed (Phase 0 only). Default: false. Set SEED_ON_STARTUP=true
# to populate fixtures before serving. The seed loader itself refuses to run
# unless ENVIRONMENT is local|phase0, so this is safe.
if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
  echo "==> seed data"
  python -m seed.load
fi

echo "==> exec: $*"
exec "$@"
