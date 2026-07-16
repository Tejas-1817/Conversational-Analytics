-- Add ENUM types if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'generation_source') THEN
        CREATE TYPE generation_source AS ENUM ('MANUAL', 'AI');
    END IF;
END$$;

-- Alter semantic_dimensions
ALTER TABLE semantic_dimensions
ADD COLUMN IF NOT EXISTS generation_source generation_source NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4, 3),
ADD COLUMN IF NOT EXISTS prompt_version TEXT,
ADD COLUMN IF NOT EXISTS review_status generation_status NOT NULL DEFAULT 'ACTIVE';

-- Alter semantic_joins
ALTER TABLE semantic_joins
ADD COLUMN IF NOT EXISTS generation_source generation_source NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS prompt_version TEXT,
ADD COLUMN IF NOT EXISTS review_status generation_status NOT NULL DEFAULT 'ACTIVE';

-- Alter semantic_metrics
ALTER TABLE semantic_metrics
ADD COLUMN IF NOT EXISTS generation_source generation_source NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4, 3),
ADD COLUMN IF NOT EXISTS prompt_version TEXT,
ADD COLUMN IF NOT EXISTS review_status generation_status NOT NULL DEFAULT 'ACTIVE';

-- Alter business_glossary
ALTER TABLE business_glossary
ADD COLUMN IF NOT EXISTS generation_source generation_source NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4, 3),
ADD COLUMN IF NOT EXISTS prompt_version TEXT,
ADD COLUMN IF NOT EXISTS review_status generation_status NOT NULL DEFAULT 'ACTIVE';

-- Alter semantic_models
ALTER TABLE semantic_models
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);

-- Alter business_ontology
ALTER TABLE business_ontology
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);

-- Alter semantic_kpis
ALTER TABLE semantic_kpis
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);

-- Alter dashboard_recommendations
ALTER TABLE dashboard_recommendations
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);

-- Alter chart_recommendations
ALTER TABLE chart_recommendations
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);

-- Alter suggested_questions
ALTER TABLE suggested_questions
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);

-- Alter ai_context
ALTER TABLE ai_context
ADD COLUMN IF NOT EXISTS generation_source generation_source,
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50),
ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);
