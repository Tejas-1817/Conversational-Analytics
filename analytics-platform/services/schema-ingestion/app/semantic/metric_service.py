import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from app.models import SemanticMetric
from app.semantic.validation_service import ValidationService
from app.semantic.version_service import VersionService

class MetricService:
    @staticmethod
    def create_metric(db: Session, tenant_id: uuid.UUID, actor: str, **kwargs) -> SemanticMetric:
        name = kwargs.get("name")
        is_calculated = kwargs.get("is_calculated", False)
        expression = kwargs.get("expression")
        source_table_id = kwargs.get("source_table_id")
        source_column_id = kwargs.get("source_column_id")
        
        # 1. Ensure uniqueness
        existing = db.scalar(select(SemanticMetric).where(
            SemanticMetric.tenant_id == tenant_id, 
            SemanticMetric.name == name
        ))
        if existing:
            raise HTTPException(status_code=400, detail=f"Metric '{name}' already exists")
            
        # 2. Validate logic
        ValidationService.validate_metric(
            db=db, tenant_id=tenant_id, metric_name=name,
            expression=expression, is_calculated=is_calculated,
            source_table_id=source_table_id, source_column_id=source_column_id
        )
        
        # 3. Create metric
        metric = SemanticMetric(
            tenant_id=tenant_id,
            created_by=actor,
            updated_by=actor,
            version=1,
            **kwargs
        )
        db.add(metric)
        db.flush()
        
        # 4. Snapshot
        VersionService.snapshot_metric(db, metric, change_reason="Initial creation", actor=actor)
        db.commit()
        db.refresh(metric)
        return metric

    @staticmethod
    def update_metric(db: Session, tenant_id: uuid.UUID, metric_id: uuid.UUID, actor: str, **kwargs) -> SemanticMetric:
        metric = db.scalar(select(SemanticMetric).where(
            SemanticMetric.id == metric_id,
            SemanticMetric.tenant_id == tenant_id
        ))
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")
            
        name = kwargs.get("name", metric.name)
        is_calculated = kwargs.get("is_calculated", metric.is_calculated)
        expression = kwargs.get("expression", metric.expression)
        source_table_id = kwargs.get("source_table_id", metric.source_table_id)
        source_column_id = kwargs.get("source_column_id", metric.source_column_id)
        
        ValidationService.validate_metric(
            db=db, tenant_id=tenant_id, metric_name=name,
            expression=expression, is_calculated=is_calculated,
            source_table_id=source_table_id, source_column_id=source_column_id
        )
        
        # Apply updates
        for k, v in kwargs.items():
            setattr(metric, k, v)
            
        metric.version += 1
        metric.updated_by = actor
        db.flush()
        
        # Snapshot
        change_reason = kwargs.get("change_reason", "Update metric")
        VersionService.snapshot_metric(db, metric, change_reason=change_reason, actor=actor)
        db.commit()
        db.refresh(metric)
        return metric

    @staticmethod
    def get_metric(db: Session, tenant_id: uuid.UUID, metric_id: uuid.UUID) -> SemanticMetric:
        metric = db.scalar(select(SemanticMetric).where(
            SemanticMetric.id == metric_id,
            SemanticMetric.tenant_id == tenant_id
        ))
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")
        return metric
        
    @staticmethod
    def list_metrics(db: Session, tenant_id: uuid.UUID) -> List[SemanticMetric]:
        return db.scalars(select(SemanticMetric).where(SemanticMetric.tenant_id == tenant_id)).all()

    @staticmethod
    def delete_metric(db: Session, tenant_id: uuid.UUID, metric_id: uuid.UUID, actor: str):
        metric = db.scalar(select(SemanticMetric).where(
            SemanticMetric.id == metric_id,
            SemanticMetric.tenant_id == tenant_id
        ))
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")
        # Snapshot before deletion for audit purposes
        VersionService.snapshot_metric(db, metric, change_reason="Deleted", actor=actor)
        db.delete(metric)
        db.commit()
        return True

    @staticmethod
    def get_versions(db: Session, tenant_id: uuid.UUID, metric_id: uuid.UUID):
        # We need to query MetricVersion. We didn't import it, so let's import it locally to avoid circular dep
        from app.models import MetricVersion
        versions = db.scalars(select(MetricVersion).where(
            MetricVersion.metric_id == metric_id
        ).order_by(MetricVersion.version.desc())).all()
        return versions

    @staticmethod
    def rollback_metric(db: Session, tenant_id: uuid.UUID, metric_id: uuid.UUID, target_version: int, actor: str) -> SemanticMetric:
        metric = db.scalar(select(SemanticMetric).where(
            SemanticMetric.id == metric_id,
            SemanticMetric.tenant_id == tenant_id
        ))
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")
            
        from app.models import MetricVersion
        version_record = db.scalar(select(MetricVersion).where(
            MetricVersion.metric_id == metric_id,
            MetricVersion.version == target_version
        ))
        if not version_record:
            raise HTTPException(status_code=404, detail="Target version not found")
            
        snapshot = version_record.snapshot
        
        metric.name = snapshot.get("name", metric.name)
        metric.business_name = snapshot.get("business_name", metric.business_name)
        metric.description = snapshot.get("description", metric.description)
        metric.is_calculated = snapshot.get("is_calculated", metric.is_calculated)
        metric.expression = snapshot.get("expression", metric.expression)
        metric.aggregation_type = snapshot.get("aggregation_type", metric.aggregation_type)
        metric.source_table_id = snapshot.get("source_table_id", metric.source_table_id)
        metric.source_column_id = snapshot.get("source_column_id", metric.source_column_id)
        
        # Validation after restore
        ValidationService.validate_metric(
            db=db, tenant_id=tenant_id, metric_name=metric.name,
            expression=metric.expression, is_calculated=metric.is_calculated,
            source_table_id=metric.source_table_id, source_column_id=metric.source_column_id
        )
        
        metric.version += 1
        metric.updated_by = actor
        db.flush()
        
        VersionService.snapshot_metric(db, metric, change_reason=f"Rollback to v{target_version}", actor=actor)
        db.commit()
        db.refresh(metric)
        return metric
