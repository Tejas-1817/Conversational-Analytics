import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ColumnMeta, SemanticDimension, SemanticMetric, TableMeta, SemanticKPI
from app.schemas_engine import LogicalQueryPlan


class SQLSafetyError(Exception):
    pass

class CompiledQuery:
    def __init__(self, sql: str, params: dict):
        self.sql = sql
        self.params = params

class CompilerService:
    @staticmethod
    def compile_plan(db: Session, tenant_id: uuid.UUID, plan: LogicalQueryPlan) -> CompiledQuery:
        # Load Metric or KPI
        metric = None
        if plan.metric_ids:
            metric = db.scalar(select(SemanticMetric).where(
                SemanticMetric.id == plan.metric_ids[0],
                SemanticMetric.tenant_id == tenant_id
            ))
        elif plan.kpi_ids:
            # For this MVP compilation, just take the first KPI's formula directly if no metric
            pass

        select_clause = []
        group_by_clause = []
        params = {"tenant_id": str(tenant_id)}

        metric_tbl = None
        if metric:
            metric_col = db.scalar(select(ColumnMeta).where(ColumnMeta.id == metric.source_column_id))
            metric_tbl = db.scalar(select(TableMeta).where(TableMeta.id == metric.source_table_id))
            agg = metric.aggregation_type if metric.aggregation_type else "SUM"
            select_clause.append(f"{agg}({metric_tbl.name}.{metric_col.name}) as {metric.name}")
        elif plan.kpi_ids:
            kpi = db.scalar(select(SemanticKPI).where(SemanticKPI.id == plan.kpi_ids[0]))
            select_clause.append(f"{kpi.formula} as {kpi.name}")
            
            # Resolve physical table from the KPI's primary measure
            if kpi.measures:
                first_metric = db.scalar(select(SemanticMetric).where(
                    SemanticMetric.semantic_model_id == kpi.semantic_model_id,
                    SemanticMetric.name == kpi.measures[0]
                ))
                if first_metric and first_metric.source_table_id:
                    metric_tbl = db.scalar(select(TableMeta).where(TableMeta.id == first_metric.source_table_id))
            
            if not metric_tbl:
                raise SQLSafetyError(f"Cannot determine physical table for KPI '{kpi.name}'.")

        # Load Dimensions
        for idx, dim_id in enumerate(plan.dimension_ids):
            dim = db.scalar(select(SemanticDimension).where(SemanticDimension.id == dim_id))
            # Mock column name resolution (In reality, dim points to a source_column_id)
            dim_expr = f"{metric_tbl.name if metric_tbl else 'table'}.{dim.business_name.lower().replace(' ', '_')}"
            select_clause.append(f"{dim_expr} as dim_{idx}")
            group_by_clause.append(f"dim_{idx}")

        where_clause = []
        if metric_tbl:
            where_clause.append(f"{metric_tbl.name}.tenant_id = :tenant_id") # Permission Injection

        for idx, f in enumerate(plan.filters):
            param_key = f"filter_{idx}"
            table_name = metric_tbl.name if metric_tbl else 'table'
            where_clause.append(f"{table_name}.filter_col {f.operator} :{param_key}")
            params[param_key] = f.value

        sql = "SELECT " + ", ".join(select_clause)
        if metric_tbl:
            sql += f" FROM {metric_tbl.name}"
        if where_clause:
            sql += " WHERE " + " AND ".join(where_clause)

        if group_by_clause:
            sql += " GROUP BY " + ", ".join(group_by_clause)

        if plan.limit:
            sql += f" LIMIT {min(plan.limit, 1000)}" # Hard limit of 1000 rows
        else:
            sql += " LIMIT 100"

        CompilerService.validate_safety(sql)
        return CompiledQuery(sql, params)

    @staticmethod
    def validate_safety(sql: str) -> None:
        """SQL Safety Validator - ensures no mutation and no wildcard selects."""
        sql_upper = sql.upper()
        forbidden_keywords = ["UPDATE ", "DELETE ", "INSERT ", "DROP ", "ALTER ", "TRUNCATE ", "GRANT ", "REVOKE ", "SELECT *"]

        for kw in forbidden_keywords:
            if kw in sql_upper:
                raise SQLSafetyError(f"Generated SQL contains forbidden keyword: {kw.strip()}")

        if ";" in sql:
            raise SQLSafetyError("Statement chaining (;) is not allowed.")
