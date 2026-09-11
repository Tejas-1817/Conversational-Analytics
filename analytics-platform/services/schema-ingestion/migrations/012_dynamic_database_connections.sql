ALTER TYPE source_type
    ADD VALUE IF NOT EXISTS 'mssql';

ALTER TABLE data_sources
    ADD COLUMN IF NOT EXISTS secret_ref text,
    ADD COLUMN IF NOT EXISTS credential_version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS ssl_mode text NOT NULL DEFAULT 'verify-full',
    ADD COLUMN IF NOT EXISTS connection_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS schema_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS embedding_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS last_connection_error_code text,
    ADD COLUMN IF NOT EXISTS last_connection_test_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_data_sources_tenant_id
    ON data_sources (tenant_id, id);

CREATE INDEX IF NOT EXISTS idx_data_sources_tenant_status
    ON data_sources (tenant_id, connection_status);