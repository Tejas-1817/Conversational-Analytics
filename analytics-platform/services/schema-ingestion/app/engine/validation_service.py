import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import SemanticMetric, SemanticDimension
from app.schemas_engine import StructuredQueryPlan

class ValidationService:
    @staticmethod
    def validate_plan(db: Session, tenant_id: uuid.UUID, plan: StructuredQueryPlan) -> None:
        # Validate Metric
        metric = db.scalar(select(SemanticMetric).where(
            SemanticMetric.id == plan.metric_id,
            SemanticMetric.tenant_id == tenant_id
        ))
        if not metric:
            raise ValueError(f"Metric {plan.metric_id} not found or access denied.")
            
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
