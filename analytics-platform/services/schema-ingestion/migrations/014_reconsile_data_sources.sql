ALTER TABLE data_sources
    ADD COLUMN IF NOT EXISTS secret_ref TEXT,
    ADD COLUMN IF NOT EXISTS credential_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS ssl_mode TEXT NOT NULL DEFAULT 'verify-full',
    ADD COLUMN IF NOT EXISTS connection_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS schema_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS embedding_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS last_connection_error_code TEXT,
    ADD COLUMN IF NOT EXISTS last_connection_test_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS file_path TEXT,
    ADD COLUMN IF NOT EXISTS original_upload_path TEXT;

ALTER TABLE data_sources
    ALTER COLUMN database_name DROP NOT NULL,
    ALTER COLUMN username DROP NOT NULL,
    ALTER COLUMN credentials_encrypted DROP NOT NULL;

ALTER TABLE data_sources
    DROP CONSTRAINT IF EXISTS chk_data_sources_type_credentials;

ALTER TABLE data_sources
    ADD CONSTRAINT chk_data_sources_type_credentials
    CHECK (
        (
            type IN ('postgres', 'mysql', 'mssql')
            AND host IS NOT NULL
            AND database_name IS NOT NULL
            AND username IS NOT NULL
            AND (
                credentials_encrypted IS NOT NULL
                OR secret_ref IS NOT NULL
            )
        )
        OR (
            type = 'excel'
            AND original_upload_path IS NOT NULL
        )
        OR type IN ('snowflake', 'bigquery')
    );