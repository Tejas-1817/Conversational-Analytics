import uuid
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = structlog.get_logger(__name__)

class SemanticGraphValidator:
    """
    Validates a SemanticModel before it is activated to prevent runtime errors and broken queries.
    """
    
    @staticmethod
    def validate(db: Session, semantic_model_id: uuid.UUID) -> bool:
        logger.info("validating_semantic_graph", semantic_model_id=str(semantic_model_id))
        
        try:
            # 1. Referential Integrity (Joins)
            res = db.execute(text("""
                SELECT sj.id
                FROM semantic_joins sj
                LEFT JOIN columns_meta lc ON sj.left_column_id = lc.id
                LEFT JOIN columns_meta rc ON sj.right_column_id = rc.id
                WHERE sj.semantic_model_id = :model_id
                  AND (lc.id IS NULL OR rc.id IS NULL)
            """), {"model_id": str(semantic_model_id)}).fetchall()
            
            if res:
                logger.error("validation_failed_broken_joins", count=len(res))
                return False
                
            # 2. Orphan Check: Check if a SemanticDimension points to a missing column
            res = db.execute(text("""
                SELECT sd.id
                FROM semantic_dimensions sd
                LEFT JOIN columns_meta c ON sd.source_column_id = c.id
                WHERE sd.semantic_model_id = :model_id
                  AND sd.source_column_id IS NOT NULL
                  AND c.id IS NULL
            """), {"model_id": str(semantic_model_id)}).fetchall()
            
            if res:
                logger.error("validation_failed_orphan_dimensions", count=len(res))
                return False
                
            # 3. Orphan Check: Check if a SemanticMetric points to a missing column
            res = db.execute(text("""
                SELECT sm.id
                FROM semantic_metrics sm
                LEFT JOIN columns_meta c ON sm.source_column_id = c.id
                WHERE sm.semantic_model_id = :model_id
                  AND sm.is_calculated = false
                  AND sm.source_column_id IS NOT NULL
                  AND c.id IS NULL
            """), {"model_id": str(semantic_model_id)}).fetchall()
            
            if res:
                logger.error("validation_failed_orphan_metrics", count=len(res))
                return False

            return True
            
        except Exception as e:
            logger.error("semantic_validation_exception", error=str(e))
            return False
