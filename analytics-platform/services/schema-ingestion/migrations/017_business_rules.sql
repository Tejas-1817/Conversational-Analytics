-- =============================================================================
-- Migration 017: Create business_rules table for Institutional Knowledge
-- =============================================================================

CREATE TABLE IF NOT EXISTS business_rules (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    source_id           uuid REFERENCES data_sources(id) ON DELETE CASCADE,
    category            varchar(50) NOT NULL DEFAULT 'filter_exclusion',
    rule_title          text NOT NULL,
    rule_instruction    text NOT NULL,
    keywords            text,
    applies_to_tables   jsonb DEFAULT '[]'::jsonb,
    is_active           boolean NOT NULL DEFAULT true,
    version             integer NOT NULL DEFAULT 1,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_business_rules_tenant ON business_rules (tenant_id);
CREATE INDEX IF NOT EXISTS idx_business_rules_source ON business_rules (source_id);
CREATE INDEX IF NOT EXISTS idx_business_rules_active ON business_rules (tenant_id, is_active);

