# Data Model

The four primitives are the spine of the product. Every feature, view, and report is a projection of these four. Read this when touching schema, models, or migrations.

## The Four Primitives

1. **Initiatives** — long-lived strategic bets and transformations. The unit of executive attention.
2. **Decisions** — choices made along the way, with rationale. Periodically re-evaluated.
3. **People** — who actually holds the knowledge. Where concentration risk sits.
4. **Signals** — continuous evidence from Jira, GitHub, HRIS. How the brain tells the truth.

Everything else (audit log, ingestion runs, person-initiative join) supports these four.

## Schema

```sql
-- =====================================================
-- initiatives
-- =====================================================
CREATE TABLE initiatives (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL,        -- proposed|active|on_hold|completed|cancelled
    owner_id        UUID REFERENCES people(id),
    inferred_from   JSONB NOT NULL DEFAULT '[]'::jsonb,  -- list of signal references
    confidence_score NUMERIC(3,2),         -- 0.00–1.00, populated when inferred
    confirmed_by_user_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX initiatives_org_idx ON initiatives(org_id);
CREATE INDEX initiatives_status_idx ON initiatives(org_id, status);

-- =====================================================
-- decisions
-- =====================================================
CREATE TABLE decisions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    initiative_id        UUID NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
    title                TEXT NOT NULL,
    rationale            TEXT NOT NULL,
    decided_at           TIMESTAMPTZ NOT NULL,
    decided_by_person_id UUID REFERENCES people(id),
    still_valid          BOOLEAN,                -- nullable until first recompute
    evidence_against     JSONB DEFAULT '[]'::jsonb,
    last_validated_at    TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX decisions_initiative_idx ON decisions(initiative_id);

-- =====================================================
-- people
-- =====================================================
CREATE TABLE people (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID NOT NULL,
    employee_id      TEXT,                       -- from HRIS
    name             TEXT NOT NULL,
    email            TEXT NOT NULL,
    role             TEXT,
    manager_id       UUID REFERENCES people(id),
    team             TEXT,
    start_date       DATE,
    status           TEXT NOT NULL DEFAULT 'active',  -- active|on_leave|departed
    github_handle    TEXT,
    jira_account_id  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX people_org_email_idx ON people(org_id, email);
CREATE INDEX people_github_idx ON people(github_handle) WHERE github_handle IS NOT NULL;
CREATE INDEX people_jira_idx ON people(jira_account_id) WHERE jira_account_id IS NOT NULL;

-- =====================================================
-- person_initiative (join table with computed fields)
-- =====================================================
CREATE TABLE person_initiative (
    person_id                       UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    initiative_id                   UUID NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
    role_in_initiative              TEXT,        -- owner|contributor|reviewer|stakeholder
    ownership_strength              NUMERIC(3,2),  -- 0.00–1.00, computed
    knowledge_concentration_score   NUMERIC(3,2),  -- 0.00–1.00, computed
    last_computed_at                TIMESTAMPTZ,
    PRIMARY KEY (person_id, initiative_id)
);

-- =====================================================
-- signals
-- =====================================================
CREATE TABLE signals (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                   UUID NOT NULL,
    source                   TEXT NOT NULL,      -- jira|github|hris
    source_entity_id         TEXT NOT NULL,      -- the ID in the source system
    signal_type              TEXT NOT NULL,      -- jira_issue|github_commit|hris_role_change|...
    payload                  JSONB NOT NULL,
    observed_at              TIMESTAMPTZ NOT NULL,
    links_to_initiative_id   UUID REFERENCES initiatives(id),
    embedding                vector(1536),       -- pgvector column
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX signals_org_observed_idx ON signals(org_id, observed_at DESC);
CREATE INDEX signals_source_idx ON signals(source, source_entity_id);
CREATE INDEX signals_initiative_idx ON signals(links_to_initiative_id)
    WHERE links_to_initiative_id IS NOT NULL;
CREATE INDEX signals_embedding_idx ON signals USING hnsw (embedding vector_cosine_ops);

-- =====================================================
-- ingestion_runs (operational)
-- =====================================================
CREATE TABLE ingestion_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ,
    status              TEXT NOT NULL,          -- running|success|failed|partial
    records_processed   INT NOT NULL DEFAULT 0,
    errors              JSONB DEFAULT '[]'::jsonb
);
CREATE INDEX ingestion_runs_source_started_idx
    ON ingestion_runs(source, started_at DESC);

-- =====================================================
-- audit_log (security/compliance)
-- =====================================================
CREATE TABLE audit_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID,
    action        TEXT NOT NULL,                -- read_initiative|generate_brief|ask_query|...
    target_type   TEXT,                          -- initiative|decision|person|signal|...
    target_id     UUID,
    payload       JSONB,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_user_occurred_idx ON audit_log(user_id, occurred_at DESC);
```

## Notes on Specific Columns

### `inferred_from` (jsonb on initiatives)

Holds the list of signal references that led the LLM to propose this initiative. Shape:
```json
[
  {"signal_id": "uuid", "source": "jira", "weight": 0.8, "reason": "epic name match"},
  {"signal_id": "uuid", "source": "github", "weight": 0.6, "reason": "repo activity spike"}
]
```
This is what makes the brain **transparent**. When the user asks "why does the system think this is an initiative?", the answer is in this column.

### `still_valid` (boolean on decisions)

Recomputed periodically by a scheduled Lambda job (`@docs/inference.md` covers the prompt). When new signals contradict the original rationale, `still_valid` flips to `false` and `evidence_against` is populated.

### `knowledge_concentration_score` (numeric on person_initiative)

Range 0.00–1.00. **Higher means more concentrated**, i.e., more risky.
Computed from:
- Share of commits to repos linked to the initiative
- Share of Jira issues assigned/resolved
- Whether this person is the named owner
- Whether anyone else has > 20% activity share

A score of 0.95 means "this person is essentially the sole holder of knowledge for this initiative." That's a flag. See `app/inference/scoring.py`.

### `embedding` (vector(1536) on signals)

We embed the relevant text from each signal (issue title + description, commit message, PR title, etc.). 1536 dims matches `text-embedding-3-small` from OpenAI by convention. **Phase 0 uses the embedding model defined in `app/core/config.py`; do not hardcode.** Use HNSW index for cosine similarity.

## Tenant Isolation

Phase 0 is single-tenant, but every "organizational" table (`initiatives`, `people`, `signals`) carries an `org_id` column from day one. The Phase 1 hardening checklist adds Postgres row-level security on `org_id`; for now, every query in the API layer must include `WHERE org_id = :current_org_id`. There is a SQLAlchemy mixin in `app/core/tenant.py` that enforces this on the ORM level — use it.

## Migrations

- **Tool:** Alembic
- **Location:** `backend/alembic/versions/`
- **Style:** autogenerate, then review and edit before committing. Autogenerated migrations are starting points, not finished products.
- **Rule:** migrations are append-only. Never edit a committed migration; add a new one to correct mistakes.

## Seed Data

Test data lives in `backend/seed/`. The `make seed` command (from repo root) loads:
- 1 fake organization
- 20–50 fake people
- 2–3 fake initiatives (with mixed inferred/confirmed status)
- Sample decisions, person_initiative rows, and signals to support the demo flow

Seed data is for development only and must never be loaded against a production environment. The `make seed` target refuses to run if `ENVIRONMENT != "phase0"`.
