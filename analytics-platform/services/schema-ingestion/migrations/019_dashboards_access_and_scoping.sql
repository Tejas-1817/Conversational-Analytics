-- Migration 019: Dashboards v2 - Scoping, Ownership, Live Data, and Customization
-- Enhances saved_insights, dashboards, and dashboard_widgets with ownership, source scoping, and responsive layouts.

-- 1. saved_insights: add source scoping, lineage, and chart metadata; relax global name uniqueness
ALTER TABLE saved_insights
    ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES data_sources(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS domain_id UUID REFERENCES domains(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS message_id UUID REFERENCES conversation_messages(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS chart_type TEXT,
    ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP WITH TIME ZONE;

-- Drop global (tenant_id, name) uniqueness so different users can have insights with the same name
ALTER TABLE saved_insights DROP CONSTRAINT IF EXISTS saved_insights_tenant_id_name_key;

-- Indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_saved_insights_tenant_user ON saved_insights (tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_saved_insights_source ON saved_insights (source_id);

-- 2. dashboards: add visibility ('private' | 'published') and scope uniqueness to (tenant_id, user_id, name)
ALTER TABLE dashboards
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'published' CHECK (visibility IN ('private', 'published'));

-- Existing dashboards backfill to 'published' so current users keep access
UPDATE dashboards SET visibility = 'published' WHERE visibility IS NULL;

-- Replace global (tenant_id, name) uniqueness with per-owner uniqueness
ALTER TABLE dashboards DROP CONSTRAINT IF EXISTS dashboards_tenant_id_name_key;
ALTER TABLE dashboards ADD CONSTRAINT dashboards_tenant_user_name_key UNIQUE (tenant_id, user_id, name);

-- Index for tenant + user lookups
CREATE INDEX IF NOT EXISTS idx_dashboards_tenant_user ON dashboards (tenant_id, user_id);

-- 3. dashboard_widgets: add overrides, settings, and responsive multi-breakpoint layouts
ALTER TABLE dashboard_widgets
    ADD COLUMN IF NOT EXISTS title_override TEXT,
    ADD COLUMN IF NOT EXISTS chart_type_override TEXT,
    ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS layouts JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Backfill existing widgets with default 'lg' layout coordinates
UPDATE dashboard_widgets
SET layouts = jsonb_build_object('lg', jsonb_build_object('x', x, 'y', y, 'w', w, 'h', h))
WHERE layouts = '{}'::jsonb OR layouts IS NULL;

-- Indexes for widget relationships
CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_dashboard ON dashboard_widgets (dashboard_id);
CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_insight ON dashboard_widgets (insight_id);
