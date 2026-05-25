# Throughlin App — Company Brain Phase 0

> **Strategic intelligence platform for tech executives (CTOs, CIOs, VPs of Technology).**
> This is the application repo: FastAPI backend, React frontend, and Lambda ingesters.
> Infrastructure (Terraform / AWS) lives in the sibling repo `kanjilalanirban/Throughlin_TFE`.

---

## OPERATING MODEL — READ FIRST

**Phase 0 runs on a pure-ephemeral AWS stack. The stack is brought up before working and torn down immediately after. Nothing in AWS persists across sessions.**

```
# In Throughlin_TFE:
make up          # provisions stack, ~10-15 min

# In Throughlin_app:
make migrate     # apply Alembic migrations to the fresh DB
make seed        # load Phase 0 test data
... work ...

# In Throughlin_TFE:
make down        # destroy stack, ~5-10 min. Everything ephemeral is gone.
```

**Rules that follow from this:**

- **Assume the database is empty on every `make up`.** Don't write app code or migrations that depend on prior state being present.
- **Seed data IS the data in Phase 0.** Demos, evals, manual testing — all run against seeded state. There is no "production data" to preserve.
- **The audit log resets each session.** Phase 0 has no compliance audience for it, so this is acceptable. Phase 1 moves audit log to a long-lived store; don't pre-build for that here.
- **Long-running jobs die on teardown.** Keep ingestion batches and eval runs short. If something needs hours, run it locally.
- **No domain, no CloudFront, no TLS on the API path.** Frontend served from S3 bucket URL or local Vite; backend reached at raw ALB DNS. Acceptable because team-only and no real PII.
- **App is deployed by pushing the container to ECR (always-on).** The running stack pulls `latest` when `make up` runs. There is no auto-deploy-on-push-to-main in Phase 0.
- **Local development is the default.** Run against `docker compose up postgres` and a local backend; only bring AWS up when you need the full stack (testing Cognito, Lambdas, full integrations).

See [docs/decisions/0002-ephemeral-aws-stack.md](docs/decisions/0002-ephemeral-aws-stack.md) for the decision rationale, and the [Throughlin_TFE](https://github.com/kanjilalanirban/Throughlin_TFE) repo for the lifecycle mechanics.

---

## Quick Orientation

- **You are working on:** an early-stage product, pre-revenue, bootstrap-funded.
- **Users in this phase:** the founding team only. No external users yet.
- **Your job:** build the end-to-end slice of the four primitives (Initiatives, Decisions, People, Signals) on real data from Jira, GitHub, and CSV-based HRIS, with a working Ask/See/Brief interface.
- **What ships:** an internal alpha that we can demo end-to-end. **Not** a partner-ready production system — that's Phase 1.

If something feels over-engineered for this phase, it probably is. **Bias toward shipping the simplest thing that works correctly.**

---

## Repo Boundary

**In this repo:**
- FastAPI backend (`backend/`)
- React frontend (`frontend/`)
- Lambda handlers / ingesters (`ingesters/`)
- Shared product, architecture, security, and ADR docs (`docs/`)
- App CI: lint, typecheck, test, container build, deploy

**Not in this repo:**
- Terraform code, AWS resource definitions, infra CI
- Bootstrap or account-layout docs (those live in [Throughlin_TFE](https://github.com/kanjilalanirban/Throughlin_TFE))

### Cross-repo seam (read this once)
- Infra provisions AWS resources and publishes outputs (RDS endpoint, ALB DNS, Cognito pool ID, ECR repo URI, secret ARNs) to **SSM Parameter Store** under `/companybrain/phase0/...`.
- App deploy workflows read those SSM parameters by name.
- The running app reads **secret values** from AWS Secrets Manager at startup (the secret container is created by Terraform; the value is populated out-of-band so it never lives in state).
- The app **never runs Terraform**. Infra **never deploys app artifacts**.

If you find yourself wanting to break this seam, stop and bring it up first.

---

## Tech Stack

| Layer        | Choice                                                                |
|--------------|-----------------------------------------------------------------------|
| Backend      | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2        |
| Database     | PostgreSQL 16 with `pgvector` extension                               |
| Frontend     | React 18 + Vite + TypeScript + Tailwind CSS + TanStack Query          |
| LLM          | Anthropic Claude (via official `anthropic` Python SDK)                |
| Auth         | AWS Cognito (validated via JWT; no SSO in Phase 0)                    |
| Observability| OpenTelemetry SDK → ADOT → CloudWatch + X-Ray                         |

---

## Essential Commands

```bash
# Backend (from backend/)
uv sync                          # Install Python deps
uv run uvicorn app.main:app --reload   # Local dev server on :8000
uv run pytest                    # Run tests
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy app                  # Type-check
uv run alembic upgrade head      # Apply DB migrations
uv run alembic revision --autogenerate -m "msg"  # Create migration

# Frontend (from frontend/)
pnpm install
pnpm dev                         # Vite dev server on :5173
pnpm test                        # Vitest
pnpm lint                        # ESLint
pnpm typecheck                   # tsc --noEmit
pnpm build                       # Production build

# Local development stack (from repo root)
docker compose up -d postgres    # Postgres with pgvector
make seed                        # Load test data
```

---

## Folder Structure

```
Throughlin_app/
├── backend/                    # FastAPI app
│   ├── app/
│   │   ├── api/                # HTTP routes (organized by surface: ask/, see/, brief/, admin/)
│   │   ├── core/               # Config, auth, db session, OTel setup, audit, tenant
│   │   ├── domain/             # The four primitives as SQLAlchemy models
│   │   ├── inference/          # Claude prompts, retrieval, scoring (see docs/inference.md)
│   │   ├── integrations/       # jira/, github/, hris/ adapters (see docs/integrations.md)
│   │   └── main.py
│   ├── alembic/                # DB migrations
│   ├── seed/                   # Test data loaders
│   └── tests/
├── ingesters/                  # Lambda handler entry points (thin; import from backend/app/integrations)
│   ├── jira/
│   ├── github/
│   ├── hris/
│   └── normalizer/
├── frontend/                   # React app
│   └── src/
│       ├── features/           # Feature-first: ask/, see/, brief/, admin/
│       ├── components/         # Shared UI components
│       ├── lib/                # api client, hooks, utils
│       └── App.tsx
├── docs/
│   ├── architecture.md         # System architecture, AWS services
│   ├── data-model.md           # The four primitives, schema details
│   ├── inference.md            # Prompt design, retrieval, scoring
│   ├── integrations.md         # Jira, GitHub, HRIS adapter patterns
│   ├── security.md             # Phase 0 security posture
│   ├── runbook.md              # Deploy/rollback/debug procedures
│   └── decisions/              # ADRs (product + app)
├── docker-compose.yml          # Local Postgres + pgvector
├── Makefile                    # seed, dev, test convenience targets
└── .github/workflows/
    ├── pr.yml                  # Lint + test on every PR
    ├── backend-deploy.yml      # Build container, push to ECR, deploy on main
    └── frontend-deploy.yml     # Build, upload to S3, invalidate CloudFront on main
```

---

## Project Conventions (only the non-obvious ones)

### Backend
- **Use `async def` for I/O-bound code.** All HTTP, DB, and Claude calls are async.
- **Pydantic v2 syntax.** No deprecated `Config` class; use `model_config = ConfigDict(...)`.
- **SQLAlchemy 2.0 syntax.** Use `Mapped[]` annotations and `mapped_column()`, not the legacy `Column()` style.
- **Every table has an `org_id` column.** Phase 0 is single-tenant, but instrumenting `org_id` now means Phase 1 multi-tenancy is a config change, not a migration.
- **Never store secrets in code or env vars.** All secrets come from AWS Secrets Manager, fetched at app startup. Locally, use `.env` (gitignored).
- **All Claude API calls go through `app/inference/llm_client.py`.** This is the abstraction layer — no direct `anthropic.Anthropic()` calls anywhere else. The wrapper handles OTel spans, retry, token accounting.
- **Audit log every read and write of organizational data.** Use the `audit_logged` decorator from `app/core/audit.py`. This is non-negotiable.

### Frontend
- **Tailwind utility classes only.** No CSS files, no styled-components, no CSS modules.
- **TanStack Query for all server state.** Don't reach for Redux/Zustand/Context for server data.
- **No `any` types.** Type errors block merge. If a third-party lib is poorly typed, write a `.d.ts` shim.
- **Feature folders, not type folders.** `features/ask/` contains the Ask page, its hooks, its components. Don't scatter ask-specific code across `components/`, `hooks/`, `pages/`.

### Database
- **Migrations are append-only.** Never edit a committed migration. Add a new one.
- **`pgvector` for embeddings.** Same database as relational data. Don't introduce a separate vector store.
- **Use `jsonb` for `inferred_from`, `payload`, `errors`, and `evidence_against` columns.** These are intentionally schemaless because the shape varies by source.

### Ingesters
- **Lambda handlers in `ingesters/` are thin.** They import the adapter from `backend/app/integrations/{source}/` and run the standard ingestion loop. No business logic in the handler.
- **Bundling for deploy:** the deploy workflow zips `backend/app/integrations/{source}/` together with `ingesters/{source}/handler.py` and shared deps.

### Git Workflow
- **Trunk-based, short-lived branches.** Feature branches off `main`, merged via PR within 1–3 days.
- **Conventional commits encouraged but not enforced.** (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`).
- **Squash-merge to main.** Keeps history readable.
- **Branch protection on `main`:** PR review required, CI must pass.

### Documentation
- **Architecture Decision Records (ADRs) for every meaningful technical choice.** One page each, in `docs/decisions/NNNN-short-title.md`. Format: Context, Decision, Consequences.
- **Update `docs/runbook.md` whenever you change deploy/rollback/debug flow.** Even infra runbook entries live here (with the team that reads them daily).

---

## What's Explicitly Out of Scope for Phase 0

Don't build these unless asked, even if they seem obvious:
- SSO/SAML, multi-tenancy enforcement, mobile app
- Real-time push updates (polling/refresh is fine)
- A second LLM provider (one provider, abstracted)
- Webhooks (polling-only in Phase 0; webhooks are Phase 1)
- Billing system, marketing site, onboarding flow

These are all in Phase 1+.

---

## How to Work With This Codebase

When given a task, follow this loop:

1. **Read the relevant doc first.** Touching the data model? Read `docs/data-model.md`. Touching Claude? Read `docs/inference.md`. Don't infer from filenames alone.
2. **Plan before you code.** For any non-trivial task, outline the changes in plain English first. Confirm with the user before writing code if you're touching more than one module.
3. **Match existing patterns.** Look at neighboring files. If `app/api/see/` exists and you're adding `app/api/brief/`, mirror its structure. Don't invent new patterns mid-codebase.
4. **Write the test alongside the code.** Backend: `pytest`. Frontend: `vitest`. Not after, alongside.
5. **Type-check and lint before finishing.** Run the typecheck and lint commands. No red on merge.
6. **For any LLM prompt change, run the eval harness.** See `docs/inference.md`.
7. **Don't add dependencies casually.** New backend deps go through `uv add`; new frontend deps through `pnpm add`. Each new dep should be justifiable.

---

## Reference Documents (Progressive Disclosure)

Read these on demand, not upfront:

| Document | Read when... |
|----------|--------------|
| `docs/architecture.md`     | Working on AWS services, deployment, infra topology |
| `docs/data-model.md`       | Touching the four primitives, schema, migrations |
| `docs/inference.md`        | Working on prompts, retrieval, scoring, evals |
| `docs/integrations.md`     | Building or modifying Jira/GitHub/HRIS adapters |
| `docs/security.md`         | Anything touching auth, secrets, audit logs, tenant isolation |
| `docs/decisions/`          | Understanding *why* a choice was made |

For Terraform conventions, AWS account layout, and infra CI/CD, see the [Throughlin_TFE](https://github.com/kanjilalanirban/Throughlin_TFE) repo.

---

## Communication With the Human

- **Be concise.** Match the user's tone. Don't pad responses with reassurance.
- **Push back when something is wrong.** If asked to do something inconsistent with the conventions above, say so before doing it. Don't silently comply with a bad request.
- **When uncertain about Phase 0 scope, ask.** Better to ask once than build the wrong thing.
- **No emojis in code, commits, or docs.** Plain text only.
