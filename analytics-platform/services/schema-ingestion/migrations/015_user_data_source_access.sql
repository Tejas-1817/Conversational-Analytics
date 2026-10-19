-- =============================================================================
-- Migration 015: User-Level Data Source Access Control
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_data_source_access (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_id       uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    granted_by      text NOT NULL,                      -- Admin email who granted access
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id, source_id)
);

-- Performance indices for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_data_source_access_lookup 
    ON user_data_source_access(tenant_id, user_id);

CREATE INDEX IF NOT EXISTS idx_source_user_access_lookup 
    ON user_data_source_access(tenant_id, source_id);
