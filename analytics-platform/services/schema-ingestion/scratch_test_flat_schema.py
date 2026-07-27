import sys
sys.path.insert(0, r"c:\Users\Admin\Downloads\Analytics Tool\Analytics Tool\analytics-platform\services\schema-ingestion")

from app.db import session_scope
from app.models import TableMeta
from app.semantic.enrichment_service import BusinessContextBuilder, SemanticPromptBuilder, ai_orchestrator
from app.schemas_semantic_ai import AITableDimensionsSchema, AITableMeasuresSchema, AITableMetadataSchema, AITableEnrichmentSchema

with session_scope() as session:
    # Get just one table
    tbl = session.query(TableMeta).first()
    if tbl:
        print(f"Testing flat schema generation on table: {tbl.table_name}")
        ctx = BusinessContextBuilder.build_table_context(session, tbl.id)
        
        print("\n--- 1. Testing DIMENSIONS ---")
        p_dim = SemanticPromptBuilder.build_table_enrichment_prompt(ctx, target_type="DIMENSIONS")
        res_dim = ai_orchestrator.generate_structured(prompt=p_dim, schema=AITableDimensionsSchema)
        print("Dimensions success!")
        print(res_dim.model_dump_json(indent=2))

        print("\n--- 2. Testing MEASURES ---")
        p_meas = SemanticPromptBuilder.build_table_enrichment_prompt(ctx, target_type="MEASURES")
        res_meas = ai_orchestrator.generate_structured(prompt=p_meas, schema=AITableMeasuresSchema)
        print("Measures success!")
        
        print("\n--- 3. Testing METADATA ---")
        p_meta = SemanticPromptBuilder.build_table_enrichment_prompt(ctx, target_type="METADATA")
        res_meta = ai_orchestrator.generate_structured(prompt=p_meta, schema=AITableMetadataSchema)
        print("Metadata success!")
        
        enrichment_res = AITableEnrichmentSchema(
            business_description=res_dim.business_description,
            dimensions=res_dim.dimensions,
            measures=res_meas.measures,
            kpis=res_meas.kpis,
            glossary_terms=res_meta.glossary_terms,
            relationships=res_meta.relationships,
            confidence_score=res_meta.confidence_score
        )
        print("\nFINAL MERGED SCHEMA SUCCESS!")
