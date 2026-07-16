import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SemanticDimension, SemanticMetric, SemanticKPI
from app.schemas_engine import LogicalQueryPlan


class ValidationService:
    @staticmethod
    def validate_plan(db: Session, tenant_id: uuid.UUID, plan: LogicalQueryPlan) -> None:
        # Validate Metric / KPI
        if not plan.metric_ids and not plan.kpi_ids:
            raise ValueError("LogicalQueryPlan must have at least one metric or KPI.")

        for metric_id in plan.metric_ids:
            metric = db.scalar(select(SemanticMetric).where(
                SemanticMetric.id == metric_id,
                SemanticMetric.tenant_id == tenant_id
            ))
            if not metric:
                raise ValueError(f"Metric {metric_id} not found or access denied.")
                
        for kpi_id in plan.kpi_ids:
            from app.models import SemanticModel
            kpi = db.scalar(select(SemanticKPI).join(
                SemanticModel, SemanticKPI.semantic_model_id == SemanticModel.id
            ).where(
                SemanticKPI.id == kpi_id,
                SemanticModel.tenant_id == tenant_id
            ))
            if not kpi:
                raise ValueError(f"KPI {kpi_id} not found or access denied.")

        # Validate Dimensions
        for dim_id in plan.dimension_ids:
            dim = db.scalar(select(SemanticDimension).where(
                SemanticDimension.id == dim_id,
                SemanticDimension.tenant_id == tenant_id
            ))
            if not dim:
                raise ValueError(f"Dimension {dim_id} not found or access denied.")

        # In a full implementation, we would validate that there is a valid path/join
        # between the metric's source_table_id and the dimensions' source_table_id.
        pass
