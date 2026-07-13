import uuid
import re
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import SemanticMetric, SemanticDimension, TableMeta, ColumnMeta
from app.schemas_engine import StructuredQueryPlan

class SQLSafetyError(Exception):
    pass

class CompiledQuery:
    def __init__(self, sql: str, params: dict):
        self.sql = sql
        self.params = params

class CompilerService:
    @staticmethod
    def compile_plan(db: Session, tenant_id: uuid.UUID, plan: StructuredQueryPlan) -> CompiledQuery:
        # Load Metric
        metric = db.scalar(select(SemanticMetric).where(
            SemanticMetric.id == plan.metric_id,
            SemanticMetric.tenant_id == tenant_id
        ))
        
        # Load Metric Table/Column names
        metric_col = db.scalar(select(ColumnMeta).where(ColumnMeta.id == metric.source_column_id))
        metric_tbl = db.scalar(select(TableMeta).where(TableMeta.id == metric.source_table_id))
        
        # For simplicity, we assume all dimensions live in the same table as the metric 
        # or we just use the column expressions.
        
        select_clause = []
        group_by_clause = []
        params = {"tenant_id": str(tenant_id)}
        
        # Determine aggregate
        agg = metric.aggregation_type if metric.aggregation_type else "SUM"
        select_clause.append(f"{agg}({metric_tbl.name}.{metric_col.name}) as {metric.name}")
        
        # Load Dimensions
        for idx, dim_id in enumerate(plan.dimension_ids):
            dim = db.scalar(select(SemanticDimension).where(SemanticDimension.id == dim_id))
            # Mock column name resolution (In reality, dim points to a source_column_id)
            dim_expr = f"{metric_tbl.name}.{dim.business_name.lower().replace(' ', '_')}"
            select_clause.append(f"{dim_expr} as dim_{idx}")
            group_by_clause.append(f"dim_{idx}")
            
        where_clause = [f"{metric_tbl.name}.tenant_id = :tenant_id"] # Permission Injection
        
        for idx, f in enumerate(plan.filters):
            param_key = f"filter_{idx}"
            where_clause.append(f"{metric_tbl.name}.filter_col {f.operator} :{param_key}")
            params[param_key] = f.value
            
        sql = "SELECT " + ", ".join(select_clause)
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
