# Throughlin App

Application code (backend + frontend + ingesters) for **Company Brain** (Phase 0).

Infrastructure: [Throughlin_TFE](https://github.com/kanjilalanirban/Throughlin_TFE).

## Status (May 2026)

| Surface | State | Notes |
|---|---|---|
| **Foundation** | ✓ live | DB models, Alembic migrations (`0001_init`), Cognito JWT verification, audit decorator, tenant scoping, OTel auto-instrumentation, errors with correlation IDs |
| **Backend API** | ✓ live | `/api/see/*` (dashboard, initiatives, people, decisions, signals + detail), `/api/admin/integrations`, `/api/admin/integrations/hris/upload`, `/api/ask` (placeholder), `/api/brief` (placeholder) |
| **Frontend** | ✓ live | React 18 + Vite + TS + Tailwind + TanStack Query; routing with react-router-dom; Cognito SRP login via amazon-cognito-identity-js; 8 pages (Dashboard, Initiatives, Initiative detail, People, Decisions, Signals, Ask, Brief, Admin) |
| **CD** | ✓ live | `backend-image.yml` (build → push to ECR → force ECS redeploy on every push to `backend/**`); `frontend-deploy.yml` (build with VITE_* from SSM → S3 sync) |
| **Seed data** | ✓ live | 10 people across 3 teams, 3 initiatives, 2 decisions, 5 signals — see [`seed/load.py`](backend/seed/load.py) |
| **Auth enforcement** | ⏳ deferred | Endpoints currently use `optional_user` (anonymous reads allowed). Switch to `require_user` once team workflow is comfortable with login. |
| **Real LLM in Ask/Brief** | ⏳ next | Currently placeholder (ILIKE on initiative name/description + synthesized markdown). Real LLM client + retrieval lands next. |
| **Real Jira/GitHub ingestion** | ⏳ next | Lambda code, OAuth callback, GitHub App install flow not yet implemented. |
| **HRIS CSV** | ✓ direct path | `POST /api/admin/integrations/hris/upload` upserts to `people` directly. The Lambda-via-S3-trigger path is wired in TFE but `ingesters/hris/handler.py` is empty. |
| **Embedding pipeline** | ⏳ next | `signals.embedding` column exists; HNSW index ready. Population pending. |
| **Eval harness** | ⏳ next | `app/inference/evals/` is empty. |

## Quick start (local dev)

```bash
# One-time per machine
brew install uv pnpm
brew install --cask docker

# Bring up local Postgres + pgvector
docker compose up -d postgres

# Backend
cd backend
uv sync
DATABASE_URL="postgresql+asyncpg://companybrain:companybrain@localhost:5432/companybrain" \
  ENVIRONMENT=local \
  uv run alembic upgrade head
DATABASE_URL="postgresql+asyncpg://companybrain:companybrain@localhost:5432/companybrain" \
  ENVIRONMENT=local \
  uv run python -m seed.load
DATABASE_URL="postgresql+asyncpg://companybrain:companybrain@localhost:5432/companybrain" \
  ENVIRONMENT=local \
  uv run uvicorn app.main:app --reload   # http://localhost:8000

# Frontend (new terminal)
cd frontend
VITE_API_URL=http://localhost:8000 pnpm dev   # http://localhost:5173
```

## Live URLs

When the ephemeral stack is up, the current URLs are published to SSM:

```bash
aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/s3/frontend_url --query Parameter.Value --output text
aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/alb/url --query Parameter.Value --output text
```

Both URLs change on every `make up` (S3 bucket name has a random suffix; ALB DNS rotates with the load balancer).

## Lifecycle (tear-down + spin-up)

The canonical procedure is in [`docs/runbook.md`](docs/runbook.md). Short version:

- **Stop the per-hour cost:** trigger [`Destroy (manual — make down)`](https://github.com/kanjilalanirban/Throughlin_TFE/actions/workflows/destroy.yml) in the TFE repo.
- **Bring it back later:** trigger [`Apply (manual — make up)`](https://github.com/kanjilalanirban/Throughlin_TFE/actions/workflows/apply.yml) in the TFE repo, then [`Frontend deploy`](https://github.com/kanjilalanirban/Throughlin_app/actions/workflows/frontend-deploy.yml) here, then re-seed (one-shot RunTask).

## What's next

Loosely ordered by dependency / value:

1. **Real LLM client + retrieval** — wire `app/inference/llm_client.py` (Anthropic SDK with OTel spans + retry); add the embedding pipeline so `signals.embedding` is populated; swap the Ask/Brief placeholders to call it.
2. **Auth enforcement** — switch routes from `optional_user` to `require_user`; add a frontend route guard that redirects to `/login` when no session.
3. **Ingester Lambdas** — actual handler code for Jira (OAuth refresh + REST v3 paginated fetch + write to S3 raw), GitHub (App auth + GraphQL), HRIS via S3 trigger; build + push their images via a workflow.
4. **Inference pipelines** — initiative inference (cluster → propose), decision validity (weekly re-check), ownership + concentration scoring.
5. **Eval harness** — 10-20 golden cases in `app/inference/evals/cases/`; LLM-as-judge for fuzzy criteria; gated in PR workflow for prompt changes.
6. **Admin connector setup UI** — Jira OAuth callback handler + GitHub App install flow (currently just status cards).
7. **Persistent audit log** — Phase 1: move out of ephemeral RDS to DynamoDB or S3+Athena.

## Conventions, deep dives

See [CLAUDE.md](CLAUDE.md) and the deep-dive docs in [docs/](docs/):

- [architecture.md](docs/architecture.md) — system topology and request flows
- [data-model.md](docs/data-model.md) — the four primitives
- [inference.md](docs/inference.md) — prompts, retrieval, scoring (target spec)
- [integrations.md](docs/integrations.md) — Jira, GitHub, HRIS adapters (target spec)
- [security.md](docs/security.md) — Phase 0 posture, hardening checklist
- [runbook.md](docs/runbook.md) — **operational procedures (tear-down, spin-up, re-seed, secret rotation)**
- [decisions/](docs/decisions/) — ADRs (product + app)
