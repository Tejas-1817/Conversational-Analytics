-- =============================================================================
-- Migration 016: Enterprise-Based Multi-Tenancy & Granular Table Permissions
-- =============================================================================

-- 1. Ensure Default Enterprise exists for legacy single-tenant records
INSERT INTO tenants (id, name, slug, display_name, plan, is_active, created_by)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Default Enterprise',
    'default-enterprise',
    'Default Enterprise',
    'enterprise',
    true,
    'system'
) ON CONFLICT (id) DO NOTHING;

-- 2. Clean up or assign orphaned users and data sources to default enterprise
UPDATE users 
SET tenant_id = '00000000-0000-0000-0000-000000000001'::uuid 
WHERE tenant_id IS NULL OR tenant_id NOT IN (SELECT id FROM tenants);

UPDATE data_sources 
SET tenant_id = '00000000-0000-0000-0000-000000000001'::uuid 
WHERE tenant_id IS NULL OR tenant_id NOT IN (SELECT id FROM tenants);

-- 3. Create user_table_access junction table
CREATE TABLE IF NOT EXISTS user_table_access (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_id       uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    table_id        uuid NOT NULL REFERENCES tables_meta(id) ON DELETE CASCADE,
    granted_by      text NOT NULL,                      -- Admin email who granted access
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id, table_id)
);

CREATE INDEX IF NOT EXISTS idx_user_table_access_lookup 
    ON user_table_access(tenant_id, user_id, source_id);

CREATE INDEX IF NOT EXISTS idx_table_user_access_lookup 
    ON user_table_access(tenant_id, table_id);

-- 4. Add explicit user ownership to domains table
ALTER TABLE domains ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_domains_tenant_user ON domains(tenant_id, user_id);

-- 5. Backfill domain ownership safely
-- Match created_by email to existing user within the same tenant
UPDATE domains d
SET user_id = u.id
FROM users u
WHERE d.user_id IS NULL 
  AND d.created_by = u.email 
  AND d.tenant_id = u.tenant_id;

-- For any legacy domain where created_by was 'system' or user no longer exists:
-- Assign user_id to the primary admin of that tenant so it is governed safely.
UPDATE domains d
SET user_id = (
    SELECT u.id FROM users u 
    WHERE u.tenant_id = d.tenant_id AND u.role::text = 'ADMIN' 
    ORDER BY u.created_at ASC LIMIT 1
)
WHERE d.user_id IS NULL;

-- 6. Add 'USER' value to user_role enum if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumtypid = 'user_role'::regtype AND enumlabel = 'USER'
    ) THEN
        ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'USER';
    END IF;
END
$$;

-- 7. Migrate all legacy ANALYST and VIEWER users to USER
UPDATE users SET role = 'USER'::user_role WHERE role::text IN ('ANALYST', 'VIEWER');
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'USER'::user_role;
