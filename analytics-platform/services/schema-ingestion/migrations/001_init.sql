-- =============================================================================
-- Schema Ingestion & Semantic Metadata Repository — initial DDL
-- Target: PostgreSQL 16+
-- This is "the blank notebook": every table the ingestion pipeline writes into.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ---- Enumerations -----------------------------------------------------------

CREATE TYPE approval_status AS ENUM ('draft', 'reviewed', 'approved', 'rejected', 'needs_clarification');
CREATE TYPE column_role     AS ENUM ('dimension', 'measure', 'key', 'attribute', 'unknown');
CREATE TYPE additivity_type AS ENUM ('additive', 'semi_additive', 'non_additive', 'not_applicable');
CREATE TYPE rel_source      AS ENUM ('declared_fk', 'naming', 'value_overlap', 'llm');
CREATE TYPE job_status      AS ENUM ('queued', 'running', 'succeeded', 'failed');
CREATE TYPE source_type     AS ENUM ('postgres', 'mysql', 'snowflake', 'bigquery');

-- ---- Registered customer databases -----------------------------------------

CREATE TABLE data_sources (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL,
    name                  text NOT NULL,
    type                  source_type NOT NULL,
    host                  text,
    port                  integer,
    database_name         text NOT NULL,
    username              text NOT NULL,
    credentials_encrypted bytea NOT NULL,          -- Fernet-encrypted secret; never stored in plain text
    options               jsonb NOT NULL DEFAULT '{}'::jsonb,  -- e.g. {"include_schemas": ["public"], "table_blocklist": []}
    status                text NOT NULL DEFAULT 'registered',
    last_ingested_at      timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    created_by            text NOT NULL,
    updated_by            text NOT NULL,
    UNIQUE (tenant_id, name)
);

-- ---- Tables discovered in customer databases --------------------------------

CREATE TABLE tables_meta (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    schema_name   text NOT NULL,
    table_name    text NOT NULL,
    business_name text,                             -- AI-drafted, human-approved
    description   text,                             -- AI-drafted, human-approved
    grain         text,                             -- what one row represents; critical for correct joins
    row_count     bigint,
    is_active     boolean NOT NULL DEFAULT true,    -- false when table disappears on a re-run (diff-aware)
    status        approval_status NOT NULL DEFAULT 'draft',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    updated_by    text NOT NULL DEFAULT 'system',
    UNIQUE (source_id, schema_name, table_name)
);
CREATE INDEX idx_tables_meta_source ON tables_meta (source_id);

-- ---- Columns ----------------------------------------------------------------

CREATE TABLE columns_meta (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    table_id         uuid NOT NULL REFERENCES tables_meta(id) ON DELETE CASCADE,
    column_name      text NOT NULL,
    ordinal_position integer,
    data_type        text NOT NULL,
    is_nullable      boolean NOT NULL DEFAULT true,
    is_primary_key   boolean NOT NULL DEFAULT false,
    business_name    text,
    description      text,
    synonyms         text[] NOT NULL DEFAULT '{}',  -- how business users phrase it: makes chat work later
    role             column_role NOT NULL DEFAULT 'unknown',
    aggregation      text,                          -- sum / avg / count / min / max (measures only)
    additivity       additivity_type NOT NULL DEFAULT 'not_applicable',
    profile          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- distinct_count, null_rate, min, max, sample_values (PII-masked)
    is_active        boolean NOT NULL DEFAULT true,
    status           approval_status NOT NULL DEFAULT 'draft',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by       text NOT NULL DEFAULT 'system',
    UNIQUE (table_id, column_name)
);
CREATE INDEX idx_columns_meta_table ON columns_meta (table_id);

-- ---- Relationship candidates and approved joins ------------------------------

CREATE TABLE relationships (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_column_id uuid NOT NULL REFERENCES columns_meta(id) ON DELETE CASCADE,
    to_column_id   uuid NOT NULL REFERENCES columns_meta(id) ON DELETE CASCADE,
    cardinality    text NOT NULL DEFAULT 'many_to_one',   -- one_to_one / many_to_one / many_to_many
    source         rel_source NOT NULL,
    confidence     numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence       jsonb NOT NULL DEFAULT '{}'::jsonb,    -- why the detector believes this (rule hit, overlap ratio, ...)
    status         approval_status NOT NULL DEFAULT 'draft',
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    updated_by     text NOT NULL DEFAULT 'system',
    UNIQUE (from_column_id, to_column_id),
    CHECK (from_column_id <> to_column_id)
);
CREATE INDEX idx_relationships_from ON relationships (from_column_id);
CREATE INDEX idx_relationships_to   ON relationships (to_column_id);

-- ---- Business metrics (populated mostly in the semantic-layer phase) ---------

CREATE TABLE metrics (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    name          text NOT NULL,
    business_name text,
    expression    text NOT NULL,                    -- e.g. SUM(net_amt) WHERE order_status != 'cancelled'
    description   text,
    owner         text,                             -- named business owner of the definition
    synonyms      text[] NOT NULL DEFAULT '{}',
    status        approval_status NOT NULL DEFAULT 'draft',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    updated_by    text NOT NULL DEFAULT 'system',
    UNIQUE (source_id, name)
);

-- ---- Pipeline runs ------------------------------------------------------------

CREATE TABLE ingestion_jobs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    stage       text NOT NULL DEFAULT 'pipeline',   -- pipeline | introspect | profile | relationships | classify
    status      job_status NOT NULL DEFAULT 'queued',
    started_at  timestamptz,
    finished_at timestamptz,
    stats       jsonb NOT NULL DEFAULT '{}'::jsonb, -- tables_seen, columns_seen, new, dropped, candidates_found ...
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_ingestion_jobs_source ON ingestion_jobs (source_id, created_at DESC);

-- ---- Immutable audit trail -----------------------------------------------------

CREATE TABLE audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id   uuid,
    entity_type text NOT NULL,      -- tables_meta | columns_meta | relationships | metrics | data_sources
    entity_id   uuid NOT NULL,
    action      text NOT NULL,      -- created | updated | approved | rejected | needs_clarification
    actor       text NOT NULL,
    before      jsonb,
    after       jsonb,
    at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_log (entity_type, entity_id);

-- ---- updated_at trigger ---------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['data_sources','tables_meta','columns_meta','relationships','metrics']
    LOOP
        EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END $$;
