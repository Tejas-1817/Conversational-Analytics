-- =============================================================================
-- Phase 6 — Enterprise Multi-Tenancy & Production Security
-- Migration 005: Tenant model, RLS, Column Security, API Keys, OIDC, Audit ext.
-- Target: PostgreSQL 16+
-- This migration is ADDITIVE ONLY. No existing data is modified.
-- =============================================================================

-- ---- 1. Tenant / Organization table -----------------------------------------

CREATE TABLE IF NOT EXISTS tenants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL UNIQUE,
    slug            text NOT NULL UNIQUE,          -- URL-safe identifier
    display_name    text,
    plan            text NOT NULL DEFAULT 'starter', -- starter | pro | enterprise
    is_active       boolean NOT NULL DEFAULT true,
    max_users       integer NOT NULL DEFAULT 10,
    max_sources     integer NOT NULL DEFAULT 5,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    created_by      text NOT NULL DEFAULT 'system'
);

-- Seed the default dev tenant so existing data keeps working
INSERT INTO tenants (id, name, slug, display_name, plan, created_by)
VALUES ('00000000-0000-0000-0000-000000000001', 'Default Organization', 'default', 'Default Org', 'enterprise', 'system')
ON CONFLICT (id) DO NOTHING;

CREATE TRIGGER trg_tenants_updated
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---- 2. OIDC / SSO Provider configuration -----------------------------------

CREATE TABLE IF NOT EXISTS oidc_providers (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider_name   text NOT NULL,                  -- azure | google | okta | auth0
    client_id       text NOT NULL,
    client_secret_encrypted bytea NOT NULL,
    issuer_url      text NOT NULL,
    scopes          text[] NOT NULL DEFAULT '{openid,email,profile}',
    claim_mapping   jsonb NOT NULL DEFAULT '{}'::jsonb, -- maps IdP claims to our user fields
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, provider_name)
);

-- ---- 3. API Keys (service accounts) -----------------------------------------

CREATE TABLE IF NOT EXISTS api_keys (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            text NOT NULL,
    key_hash        text NOT NULL UNIQUE,           -- bcrypt hash of the raw key
    key_prefix      text NOT NULL,                  -- first 8 chars shown in UI
    scopes          text[] NOT NULL DEFAULT '{}',   -- e.g. {read:data, write:insights}
    last_used_at    timestamptz,
    expires_at      timestamptz,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);
CREATE INDEX idx_api_keys_tenant ON api_keys (tenant_id);
CREATE INDEX idx_api_keys_hash   ON api_keys (key_hash);

-- ---- 4. Row-Level Security Policies -----------------------------------------

CREATE TABLE IF NOT EXISTS rls_policies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            text NOT NULL,
    description     text,
    -- Which table/source this policy applies to
    source_id       uuid REFERENCES data_sources(id) ON DELETE CASCADE,
    table_name      text,                           -- NULL = all tables in source
    -- Policy definition: adds a WHERE clause to every query
    filter_column   text NOT NULL,                  -- e.g. "region"
    filter_operator text NOT NULL DEFAULT '=',      -- =, IN, !=
    -- Resolved at runtime from the user's JWT claims or profile
    filter_claim    text NOT NULL,                  -- e.g. "region", "department", "business_unit"
    applies_to_roles text[] NOT NULL DEFAULT '{ANALYST,VIEWER}',
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    created_by      text NOT NULL
);
CREATE INDEX idx_rls_policies_tenant ON rls_policies (tenant_id, is_active);

-- ---- 5. Column-Level Security Policies --------------------------------------

CREATE TYPE col_security_action AS ENUM ('deny', 'mask', 'hash', 'partial_mask');

CREATE TABLE IF NOT EXISTS column_security_policies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            text NOT NULL,
    description     text,
    source_id       uuid REFERENCES data_sources(id) ON DELETE CASCADE,
    table_name      text NOT NULL,
    column_name     text NOT NULL,
    action          col_security_action NOT NULL,
    mask_char       text DEFAULT '*',               -- for partial_mask
    visible_chars   integer DEFAULT 4,              -- show last N for partial_mask
    applies_to_roles text[] NOT NULL DEFAULT '{VIEWER}',
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    created_by      text NOT NULL
);
CREATE INDEX idx_col_security_tenant ON column_security_policies (tenant_id, is_active);

-- ---- 6. Tenant Policies (global settings) -----------------------------------

CREATE TABLE IF NOT EXISTS tenant_policies (
    tenant_id           uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    -- Rate limits (override platform defaults)
    rate_chat_per_min   integer NOT NULL DEFAULT 100,
    rate_login_per_min  integer NOT NULL DEFAULT 10,
    rate_export_per_min integer NOT NULL DEFAULT 20,
    -- Data governance
    max_query_rows      integer NOT NULL DEFAULT 50000,
    query_timeout_ms    integer NOT NULL DEFAULT 30000,
    allow_raw_sql       boolean NOT NULL DEFAULT false,
    require_mfa         boolean NOT NULL DEFAULT false,
    session_timeout_min integer NOT NULL DEFAULT 480,
    allowed_export_formats text[] NOT NULL DEFAULT '{csv,xlsx}',
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Seed default tenant policy
INSERT INTO tenant_policies (tenant_id) 
VALUES ('00000000-0000-0000-0000-000000000001')
ON CONFLICT (tenant_id) DO NOTHING;

-- ---- 7. Extend audit_log with security fields --------------------------------

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS ip_address  text,
    ADD COLUMN IF NOT EXISTS user_agent  text,
    ADD COLUMN IF NOT EXISTS request_id  text,
    ADD COLUMN IF NOT EXISTS event_type  text;      -- LOGIN | LOGOUT | QUERY | EXPORT | etc.

CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_log (tenant_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_type  ON audit_log (event_type, at DESC);

-- ---- 8. Missing indexes on existing tables ----------------------------------

CREATE INDEX IF NOT EXISTS idx_data_sources_tenant     ON data_sources (tenant_id);
CREATE INDEX IF NOT EXISTS idx_dashboards_tenant        ON dashboards (tenant_id);
CREATE INDEX IF NOT EXISTS idx_saved_insights_tenant    ON saved_insights (tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_tenant     ON conversations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_semantic_metrics_tenant  ON semantic_metrics (tenant_id);
CREATE INDEX IF NOT EXISTS idx_semantic_dims_tenant     ON semantic_dimensions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant             ON users (tenant_id);

-- ---- 9. Add foreign key: users -> tenants -----------------------------------
-- Only add if the tenants table is fresh (skip if FK already exists in pg_constraint)

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_tenant_id_fkey' AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_tenant_id_fkey
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- ---- 10. Updated_at triggers for new tables ---------------------------------

CREATE TRIGGER trg_oidc_providers_updated
    BEFORE UPDATE ON oidc_providers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_rls_policies_updated
    BEFORE UPDATE ON rls_policies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
