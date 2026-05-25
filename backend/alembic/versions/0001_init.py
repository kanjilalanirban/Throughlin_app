"""0001 init: extensions + 4 primitives + supporting tables.

Mirrors the SQL in docs/data-model.md verbatim. Written as raw SQL so it
reads 1:1 with the doc — autogenerate-style migrations would obscure that.

Revision ID: 0001_init
Revises:
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Extensions
    # -----------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")  # pgvector

    # -----------------------------------------------------------------------
    # people (created first — initiatives.owner_id references it)
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE people (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           UUID NOT NULL,
            employee_id      TEXT,
            name             TEXT NOT NULL,
            email            TEXT NOT NULL,
            role             TEXT,
            manager_id       UUID REFERENCES people(id),
            team             TEXT,
            start_date       DATE,
            status           TEXT NOT NULL DEFAULT 'active',
            github_handle    TEXT,
            jira_account_id  TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE UNIQUE INDEX people_org_email_unique ON people(org_id, email);")
    op.execute(
        "CREATE INDEX people_github_idx ON people(github_handle) "
        "WHERE github_handle IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX people_jira_idx ON people(jira_account_id) "
        "WHERE jira_account_id IS NOT NULL;"
    )
    op.execute("CREATE INDEX people_org_id_idx ON people(org_id);")

    # -----------------------------------------------------------------------
    # initiatives
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE initiatives (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id               UUID NOT NULL,
            name                 TEXT NOT NULL,
            description          TEXT,
            status               TEXT NOT NULL,
            owner_id             UUID REFERENCES people(id),
            inferred_from        JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence_score     NUMERIC(3,2),
            confirmed_by_user_at TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX initiatives_org_idx ON initiatives(org_id);")
    op.execute("CREATE INDEX initiatives_status_idx ON initiatives(org_id, status);")

    # -----------------------------------------------------------------------
    # decisions
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE decisions (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            initiative_id        UUID NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
            title                TEXT NOT NULL,
            rationale            TEXT NOT NULL,
            decided_at           TIMESTAMPTZ NOT NULL,
            decided_by_person_id UUID REFERENCES people(id),
            still_valid          BOOLEAN,
            evidence_against     JSONB DEFAULT '[]'::jsonb,
            last_validated_at    TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX decisions_initiative_idx ON decisions(initiative_id);")

    # -----------------------------------------------------------------------
    # person_initiative
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE person_initiative (
            person_id                       UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            initiative_id                   UUID NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
            role_in_initiative              TEXT,
            ownership_strength              NUMERIC(3,2),
            knowledge_concentration_score   NUMERIC(3,2),
            last_computed_at                TIMESTAMPTZ,
            PRIMARY KEY (person_id, initiative_id)
        );
    """)

    # -----------------------------------------------------------------------
    # signals (with pgvector embedding column)
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE signals (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id                   UUID NOT NULL,
            source                   TEXT NOT NULL,
            source_entity_id         TEXT NOT NULL,
            signal_type              TEXT NOT NULL,
            payload                  JSONB NOT NULL,
            observed_at              TIMESTAMPTZ NOT NULL,
            links_to_initiative_id   UUID REFERENCES initiatives(id),
            embedding                vector(1536),
            created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX signals_org_observed_idx ON signals(org_id, observed_at DESC);")
    op.execute("CREATE INDEX signals_source_idx ON signals(source, source_entity_id);")
    op.execute(
        "CREATE INDEX signals_initiative_idx ON signals(links_to_initiative_id) "
        "WHERE links_to_initiative_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX signals_embedding_idx ON signals "
        "USING hnsw (embedding vector_cosine_ops);"
    )

    # -----------------------------------------------------------------------
    # ingestion_runs (operational)
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE ingestion_runs (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source              TEXT NOT NULL,
            started_at          TIMESTAMPTZ NOT NULL,
            completed_at        TIMESTAMPTZ,
            status              TEXT NOT NULL,
            records_processed   INT NOT NULL DEFAULT 0,
            errors              JSONB DEFAULT '[]'::jsonb
        );
    """)
    op.execute(
        "CREATE INDEX ingestion_runs_source_started_idx "
        "ON ingestion_runs(source, started_at DESC);"
    )

    # -----------------------------------------------------------------------
    # audit_log (security/compliance)
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE audit_log (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       UUID,
            action        TEXT NOT NULL,
            target_type   TEXT,
            target_id     UUID,
            payload       JSONB,
            occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX audit_log_user_occurred_idx ON audit_log(user_id, occurred_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_log;")
    op.execute("DROP TABLE IF EXISTS ingestion_runs;")
    op.execute("DROP TABLE IF EXISTS signals;")
    op.execute("DROP TABLE IF EXISTS person_initiative;")
    op.execute("DROP TABLE IF EXISTS decisions;")
    op.execute("DROP TABLE IF EXISTS initiatives;")
    op.execute("DROP TABLE IF EXISTS people;")
    # Extensions left in place — other databases on the cluster may use them.
