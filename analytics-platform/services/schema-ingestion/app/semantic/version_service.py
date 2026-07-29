import uuid

from sqlalchemy.orm import Session

from app.models import DimensionVersion, JoinVersion, MetricVersion, SemanticDimension, SemanticJoin, SemanticMetric


class VersionService:
    """Creates JSON snapshots of semantic objects for version history."""

    @staticmethod
    def _model_to_dict(instance) -> dict:
        """Serialize a SQLAlchemy model instance to a dict."""
        data = {}
        for column in instance.__table__.columns:
            val = getattr(instance, column.name)
            if isinstance(val, uuid.UUID):
                data[column.name] = str(val)
            elif hasattr(val, "isoformat"):
                data[column.name] = val.isoformat()
            else:
                data[column.name] = val
        return data

    @classmethod
    def snapshot_metric(cls, db: Session, metric: SemanticMetric, change_reason: str, actor: str):
        snapshot_data = cls._model_to_dict(metric)
        version_record = MetricVersion(
            metric_id=metric.id,
            version=metric.version,
            snapshot=snapshot_data,
            change_reason=change_reason,
            created_by=actor
        )
        db.add(version_record)

    @classmethod
    def snapshot_dimension(cls, db: Session, dimension: SemanticDimension, change_reason: str, actor: str):
        snapshot_data = cls._model_to_dict(dimension)
        version_record = DimensionVersion(
            dimension_id=dimension.id,
            version=dimension.version,
            snapshot=snapshot_data,
            change_reason=change_reason,
            created_by=actor
        )
        db.add(version_record)

    @classmethod
    def snapshot_join(cls, db: Session, join: SemanticJoin, change_reason: str, actor: str):
        snapshot_data = cls._model_to_dict(join)
        version_record = JoinVersion(
            join_id=join.id,
            version=join.version,
            snapshot=snapshot_data,
            change_reason=change_reason,
            created_by=actor
        )
        db.add(version_record)

    @staticmethod
    def rollback_semantic_model(db: Session, tenant_id: uuid.UUID, source_id: uuid.UUID, target_version: int, actor: str):
        import structlog
        from fastapi import HTTPException
        from app.models import SemanticModel
        from app.semantic.version_manager import SemanticVersionManager
        from app.semantic.audit_service import AuditService
        
        logger = structlog.get_logger(__name__)
        logger.info("rollback_semantic_model_requested", source_id=str(source_id), target_version=target_version)
        
        target_model = db.query(SemanticModel).filter(
            SemanticModel.source_id == source_id,
            SemanticModel.semantic_version == target_version
        ).first()
        
        if not target_model:
            raise HTTPException(status_code=404, detail=f"Version {target_version} not found for source {source_id}")
            
        current_active = db.query(SemanticModel).filter(
            SemanticModel.source_id == source_id,
            SemanticModel.is_active == True
        ).first()
        
        if current_active and current_active.semantic_version == target_version:
            raise HTTPException(status_code=400, detail="Target version is already active")
            
        # Promote target model
        SemanticVersionManager.promote_version(db, source_id, target_model.id)
        
        # Log Audit
        AuditService.log_action(
            db=db,
            tenant_id=tenant_id,
            entity_type="semantic_model",
            entity_id=target_model.id,
            action="ROLLBACK",
            actor=actor,
            reason=f"Rolled back to version {target_version}",
            before_state={"active_version": current_active.semantic_version if current_active else None},
            after_state={"active_version": target_version}
        )
        
        return target_model
