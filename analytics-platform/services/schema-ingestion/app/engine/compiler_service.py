"""SQL compiler: translates a LogicalQueryPlan into a parameterized SQL string.

Invariants this module upholds:
- The LLM never writes raw SQL; this compiler does.
- RLS tenant_id predicate is always injected at compile time — the LLM must not produce it.
- Every filter column is resolved via ColumnMeta (real table/column), never guessed.
- Every dimension is resolved via SemanticDimension → ColumnMeta → TableMeta (real column),
  never derived by transforming the business_name string.
- validate_safety() is always called before returning; forbidden keywords abort compilation.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ColumnMeta, SemanticDimension, SemanticKPI, SemanticMetric, TableMeta
from app.schemas_engine import LogicalQueryPlan


class SQLSafetyError(Exception):
    pass


class ColumnResolutionError(Exception):
    """Raised when a dimension or filter cannot be resolved to a real ColumnMeta row."""


class CompiledQuery:
    def __init__(self, sql: str, params: dict):
        self.sql = sql
        self.params = params


class CompilerService:
    @staticmethod
    def _resolve_column(db: Session, column_id: uuid.UUID, context: str) -> tuple[ColumnMeta, TableMeta]:
        """Return (ColumnMeta, TableMeta) for the given column_id.

        Raises ColumnResolutionError if either row is missing — callers must never
        fall back to guessing a column name.
        """
        col = db.scalar(select(ColumnMeta).where(ColumnMeta.id == column_id))
        if col is None:
            raise ColumnResolutionError(
                f"ColumnMeta not found for column_id={column_id} ({context}). "
                "The semantic layer references a column that no longer exists in the catalog."
            )
        tbl = db.scalar(select(TableMeta).where(TableMeta.id == col.table_id))
        if tbl is None:
            raise ColumnResolutionError(
                f"TableMeta not found for table_id={col.table_id} referenced by "
                f"column '{col.column_name}' ({context})."
            )
        return col, tbl

    @staticmethod
    def compile_plan(db: Session, tenant_id: uuid.UUID, plan: LogicalQueryPlan) -> CompiledQuery:
        # Load Metric or KPI
        metric = None
        if plan.metric_ids:
            metric = db.scalar(select(SemanticMetric).where(
                SemanticMetric.id == plan.metric_ids[0],
                SemanticMetric.tenant_id == tenant_id
            ))
            if not metric:
                raise ColumnResolutionError("Metric not found or tenant mismatch")
        elif plan.kpi_ids:
            pass  # handled in the elif block below

        select_clause: list[str] = []
        group_by_clause: list[str] = []
        params: dict = {"tenant_id": str(tenant_id)}

        metric_tbl: TableMeta | None = None
        if metric:
            metric_col, metric_tbl = CompilerService._resolve_column(
                db, metric.source_column_id, f"metric '{metric.name}'"
            )
            agg = metric.aggregation_type if metric.aggregation_type else "SUM"
            select_clause.append(f"{agg}({metric_tbl.table_name}.{metric_col.column_name}) as \"{metric.name}\"")
        elif plan.kpi_ids:
            kpi = db.scalar(select(SemanticKPI).where(SemanticKPI.id == plan.kpi_ids[0]))
            select_clause.append(f"{kpi.formula} as \"{kpi.name}\"")

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

        # --- Dimensions: resolved via SemanticDimension → source_column_id → ColumnMeta → TableMeta ---
        for idx, dim_id in enumerate(plan.dimension_ids):
            dim = db.scalar(select(SemanticDimension).where(SemanticDimension.id == dim_id))
            if dim is None:
                raise ColumnResolutionError(
                    f"SemanticDimension not found for id={dim_id}. "
                    "The query plan references a dimension that does not exist."
                )
            if dim.source_column_id is None:
                raise ColumnResolutionError(
                    f"SemanticDimension '{dim.business_name}' (id={dim_id}) has no "
                    "source_column_id set. Cannot compile to SQL without a real column reference."
                )
            dim_col, dim_tbl = CompilerService._resolve_column(
                db, dim.source_column_id, f"dimension '{dim.business_name}'"
            )
            alias = f"dim_{idx}"
            dim_expr = f"{dim_tbl.table_name}.{dim_col.column_name}"
            select_clause.append(f"{dim_expr} as {alias}")
            group_by_clause.append(dim_expr)
        where_clause: list[str] = []
        if metric_tbl:
            where_clause.append(f"{metric_tbl.table_name}.tenant_id = :tenant_id")  # RLS injection
            
            if plan.time_granularity:
                time_dim = db.scalar(
                    select(SemanticDimension)
                    .where(SemanticDimension.source_table_id == metric_tbl.id)
                    .where(SemanticDimension.is_time_dimension == True)
                    .limit(1)
                )
                if not time_dim:
                    raise SQLSafetyError(f"Cannot apply time_granularity '{plan.time_granularity}' because no time dimension is configured for table '{metric_tbl.table_name}'.")
                
                time_col, time_tbl = CompilerService._resolve_column(db, time_dim.source_column_id, "time dimension")
                # Postgres-compatible DATE_TRUNC
                trunc_expr = f"DATE_TRUNC('{plan.time_granularity}', {time_tbl.table_name}.{time_col.column_name})"
                select_clause.append(f"{trunc_expr} as time_period")
                group_by_clause.append(trunc_expr)

        # --- Filters: resolved via QueryPlanFilter.column_id → ColumnMeta → TableMeta ---
        for idx, f in enumerate(plan.filters):
            param_key = f"filter_{idx}"
            filter_col, filter_tbl = CompilerService._resolve_column(
                db, f.column_id, f"filter index {idx}"
            )
            where_clause.append(f"{filter_tbl.table_name}.{filter_col.column_name} {f.operator} :{param_key}")
            params[param_key] = f.value

        # Assemble
        sql = "SELECT " + ", ".join(select_clause)
        if metric_tbl:
            sql += f" FROM {metric_tbl.table_name}"
        if where_clause:
            sql += " WHERE " + " AND ".join(where_clause)
        if group_by_clause:
            sql += " GROUP BY " + ", ".join(group_by_clause)

        if plan.limit:
            sql += f" LIMIT {min(plan.limit, 1000)}"
        else:
            sql += " LIMIT 100"

        CompilerService.validate_safety(sql)
        return CompiledQuery(sql, params)

    @staticmethod
    def validate_safety(sql: str) -> None:
        """SQL Safety Validator — ensures no mutation and no wildcard selects."""
        sql_upper = sql.upper()
        forbidden_keywords = [
            "UPDATE ", "DELETE ", "INSERT ", "DROP ", "ALTER ",
            "TRUNCATE ", "GRANT ", "REVOKE ", "SELECT *",
        ]
        for kw in forbidden_keywords:
            if kw in sql_upper:
                raise SQLSafetyError(f"Generated SQL contains forbidden keyword: {kw.strip()}")

        if ";" in sql:
            raise SQLSafetyError("Statement chaining (;) is not allowed.")
