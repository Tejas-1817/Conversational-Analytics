export interface ColumnGraphMeta {
  id: string;
  column_name: string;
  data_type: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  description?: string | null;
}

export interface DomainGraphNode {
  id: string; // table_id as string
  table_id: string;
  table_name: string;
  business_name?: string | null;
  schema_name: string;
  source_id: string;
  source_name: string;
  source_type: string;
  row_count?: number | null;
  column_count: number;
  columns: ColumnGraphMeta[];
}

export interface DomainGraphEdge {
  id: string; // relationship_id as string
  relationship_id: string;
  source_table_id: string;
  source_column_id: string;
  source_column_name: string;
  target_table_id: string;
  target_column_id: string;
  target_column_name: string;
  cardinality: string; // "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many"
  relationship_source: string; // "foreign_key" | "name_match" | "value_overlap" | "user_defined"
  confidence: number;
  status: string; // "draft" | "approved" | "rejected" | "reviewed"
  evidence: Record<string, any>;
}

export interface DomainGraphResponse {
  domain_id: string;
  domain_name: string;
  nodes: DomainGraphNode[];
  edges: DomainGraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export type GraphVisualizationMode = 'erd' | 'neo4j_circle';

export type TableFilterMode = 'all' | 'related' | 'connected';
export type ConnectedScope = 'all' | 'direct';

// Runtime fallbacks in case of non-type imports
export const DomainGraphNode = {};
export const DomainGraphEdge = {};
export const DomainGraphResponse = {};
export const ColumnGraphMeta = {};
