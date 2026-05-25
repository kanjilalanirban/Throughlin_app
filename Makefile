.PHONY: help dev seed test lint typecheck migrate fmt

help:
	@echo "Targets:"
	@echo "  dev         Start backend (uvicorn) and frontend (vite) in foreground"
	@echo "  seed        Load Phase 0 test data (refuses to run if ENVIRONMENT != phase0|local)"
	@echo "  migrate     Apply Alembic migrations"
	@echo "  test        Run backend and frontend tests"
	@echo "  lint        Run ruff + eslint"
	@echo "  typecheck   Run mypy + tsc"
	@echo "  fmt         Format with ruff + prettier"

dev:
	@echo "Run 'cd backend && uv run uvicorn app.main:app --reload' and 'cd frontend && pnpm dev' in separate terminals."

seed:
	cd backend && uv run python -m seed.load

migrate:
	cd backend && uv run alembic upgrade head

test:
	cd backend && uv run pytest
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check .
	cd frontend && pnpm lint

typecheck:
	cd backend && uv run mypy app
	cd frontend && pnpm typecheck

fmt:
	cd backend && uv run ruff format .
	cd frontend && pnpm exec prettier --write .
