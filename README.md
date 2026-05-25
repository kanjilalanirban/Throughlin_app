# Throughlin App

Application code (backend + frontend + ingesters) for **Company Brain** (Phase 0).

Infrastructure (Terraform / AWS) lives in the sibling repo: [Throughlin_TFE](https://github.com/kanjilalanirban/Throughlin_TFE).

## Quick start

```bash
# One-time per machine
brew install uv pnpm docker
brew install --cask docker         # if Docker Desktop is not installed

# Bring up local Postgres + pgvector
docker compose up -d postgres

# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000

# Frontend (new terminal)
cd frontend
pnpm install
pnpm dev                               # http://localhost:5173

# Seed test data
make seed
```

## Conventions, scope, cross-repo seam

See [CLAUDE.md](CLAUDE.md) and the deep-dive docs in [docs/](docs/):

- [architecture.md](docs/architecture.md) — system topology and request flows
- [data-model.md](docs/data-model.md) — the four primitives
- [inference.md](docs/inference.md) — prompts, retrieval, scoring
- [integrations.md](docs/integrations.md) — Jira, GitHub, HRIS adapters
- [security.md](docs/security.md) — Phase 0 posture, hardening checklist
- [decisions/](docs/decisions/) — ADRs (product + app)
