from typing import List, Optional
from pydantic import BaseModel, Field

class AIDimensionSchema(BaseModel):
    business_name: str = Field(description="A user-friendly, business-readable name for this dimension.")
    description: str = Field(description="A detailed description of what this dimension represents.")
    source_column_name: str = Field(description="The exact physical column name from the table this dimension corresponds to.")
    is_time_dimension: bool = Field(default=False, description="True if this column represents a date or timestamp.")
    time_granularity: str = Field(default="NONE", description="The lowest granularity of time this column represents, e.g., 'DAY', 'MONTH', 'YEAR', 'NONE'.")

class AIMeasureSchema(BaseModel):
    business_name: str = Field(description="A user-friendly, business-readable name for this measure (numeric field).")
    description: str = Field(description="A detailed description of what this measure represents.")
    source_column_name: str = Field(description="The exact physical column name from the table.")
    aggregation_type: str = Field(description="The default aggregation type. Must be one of SUM, AVG, COUNT, COUNT_DISTINCT, MIN, MAX.")

class AIKPISchema(BaseModel):
    business_name: str = Field(description="A user-friendly name for this Key Performance Indicator (KPI).")
    description: str = Field(description="A detailed description of this KPI.")
    is_calculated: bool = Field(default=True, description="True if this KPI is derived from a formula.")
    expression: str = Field(description="The SQL-compatible mathematical formula for this KPI, referencing physical column names, e.g., 'SUM(revenue) - SUM(cost)'")

class AIGlossaryTermSchema(BaseModel):
    term: str = Field(description="The business term or acronym.")
    business_definition: str = Field(description="A clear, business-friendly definition of the term within the context of this data.")

class AISemanticRelationshipSchema(BaseModel):
    from_column_name: str = Field(description="The exact physical column name representing the foreign key.")
    to_table_name: str = Field(description="The exact physical table name this foreign key points to.")
    to_column_name: str = Field(description="The exact physical column name representing the primary key in the referenced table.")
    cardinality: str = Field(description="The cardinality of the relationship. Expected: 'many_to_one', 'one_to_many', 'one_to_one'.")

class AITableEnrichmentSchema(BaseModel):
    """
    The master schema for enriching a single database table.
    """
    business_description: str = Field(description="A high-level business description of what entities or events this table tracks.")
    dimensions: List[AIDimensionSchema] = Field(description="A list of proposed dimensions (categorical attributes) found in the table.")
    measures: List[AIMeasureSchema] = Field(description="A list of proposed raw measures (numeric facts) found in the table.")
    kpis: List[AIKPISchema] = Field(default_factory=list, description="A list of proposed calculated KPIs relevant to this table's data.")
    glossary_terms: List[AIGlossaryTermSchema] = Field(default_factory=list, description="A list of domain-specific business terms derived from the table.")
    relationships: List[AISemanticRelationshipSchema] = Field(default_factory=list, description="A list of relationships (joins) discovered.")
    confidence_score: float = Field(description="A self-assessed confidence score between 0.0 and 1.0 for these generated semantics.")

class AIOntologyDomainSchema(BaseModel):
    domain: str = Field(description="The broad business domain this data belongs to (e.g., 'Sales', 'Marketing', 'Logistics').")
    description: str = Field(description="Description of what this domain covers.")

class AICrossTableKPISchema(BaseModel):
    name: str = Field(description="A user-friendly name for this Key Performance Indicator.")
    description: str = Field(description="Detailed description of the KPI.")
    formula: str = Field(description="The mathematical formula for this KPI, which may span multiple tables.")
    dimensions: List[str] = Field(description="A list of dimension names that can be used to slice this KPI.")
    measures: List[str] = Field(description="A list of measure names used to calculate this KPI.")

class AIDashboardWidgetSchema(BaseModel):
    kpi_name: str = Field(description="The name of the KPI to display.")
    chart_type: str = Field(description="Recommended chart type (e.g., 'line_chart', 'bar_chart', 'scorecard').")
    filters: List[str] = Field(description="Recommended default filters for this widget.")
    drill_paths: List[str] = Field(description="Recommended dimensions to drill down into.")

class AIDashboardRecommendationSchema(BaseModel):
    name: str = Field(description="The title of the dashboard.")
    description: str = Field(description="What this dashboard is designed to monitor.")
    business_goal: str = Field(description="The primary business goal this dashboard supports.")
    widgets: List[AIDashboardWidgetSchema] = Field(description="The widgets that make up this dashboard.")

class AISuggestedQuestionSchema(BaseModel):
    entity_name: str = Field(description="The primary entity this question relates to (e.g., 'Customer', 'Order').")
    question: str = Field(description="A natural language business question (e.g., 'What is our total revenue by region?').")
    filter_logic: dict = Field(description="JSON-compatible dictionary representing the implicit filters in this question.")

class AIGlobalContextSchema(BaseModel):
    purpose: str = Field(description="The overarching purpose of this data source.")
    default_filters: dict = Field(description="Standard global filters to apply across the data source.")
    time_intelligence: dict = Field(description="Global time intelligence settings (e.g., fiscal year start).")
    chart_preferences: dict = Field(description="Global charting preferences (e.g., standard colors for statuses).")

class AIGlobalEnrichmentSchema(BaseModel):
    """
    The master schema for enriching the entire database schema globally.
    """
    ontology: List[AIOntologyDomainSchema] = Field(default_factory=list, description="Proposed business ontology domains.")
    kpis: List[AICrossTableKPISchema] = Field(default_factory=list, description="Proposed cross-table or global KPIs.")
    dashboards: List[AIDashboardRecommendationSchema] = Field(default_factory=list, description="Proposed dashboard layouts.")
    questions: List[AISuggestedQuestionSchema] = Field(default_factory=list, description="Suggested natural language questions.")
    ai_context: AIGlobalContextSchema = Field(description="Global AI context and preferences.")
    confidence_score: float = Field(description="A self-assessed confidence score between 0.0 and 1.0.")
