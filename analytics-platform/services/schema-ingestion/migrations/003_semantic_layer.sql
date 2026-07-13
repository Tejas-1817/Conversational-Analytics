-- 003_semantic_layer.sql

BEGIN;

-- Drop the old stub metrics table if it exists
DROP TABLE IF EXISTS metrics CASCADE;

-- Enums
CREATE TYPE agg_type AS ENUM ('SUM', 'AVG', 'COUNT', 'COUNT_DISTINCT', 'MIN', 'MAX', 'CUSTOM');
CREATE TYPE join_type AS ENUM ('INNER', 'LEFT', 'RIGHT', 'FULL');
CREATE TYPE entity_type AS ENUM ('METRIC', 'DIMENSION', 'GLOSSARY');
CREATE TYPE time_grain AS ENUM ('YEAR', 'QUARTER', 'MONTH', 'WEEK', 'DAY', 'HOUR', 'NONE');

-- 1. Semantic Dimensions
CREATE TABLE semantic_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    business_name TEXT NOT NULL,
    description TEXT,
    source_table_id UUID REFERENCES tables_meta(id) ON DELETE CASCADE,
    source_column_id UUID REFERENCES columns_meta(id) ON DELETE CASCADE,
    data_type TEXT NOT NULL,
    is_time_dimension BOOLEAN DEFAULT FALSE,
    time_granularity time_grain DEFAULT 'NONE',
    visibility TEXT DEFAULT 'visible',
    status approval_status DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- 2. Semantic Joins
CREATE TABLE semantic_joins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    left_table_id UUID REFERENCES tables_meta(id) ON DELETE CASCADE,
    right_table_id UUID REFERENCES tables_meta(id) ON DELETE CASCADE,
    join_condition TEXT NOT NULL, -- e.g., "A.id = B.a_id"
    join_type join_type DEFAULT 'LEFT',
    cardinality TEXT DEFAULT 'many_to_one',
    confidence NUMERIC(4,3) DEFAULT 1.0,
    status approval_status DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- 3. Semantic Metrics
CREATE TABLE semantic_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    business_name TEXT,
    description TEXT,
    is_calculated BOOLEAN DEFAULT FALSE,
    aggregation_type agg_type DEFAULT 'CUSTOM',
    expression TEXT NOT NULL,
    source_table_id UUID REFERENCES tables_meta(id) ON DELETE SET NULL,
    source_column_id UUID REFERENCES columns_meta(id) ON DELETE SET NULL,
    owner TEXT,
    status approval_status DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    UNIQUE (tenant_id, name)
);

-- Allowed Dimensions mapping (Junction)
CREATE TABLE metric_allowed_dimensions (
    metric_id UUID REFERENCES semantic_metrics(id) ON DELETE CASCADE,
    dimension_id UUID REFERENCES semantic_dimensions(id) ON DELETE CASCADE,
    PRIMARY KEY (metric_id, dimension_id)
);

-- Allowed Filters mapping (Junction)
CREATE TABLE metric_allowed_filters (
    metric_id UUID REFERENCES semantic_metrics(id) ON DELETE CASCADE,
    filter_dimension_id UUID REFERENCES semantic_dimensions(id) ON DELETE CASCADE,
    PRIMARY KEY (metric_id, filter_dimension_id)
);

-- 4. Business Glossary
CREATE TABLE business_glossary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    term TEXT NOT NULL,
    business_definition TEXT NOT NULL,
    owner TEXT,
    status approval_status DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    UNIQUE (tenant_id, term)
);

-- Glossary Links
CREATE TABLE glossary_links (
    glossary_id UUID REFERENCES business_glossary(id) ON DELETE CASCADE,
    entity_type entity_type NOT NULL,
    entity_id UUID NOT NULL,
    PRIMARY KEY (glossary_id, entity_type, entity_id)
);

-- 5. Semantic Synonyms
CREATE TABLE semantic_synonyms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity_type entity_type NOT NULL,
    entity_id UUID NOT NULL,
    synonym TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (tenant_id, entity_type, entity_id, synonym)
);

-- 6. Versions (Historical Snapshots)
CREATE TABLE metric_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_id UUID REFERENCES semantic_metrics(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    UNIQUE (metric_id, version)
);

CREATE TABLE dimension_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dimension_id UUID REFERENCES semantic_dimensions(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    UNIQUE (dimension_id, version)
);

CREATE TABLE join_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    join_id UUID REFERENCES semantic_joins(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL,
    UNIQUE (join_id, version)
);

-- Add indexes
CREATE INDEX idx_metrics_tenant ON semantic_metrics(tenant_id);
CREATE INDEX idx_dims_tenant ON semantic_dimensions(tenant_id);
CREATE INDEX idx_joins_tenant ON semantic_joins(tenant_id);
CREATE INDEX idx_glossary_tenant ON business_glossary(tenant_id);
CREATE INDEX idx_synonyms_synonym ON semantic_synonyms(synonym);

COMMIT;
