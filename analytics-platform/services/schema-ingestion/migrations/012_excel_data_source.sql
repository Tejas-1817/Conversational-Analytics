-- Migration 012: Add Excel data source support
ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'excel';

ALTER TABLE data_sources
    ADD COLUMN IF NOT EXISTS file_path TEXT,
    ADD COLUMN IF NOT EXISTS original_upload_path TEXT;

-- Make database credentials and database_name nullable for file-backed sources
ALTER TABLE data_sources
    ALTER COLUMN database_name DROP NOT NULL,
    ALTER COLUMN username DROP NOT NULL,
    ALTER COLUMN credentials_encrypted DROP NOT NULL;

-- Enforce credentials presence for live databases, allow NULL for excel
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_data_sources_type_credentials'
    ) THEN
        ALTER TABLE data_sources
            ADD CONSTRAINT chk_data_sources_type_credentials
            CHECK (
                (type IN ('postgres', 'mysql') AND username IS NOT NULL AND credentials_encrypted IS NOT NULL AND database_name IS NOT NULL)
                OR (type = 'excel' AND (original_upload_path IS NOT NULL OR file_path IS NOT NULL))
                OR (type NOT IN ('postgres', 'mysql', 'excel'))
            );
    END IF;
END $$;
