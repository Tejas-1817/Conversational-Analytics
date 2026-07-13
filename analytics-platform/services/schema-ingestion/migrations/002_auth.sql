-- =============================================================================
-- Migration: 002_auth.sql
-- Description: Adds users and authentication tables (RBAC)
-- =============================================================================

CREATE TYPE user_role AS ENUM ('ADMIN', 'ANALYST', 'VIEWER');

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL,
    email         text NOT NULL,
    password_hash text NOT NULL,
    role          user_role NOT NULL DEFAULT 'VIEWER',
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Blacklisted refresh tokens to prevent reuse after logout
CREATE TABLE revoked_tokens (
    token_id    text PRIMARY KEY,
    revoked_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL
);
