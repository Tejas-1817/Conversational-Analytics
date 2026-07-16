-- =============================================================================
-- Phase 3: AI-Powered Automatic Semantic Layer Generation
-- =============================================================================

CREATE TYPE generation_status AS ENUM ('ACTIVE', 'REVIEW_REQUIRED', 'REJECTED');

CREATE TABLE semantic_models (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL,
    source_id            uuid NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    metadata_version_id  uuid NOT NULL REFERENCES metadata_versions(id) ON DELETE CASCADE,
    semantic_version     integer NOT NULL,
    generated_at         timestamptz NOT NULL DEFAULT now(),
    generated_by_model   text NOT NULL,
    generation_status    generation_status NOT NULL DEFAULT 'ACTIVE',
    confidence_summary   jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_active            boolean NOT NULL DEFAULT false,
    UNIQUE (source_id, semantic_version)
);
CREATE INDEX idx_semantic_models_tenant ON semantic_models(tenant_id);

CREATE TABLE business_ontology (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_model_id    uuid NOT NULL REFERENCES semantic_models(id) ON DELETE CASCADE,
    domain               text NOT NULL,
    description          text,
    confidence           numeric(4, 3) NOT NULL DEFAULT 1.0,
    status               generation_status NOT NULL DEFAULT 'ACTIVE',
    generated_at         timestamptz NOT NULL DEFAULT now(),
    reviewed             boolean NOT NULL DEFAULT false,
    approved             boolean NOT NULL DEFAULT false,
    source               text NOT NULL DEFAULT 'ai_generated',
    UNIQUE (semantic_model_id, domain)
);

CREATE TABLE semantic_kpis (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_model_id    uuid NOT NULL REFERENCES semantic_models(id) ON DELETE CASCADE,
    ontology_id          uuid REFERENCES business_ontology(id) ON DELETE SET NULL,
    name                 text NOT NULL,
    description          text,
    formula              text NOT NULL,
    dimensions           text[] NOT NULL DEFAULT '{}',
    measures             text[] NOT NULL DEFAULT '{}',
    confidence           numeric(4, 3) NOT NULL DEFAULT 1.0,
    status               generation_status NOT NULL DEFAULT 'ACTIVE',
    generated_at         timestamptz NOT NULL DEFAULT now(),
    reviewed             boolean NOT NULL DEFAULT false,
    approved             boolean NOT NULL DEFAULT false,
    source               text NOT NULL DEFAULT 'ai_generated',
    UNIQUE (semantic_model_id, name)
);

CREATE TABLE dashboard_recommendations (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_model_id    uuid NOT NULL REFERENCES semantic_models(id) ON DELETE CASCADE,
    ontology_id          uuid REFERENCES business_ontology(id) ON DELETE SET NULL,
    name                 text NOT NULL,
    description          text,
    business_goal        text,
    structure            jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence           numeric(4, 3) NOT NULL DEFAULT 1.0,
    status               generation_status NOT NULL DEFAULT 'ACTIVE',
    generated_at         timestamptz NOT NULL DEFAULT now(),
    reviewed             boolean NOT NULL DEFAULT false,
    approved             boolean NOT NULL DEFAULT false,
    source               text NOT NULL DEFAULT 'ai_generated',
    UNIQUE (semantic_model_id, name)
);

CREATE TABLE chart_recommendations (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_model_id    uuid NOT NULL REFERENCES semantic_models(id) ON DELETE CASCADE,
    insight_type         text NOT NULL,
    chart_type           text NOT NULL,
    applicability        text NOT NULL,
    confidence           numeric(4, 3) NOT NULL DEFAULT 1.0,
    status               generation_status NOT NULL DEFAULT 'ACTIVE',
    generated_at         timestamptz NOT NULL DEFAULT now(),
    reviewed             boolean NOT NULL DEFAULT false,
    approved             boolean NOT NULL DEFAULT false,
    source               text NOT NULL DEFAULT 'ai_generated'
);

CREATE TABLE suggested_questions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_model_id    uuid NOT NULL REFERENCES semantic_models(id) ON DELETE CASCADE,
    ontology_id          uuid REFERENCES business_ontology(id) ON DELETE SET NULL,
    entity_name          text NOT NULL,
    question             text NOT NULL,
    filter_logic         jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence           numeric(4, 3) NOT NULL DEFAULT 1.0,
    status               generation_status NOT NULL DEFAULT 'ACTIVE',
    generated_at         timestamptz NOT NULL DEFAULT now(),
    reviewed             boolean NOT NULL DEFAULT false,
    approved             boolean NOT NULL DEFAULT false,
    source               text NOT NULL DEFAULT 'ai_generated'
);

CREATE TABLE ai_context (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_model_id    uuid NOT NULL REFERENCES semantic_models(id) ON DELETE CASCADE,
    purpose              text,
    default_filters      jsonb NOT NULL DEFAULT '{}'::jsonb,
    time_intelligence    jsonb NOT NULL DEFAULT '{}'::jsonb,
    chart_preferences    jsonb NOT NULL DEFAULT '{}'::jsonb,
    context_payload      jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence           numeric(4, 3) NOT NULL DEFAULT 1.0,
    status               generation_status NOT NULL DEFAULT 'ACTIVE',
    generated_at         timestamptz NOT NULL DEFAULT now(),
    reviewed             boolean NOT NULL DEFAULT false,
    approved             boolean NOT NULL DEFAULT false,
    source               text NOT NULL DEFAULT 'ai_generated',
    UNIQUE (semantic_model_id)
);

-- We need to alter existing semantic tables to link to semantic_models optionally or modify our logic.
-- However, to keep it simple and not break existing tables, we can add semantic_model_id to them.
ALTER TABLE semantic_dimensions ADD COLUMN semantic_model_id uuid REFERENCES semantic_models(id) ON DELETE CASCADE;
ALTER TABLE semantic_metrics ADD COLUMN semantic_model_id uuid REFERENCES semantic_models(id) ON DELETE CASCADE;
ALTER TABLE semantic_joins ADD COLUMN semantic_model_id uuid REFERENCES semantic_models(id) ON DELETE CASCADE;
ALTER TABLE business_glossary ADD COLUMN semantic_model_id uuid REFERENCES semantic_models(id) ON DELETE CASCADE;
