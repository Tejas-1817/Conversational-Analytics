CREATE TABLE IF NOT EXISTS rag_chunks (
    id TEXT PRIMARY KEY,
    tenant_id UUID NOT NULL,
    source_id UUID,
    domain_id UUID,
    parent_id TEXT,
    object_type TEXT NOT NULL,
    document_id UUID,
    table_id UUID,
    section_path TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL DEFAULT '',
    acl_tags TEXT[] NOT NULL DEFAULT '{}',
    body TEXT NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(body, ''))) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_tenant ON rag_chunks (tenant_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_scope ON rag_chunks (tenant_id, source_id, domain_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_tsv ON rag_chunks USING GIN (tsv);