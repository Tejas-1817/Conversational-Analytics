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
