-- 020_dashboards_phase2_tabs_and_widgets.sql
-- Dashboards Phase 2: Tabs, text widgets, overview summary, and nullable insight_id

-- 1. Create dashboard_tabs table
CREATE TABLE IF NOT EXISTS dashboard_tabs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id UUID NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_dashboard_tab_name UNIQUE (dashboard_id, name)
);

CREATE INDEX IF NOT EXISTS idx_dashboard_tabs_dashboard_pos ON dashboard_tabs (dashboard_id, position);

-- 2. Add overview_summary to dashboards table
ALTER TABLE dashboards ADD COLUMN IF NOT EXISTS overview_summary TEXT;

-- 3. Update dashboard_widgets to support tabs and text widgets
ALTER TABLE dashboard_widgets ADD COLUMN IF NOT EXISTS tab_id UUID REFERENCES dashboard_tabs(id) ON DELETE CASCADE;
ALTER TABLE dashboard_widgets ADD COLUMN IF NOT EXISTS widget_type TEXT NOT NULL DEFAULT 'insight';
ALTER TABLE dashboard_widgets ALTER COLUMN insight_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_tab_id ON dashboard_widgets (tab_id);
