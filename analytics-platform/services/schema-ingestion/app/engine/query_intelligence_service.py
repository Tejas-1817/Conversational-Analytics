import uuid
import structlog
import json
from sqlalchemy.orm import Session

from app.engine.retrieval_service import RetrievalService, RetrievalHits
from app.engine.compiler_service import CompilerService, CompiledQuery, SQLSafetyError
from app.engine.executor_service import ExecutorService
from app.schemas_engine import QueryIntelligenceOutput
from app.llm.orchestrator import ai_orchestrator

logger = structlog.get_logger(__name__)

class QueryIntelligenceService:
    @staticmethod
    def answer_question(db: Session, tenant_id: uuid.UUID, question: str) -> dict:
        logger.info("query_intelligence_started", tenant_id=str(tenant_id), question=question)
        
        # 1. Retrieve
        hits: RetrievalHits = RetrievalService.retrieve(question, tenant_id, db)
        
        # 2. Build Context
        context_data = {
            "metrics": [{"name": m.name, "business_name": m.business_name, "formula": m.expression} for m, _ in hits.metrics],
            "dimensions": [{"business_name": d.business_name, "column": d.source_column_id} for d, _ in hits.dimensions],
            "tables": [{"name": t.table_name, "schema": t.schema_name, "id": str(t.id)} for t, _ in hits.tables],
            "glossary": [{"term": g.term, "definition": g.definition} for g, _ in hits.glossary]
        }
        
        if not hits.metrics and not hits.dimensions and not hits.tables:
            logger.warning("query_intelligence_no_context", tenant_id=str(tenant_id))
            return {
                "sql": None,
                "explanation": "I don't have enough semantic context to answer that accurately.",
                "referenced_semantics": [],
                "confidence": 0.0,
                "execution_metadata": None
            }
            
        context_json = json.dumps(context_data, indent=2, default=str)
        
        # 3. Prompt LLM
        prompt = f"""
You are an expert Data Analyst and PostgreSQL SQL generator.
Your task is to generate an executable SQL query to answer the user's question, strictly using the provided Semantic Context.

USER QUESTION: {question}

--- SEMANTIC CONTEXT ---
{context_json}
------------------------

CRITICAL INSTRUCTIONS:
1. ONLY use tables, metrics, and dimensions provided in the context. Do NOT hallucinate tables or columns.
2. If there is a semantic metric for the requested data, USE ITS FORMULA. Do not invent your own formula.
3. If the context is completely insufficient to answer the question, set 'sql' to null.
4. IMPORTANT: You MUST include a tenant_id filter in every WHERE clause using the exact string parameter: `:tenant_id`
   Example: `WHERE table_name.tenant_id = :tenant_id`
5. Do NOT include any destructive keywords (INSERT, UPDATE, DELETE, DROP, ALTER). Only SELECT.
"""
        
        try:
            result: QueryIntelligenceOutput = ai_orchestrator.generate_structured(prompt, QueryIntelligenceOutput)
        except Exception as e:
            logger.error("query_intelligence_llm_error", error=str(e))
            return {
                "sql": None,
                "explanation": "Failed to generate SQL due to an internal error.",
                "referenced_semantics": [],
                "confidence": 0.0,
                "execution_metadata": None
            }

        if not result.sql:
            return {
                "sql": None,
                "explanation": result.explanation,
                "referenced_semantics": result.referenced_semantics,
                "confidence": result.confidence,
                "execution_metadata": None
            }
            
        # 4. Validate SQL
        try:
            CompilerService.validate_safety(result.sql)
        except SQLSafetyError as e:
            logger.warning("query_intelligence_unsafe_sql", error=str(e), sql=result.sql)
            return {
                "sql": None,
                "explanation": f"The generated SQL was rejected for safety reasons: {str(e)}",
                "referenced_semantics": result.referenced_semantics,
                "confidence": result.confidence,
                "execution_metadata": None
            }
            
        # 5. Execute
        compiled = CompiledQuery(sql=result.sql, params={"tenant_id": str(tenant_id)})
        try:
            exec_result = ExecutorService.execute(db, compiled)
            exec_metadata = {
                "execution_time_ms": exec_result.execution_time_ms,
                "columns": exec_result.columns,
                "rows": exec_result.rows
            }
        except Exception as e:
            logger.error("query_intelligence_exec_error", error=str(e), sql=result.sql)
            return {
                "sql": result.sql,
                "explanation": result.explanation + f"\n\nHowever, execution failed: {str(e)}",
                "referenced_semantics": result.referenced_semantics,
                "confidence": result.confidence,
                "execution_metadata": None
            }
            
        # 6. Return
        return {
            "sql": result.sql,
            "explanation": result.explanation,
            "referenced_semantics": result.referenced_semantics,
            "confidence": result.confidence,
            "execution_metadata": exec_metadata
        }
