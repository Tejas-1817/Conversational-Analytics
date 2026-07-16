-- Phase 3.3 Bug Fixes - Additional Unique Constraints

-- Chart Recommendation Missing Columns
ALTER TABLE chart_recommendations ADD COLUMN IF NOT EXISTS dashboard_id UUID REFERENCES dashboard_recommendations(id) ON DELETE CASCADE;
ALTER TABLE chart_recommendations ADD COLUMN IF NOT EXISTS kpi_name TEXT;

-- Constraints
ALTER TABLE chart_recommendations DROP CONSTRAINT IF EXISTS chart_recommendations_dashboard_id_kpi_name_key;
ALTER TABLE chart_recommendations ADD CONSTRAINT chart_recommendations_dashboard_id_kpi_name_key UNIQUE (dashboard_id, kpi_name);

ALTER TABLE suggested_questions DROP CONSTRAINT IF EXISTS suggested_questions_semantic_model_id_question_key;
ALTER TABLE suggested_questions ADD CONSTRAINT suggested_questions_semantic_model_id_question_key UNIQUE (semantic_model_id, question);
