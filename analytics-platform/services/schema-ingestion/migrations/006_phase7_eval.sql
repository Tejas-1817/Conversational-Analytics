-- Phase 7 Evaluation Models Migration

CREATE TABLE IF NOT EXISTS benchmark_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    domain TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    created_by TEXT NOT NULL,
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS evaluation_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES benchmark_collections(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    difficulty TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    expected_intent JSONB,
    expected_plan JSONB,
    expected_sql TEXT,
    expected_result JSONB,
    expected_chart TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    collection_id UUID NOT NULL REFERENCES benchmark_collections(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'running',
    overall_score NUMERIC(5, 4),
    pass_rate NUMERIC(5, 4),
    avg_latency_ms INTEGER,
    error_rate NUMERIC(5, 4),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    finished_at TIMESTAMP WITH TIME ZONE,
    triggered_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
    generated_intent JSONB,
    generated_plan JSONB,
    generated_sql TEXT,
    generated_result JSONB,
    generated_chart TEXT,
    generated_answer TEXT,
    execution_time_ms INTEGER,
    error TEXT,
    intent_score NUMERIC(5, 4),
    plan_score NUMERIC(5, 4),
    sql_score NUMERIC(5, 4),
    result_score NUMERIC(5, 4),
    chart_score NUMERIC(5, 4),
    nl_score NUMERIC(5, 4),
    reliability_score NUMERIC(5, 4),
    is_pass BOOLEAN,
    failure_reasons TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
