-- Phase 3.3 Stabilization Migration

-- 1. SemanticJoin Schema Update
ALTER TABLE semantic_joins ADD COLUMN IF NOT EXISTS left_column_id UUID REFERENCES columns_meta(id) ON DELETE CASCADE;
ALTER TABLE semantic_joins ADD COLUMN IF NOT EXISTS right_column_id UUID REFERENCES columns_meta(id) ON DELETE CASCADE;

-- 2. SemanticMetric UniqueConstraint Fix
ALTER TABLE semantic_metrics DROP CONSTRAINT IF EXISTS semantic_metrics_tenant_id_name_key;
ALTER TABLE semantic_metrics ADD CONSTRAINT semantic_metrics_semantic_model_id_name_key UNIQUE (semantic_model_id, name);

-- 3. BusinessGlossary UniqueConstraint Fix
ALTER TABLE business_glossary DROP CONSTRAINT IF EXISTS business_glossary_tenant_id_term_key;
ALTER TABLE business_glossary ADD CONSTRAINT business_glossary_semantic_model_id_term_key UNIQUE (semantic_model_id, term);
