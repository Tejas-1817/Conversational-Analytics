-- =============================================================================
-- Phase 2: Metadata Catalog Additions
-- =============================================================================

CREATE TABLE metadata_versions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id      uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    version_number integer NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    sync_status    job_status NOT NULL DEFAULT 'queued',
    sync_duration  numeric,
    UNIQUE (source_id, version_number)
);
CREATE INDEX idx_metadata_versions_source ON metadata_versions (source_id, created_at DESC);

CREATE TABLE index_meta (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    table_id       uuid NOT NULL REFERENCES tables_meta(id) ON DELETE CASCADE,
    index_name     text NOT NULL,
    column_names   text[] NOT NULL,
    is_unique      boolean NOT NULL DEFAULT false,
    UNIQUE (table_id, index_name)
);
CREATE INDEX idx_index_meta_table ON index_meta (table_id);
