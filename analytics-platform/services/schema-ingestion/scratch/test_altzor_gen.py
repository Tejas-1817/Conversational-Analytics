import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import session_scope
from app.models import Tenant, DataSource, TableMeta, SemanticMetric, SemanticDimension, SemanticModel, MetadataVersion
from app.semantic.generation_service import SemanticGenerationService

with session_scope() as db:
    source = db.query(DataSource).first()
    if not source:
        print("No DataSource found in database!")
        sys.exit(1)
        
    tenant_id = source.tenant_id
    print(f"Testing for DataSource '{source.name}' with tenant_id '{tenant_id}'")
        
    tables = db.query(TableMeta).filter_by(source_id=source.id).all()
    print(f"Found {len(tables)} tables for DataSource '{source.name}'")
    
    meta = db.query(MetadataVersion).filter_by(source_id=source.id).order_by(MetadataVersion.version_number.desc()).first()
    if not meta:
        meta = MetadataVersion(source_id=source.id, version_number=1, sync_status="succeeded")
        db.add(meta)
        db.commit()

    model = db.query(SemanticModel).filter_by(tenant_id=tenant_id, source_id=source.id).first()
    if not model:
        model = SemanticModel(
            tenant_id=tenant_id,
            source_id=source.id,
            metadata_version_id=meta.id,
            semantic_version=1,
            generated_by_model="test-script",
            generation_status="ACTIVE"
        )
        db.add(model)
        db.commit()

    # Clear previous metrics/dimensions to test clean generation
    db.query(SemanticMetric).filter_by(tenant_id=tenant_id).delete()
    db.query(SemanticDimension).filter_by(tenant_id=tenant_id).delete()
    db.commit()

    print("Running SemanticGenerationService.generate_for_tables...")
    res = SemanticGenerationService.generate_for_tables(
        db=db,
        tables=tables[:1], # test 1 table
        tenant_id=tenant_id,
        semantic_model_id=model.id,
        max_workers=3
    )
    print("Generation complete result:", res)
    
    metrics = db.query(SemanticMetric).filter_by(tenant_id=tenant_id).all()
    dims = db.query(SemanticDimension).filter_by(tenant_id=tenant_id).all()
    
    print(f"\n--- VERIFICATION ---")
    print(f"Created {len(metrics)} SemanticMetrics:")
    for m in metrics:
        print(f"  - Metric: {m.name} | Formula: {m.formula} | Table: {m.table_name}")
        
    print(f"Created {len(dims)} SemanticDimensions:")
    for d in dims:
        print(f"  - Dimension: {d.name} | Column: {d.column_name} | Type: {d.type}")
