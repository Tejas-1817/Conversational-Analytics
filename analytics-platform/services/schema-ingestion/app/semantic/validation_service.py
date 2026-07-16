import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ColumnMeta, SemanticMetric, TableMeta
from app.semantic.formula_parser import CircularDependencyError, InvalidExpressionError, MetricFormulaParser


class ValidationService:
    @staticmethod
    def validate_metric(db: Session, tenant_id: uuid.UUID, metric_name: str, expression: str,
                        is_calculated: bool, source_table_id: uuid.UUID = None, source_column_id: uuid.UUID = None):
        """Validates metric creation/update logic."""

        # 1. Base Metric Validation
        if not is_calculated:
            if not source_table_id or not source_column_id:
                raise HTTPException(status_code=400, detail="Base metrics require source_table_id and source_column_id")

            # Verify table and column exist and are active
            table = db.scalar(select(TableMeta).where(TableMeta.id == source_table_id, TableMeta.is_active == True))
            if not table:
                raise HTTPException(status_code=400, detail=f"Source table {source_table_id} not found or inactive")

            column = db.scalar(select(ColumnMeta).where(ColumnMeta.id == source_column_id, ColumnMeta.is_active == True))
            if not column:
                raise HTTPException(status_code=400, detail=f"Source column {source_column_id} not found or inactive")

        # 2. Calculated Metric Validation
        if is_calculated:
            if not expression:
                raise HTTPException(status_code=400, detail="Calculated metrics require an expression")

            try:
                # Parse formula to get dependencies
                deps = MetricFormulaParser.extract_metrics(expression)

                # Fetch all existing metrics to build dependency graph
                existing_metrics = db.execute(
                    select(SemanticMetric.name, SemanticMetric.expression)
                    .where(SemanticMetric.tenant_id == tenant_id)
                ).all()

                all_metrics = {m.name: m.expression for m in existing_metrics}

                # Ensure all referenced dependencies exist in the DB
                for dep in deps:
                    if dep not in all_metrics and dep != metric_name:
                        raise HTTPException(status_code=400, detail=f"Referenced metric '{dep}' does not exist")

                # Ensure no circular dependency
                MetricFormulaParser.validate_no_cycles(metric_name, expression, all_metrics)

            except (InvalidExpressionError, CircularDependencyError) as e:
                raise HTTPException(status_code=400, detail=str(e))
