"""Chat Service.

Orchestrates SchemaProvider, PromptBuilder, LLMProvider, and SQLValidator
to handle Text-to-SQL requests.
"""
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from app.chat_sql.answer_synthesizer import AnswerSynthesizer
from app.chat_sql.llm_provider import LLMProvider
from app.chat_sql.prompt_builder import PromptBuilder
from app.chat_sql.schema_provider import SchemaProvider
from app.chat_sql.sql_executor import SQLExecutor
from app.chat_sql.sql_validator import SQLValidator

log = structlog.get_logger(__name__)


import uuid
from app.models import (Conversation, ConversationMessage, DataSource, TableMeta)


class ChatService:
    """Text-to-SQL & Analytics Chat Service."""

    def __init__(self):
        self.schema_provider = SchemaProvider()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = LLMProvider()
        self.sql_validator = SQLValidator()
        self.sql_executor = SQLExecutor()
        self.answer_synthesizer = AnswerSynthesizer()

    def process_text_to_sql(
        self,
        question: str,
        conversation_id: str | None = None,
        domain_id: str | None = None,
        db_session: Any | None = None,
        user: Any | None = None,
    ) -> Dict[str, Any]:
        """Loads connected database schema, prompts LLM, executes SQL, synthesizes answer, persists messages, and returns DTO."""
        # 1. Dynamically resolve caller's active connected customer DataSource
        active_source = None
        if db_session and user and hasattr(user, "tenant_id"):
            try:
                active_source = db_session.query(DataSource).filter_by(
                    tenant_id=user.tenant_id,
                    status="connected"
                ).first()
            except Exception as exc:
                log.warning("failed_to_resolve_active_datasource", error=str(exc))

        if active_source is None:
            raise RuntimeError(
                "No connected customer data source was found for this tenant."
            )

        # 2. Stage 1: Vector DB Semantic Routing (Retrieve Top Relevant Table Schemas)
        db_name, full_schema_text = self.schema_provider.get_connected_schema(
            db_session=db_session,
            user=user,
            source=active_source
        )
        if active_source and active_source.database_name:
            db_name = active_source.database_name

        relevant_schema_text = ""
        if user and hasattr(user, "tenant_id"):
            try:
                from app.embeddings.chroma_store import ChromaStore
                from app.embeddings.registry import get_embedding_provider

                query_vector = get_embedding_provider().embed([question])[0]
                hits = ChromaStore().query(
                    tenant_id=user.tenant_id,
                    query_embedding=query_vector,
                    n_results=7,
                    source_id=active_source.id if active_source else None
                )
                if hits:
                    # Filter out FK-only/relationship chunks — they contain no column definitions
                    # A valid table chunk must contain the "TABLE:" keyword
                    table_hits = [
                        hit for hit in hits
                        if "TABLE:" in hit.text or "-- TABLE:" in hit.text
                    ]
                    # Safety fallback: if filtering removed everything, use all hits
                    valid_hits = table_hits if table_hits else hits

                    relevant_schema_text = "\n\n".join(hit.text for hit in valid_hits)
                    table_labels = [
                        hit.metadata.get("label", "").replace("TABLE: ", "").strip()
                        for hit in valid_hits
                        if hit.metadata.get("label")
                    ]
                    log.info(
                        "stage_1_vector_db_relevant_tables_found",
                        chunks=len(valid_hits),
                        fk_chunks_filtered=len(hits) - len(valid_hits),
                        relevant_tables=table_labels,
                        schema_chars=len(relevant_schema_text)
                    )
            except Exception as exc:
                log.warning("stage_1_vector_search_fallback", error=str(exc))

        # Fallback: if vector search returned empty or was unavailable, use full schema text
        schema_text = relevant_schema_text if relevant_schema_text else full_schema_text

        source_tables = (
            db_session.query(TableMeta)
            .filter(
                TableMeta.source_id == active_source.id,
                TableMeta.is_active.is_(True),
            )
            .all()
        )

        catalog = {}
        for table in source_tables:
            columns = {
                column.column_name
                for column in table.columns
                if column.is_active
            }
            catalog[table.table_name] = columns
            catalog[f"{table.schema_name}.{table.table_name}"] = columns

        # 3. Domain context & table scoping
        domain_context_str = ""
        if domain_id and db_session:
            try:
                from app.models import Domain, DomainTable, DomainTerm
                dom_uuid = uuid.UUID(str(domain_id))
                domain = db_session.query(Domain).filter(Domain.id == dom_uuid).first()
                if domain:
                    # Fetch domain terms
                    terms = db_session.query(DomainTerm).filter(DomainTerm.domain_id == dom_uuid).limit(10).all()
                    terms_str = "\n".join(f"- {t.term}: {t.definition}" for t in terms)

                    # Fetch domain selected tables
                    dom_tables = db_session.query(DomainTable).filter(DomainTable.domain_id == dom_uuid).all()
                    table_names = []
                    for dt in dom_tables:
                        tm = db_session.query(TableMeta).filter(TableMeta.id == dt.table_id).first()
                        if tm:
                            table_names.append(tm.table_name)

                    domain_context_str = f"Domain Name: {domain.name}\nDescription: {domain.description or 'None'}\nScoped Domain Tables: {', '.join(table_names) if table_names else 'All'}\nBusiness Terms & Definitions:\n{terms_str if terms_str else 'None'}"
            except Exception as exc:
                log.warning("failed_to_load_domain_context", error=str(exc))


        # 4. Route broad overview, strategy, and schema-gap questions
        # directly to grounded text analysis instead of Text-to-SQL.
        q_lower = " ".join(question.lower().split())

        direct_analysis_phrases = (
            "what kind of analytics",
            "what analytics",
            "what can we build",
            "explain database",
            "explain the database",
            "what tables",
            "overview of database",
            "overview of the database",
            "what data do we have",
            "business advice",
            "business opportunity",
            "business opportunities",
            "identify opportunities",
            "growth opportunities",
            "business strategy",
            "business strategies",
            "how do i improve business",
            "how can i improve business",
            "what is missing in the data",
            "what data is missing",
            "data gaps",
            "schema gaps",
        )

        is_direct_analysis = any(
            phrase in q_lower
            for phrase in direct_analysis_phrases
        )

        if is_direct_analysis:
            # Include all connected tables in a compact format.
            # Broad questions should not rely on only the top Chroma matches.
            schema_inventory = "\n".join(
                (
                    f"- {table.schema_name}.{table.table_name}: "
                    + ", ".join(
                        column.column_name
                        for column in table.columns
                        if column.is_active
                    )
                )
                for table in source_tables
            )

            analysis_prompt = f"""
You are a careful business data analyst.

Answer the user's broad analytical question using only the connected
database schema inventory below.

Rules:
- Do not generate SQL.
- Do not invent database values, performance results, trends, causes,
  forecasts, or missing-value counts.
- Clearly distinguish facts visible in the schema from suggested analyses.
- For business-opportunity questions, describe potential opportunities as
  hypotheses that should be verified with data.
- For missing-data questions, identify possible schema or coverage gaps only.
- State that row-level profiling is required to confirm NULL values,
  incomplete records, or data-quality problems.
- Use concise Markdown paragraphs and bullet points.
- Mention the relevant physical tables and columns supporting each suggestion.

DATABASE:
{db_name}

SCHEMA INVENTORY:
{schema_inventory}

USER QUESTION:
{question}
""".strip()

            direct_answer = self.llm_provider.generate_text(
                prompt=analysis_prompt,
                max_tokens=384,
                timeout=300
            )

            generated_at = datetime.now(timezone.utc).isoformat()

            return {
                "success": True,
                "conversation_id": conversation_id,
                "question": question,
                "summary": direct_answer,
                "answer": direct_answer,
                "sql": "-- No SQL required for this broad analysis question",
                "result_data": [],
                "rows": [],
                "columns": [],
                "row_count": 0,
                "column_count": 0,
                "visualization": "text",
                "title": "Business and Data Analysis",
                "profile": None,
                "statistics": {
                    "row_count": 0,
                    "column_count": 0,
                    "execution_time_ms": 0,
                },
                "recommended_visualization": {
                    "visualization": "text",
                    "title": "Business and Data Analysis",
                },
                "execution_time_ms": 0,
                "generated_at": generated_at,
                "database": db_name,
                "column_types": {},
            }

        # 4b. Build a SQL prompt only when the question requires SQL.
        prompt = self.prompt_builder.build_prompt(
            question=question,
            schema_text=schema_text,
            database_name=db_name,
            domain_context=domain_context_str,
        )
        # 4b. Generate the initial SQL draft
        try:
            raw_sql = self.llm_provider.generate_sql(
                prompt=prompt,
                question=question,
            )
        except Exception as exc:
            log.error(
                "chat_sql_generation_error",
                error=str(exc),
            )
            raise RuntimeError(
                f"Ollama SQL generation failed: {exc}"
            ) from exc

        # 5. Deterministic validation of the generated draft
        draft_sql = self.sql_validator.validate_sql(
            raw_sql,
            catalog=catalog,
        )

        if draft_sql == "UNANSWERABLE":
            validated_sql = "UNANSWERABLE"
        else:
            # 5b. Second Ollama pass for semantic review/correction
            reviewed_sql = self.llm_provider.review_sql(
                question=question,
                candidate_sql=draft_sql,
                schema_text=schema_text,
                domain_context=domain_context_str,
            )

            # 5c. Never trust the reviewed output without validating it again
            validated_sql = self.sql_validator.validate_sql(
                reviewed_sql,
                catalog=catalog,
            )

        # Return a controlled response instead of sending UNANSWERABLE to the database executor.
        if validated_sql == "UNANSWERABLE":
            generated_at = datetime.now(timezone.utc).isoformat()

            return {
                "success": False,
                "conversation_id": conversation_id,
                "question": question,
                "summary": (
                    "This question cannot be answered reliably using the "
                    "connected database schema."
                ),
                "answer": (
                    "This question cannot be answered reliably using the "
                    "connected database schema."
                ),
                "sql": "UNANSWERABLE",
                "result_data": [],
                "rows": [],
                "columns": [],
                "row_count": 0,
                "column_count": 0,
                "visualization": "text",
                "title": "Question cannot be answered",
                "profile": None,
                "statistics": {
                    "row_count": 0,
                    "column_count": 0,
                    "execution_time_ms": 0,
                },
                "recommended_visualization": {
                    "visualization": "text",
                    "title": "Question cannot be answered",
                },
                "execution_time_ms": 0,
                "generated_at": generated_at,
                "database": db_name,
                "column_types": {},
            }

        # 6. Execute reviewed and validated SQL
        (result_data,
            row_count,
            execution_time_ms,
            columns,
            execution_error,
        ) = self.sql_executor.execute_query(
            validated_sql,
            source=active_source,
        )
        
        # 6b. One error-driven Ollama correction attempt
        if execution_error:
            log.warning(
                "sql_execution_failed_triggering_refinement",
                failed_sql=validated_sql,
                error=execution_error,
            ) 

            refined_raw_sql = self.llm_provider.refine_sql(
                question=question,
                failed_sql=validated_sql,
                error_message=execution_error,
                schema_text=schema_text,
            )
            refined_sql = self.sql_validator.validate_sql(
                refined_raw_sql,
                catalog=catalog,
            )
            if refined_sql == "UNANSWERABLE":
                raise RuntimeError(
                    "The SQL could not be corrected from the available schema. "
                    f"Original database error: {execution_error}"
                ) 
        
            (
                retry_data,
                retry_row_count,
                retry_time_ms,
                retry_columns,
                retry_error,
            ) = self.sql_executor.execute_query(
                refined_sql,
                source=active_source,
            )

            execution_time_ms += retry_time_ms

            if retry_error:
                raise RuntimeError(
                    "SQL execution failed after one correction attempt. "
                    f"Database error: {retry_error}"
                )
            validated_sql = refined_sql
            result_data = retry_data
            row_count = retry_row_count
            columns = retry_columns

            log.info(
                "refined_sql_execution_succeeded",
                refined_sql=validated_sql,
                row_count=row_count,
            )

        # 7. Synthesize an answer from verified query results
        answer = self.answer_synthesizer.synthesize_answer(
            question=question,
            result_data=result_data,
            sql=validated_sql,
            domain_context=domain_context_str,
        )

        # 8. Recommend Visualization Type (KPI Card, Detail Card, Bar/Line/Pie Chart, Table)
        from app.engine.chart_recommender import ChartRecommender
        vis_payload = ChartRecommender.recommend_visualization(
            rows=result_data,
            columns=columns,
            question=question,
            sql=validated_sql
        )
        vis_type = vis_payload.get("visualization", "table")
        title = vis_payload.get("title", question[:40] if question else "Query Results")

        format_date = lambda d: d.strftime("%d %b %Y, %I:%M %p")
        generated_at = format_date(datetime.now(timezone.utc))

        log.info(
            "chat_sql_processed",
            database=db_name,
            question=question[:50],
            row_count=row_count,
            column_count=len(columns),
            vis_type=vis_type,
            title=title,
            execution_time_ms=execution_time_ms
        )

        # 9. Persist Conversation & Messages to PostgreSQL if session and user provided
        res_conv_id = conversation_id
        if db_session and user:
            try:
                conv = None
                if conversation_id:
                    try:
                        conv_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
                        conv = db_session.query(Conversation).filter(
                            Conversation.id == conv_uuid,
                            Conversation.tenant_id == user.tenant_id
                        ).first()
                    except Exception:
                        pass

                if not conv:
                    conv = Conversation(
                        tenant_id=user.tenant_id,
                        user_id=user.id,
                        title=title
                    )
                    db_session.add(conv)
                    db_session.flush()
                elif not conv.title or conv.title == "New Conversation":
                    conv.title = title

                res_conv_id = str(conv.id)

                # Store user question message
                user_msg = ConversationMessage(
                    conversation_id=conv.id,
                    role="user",
                    content=question,
                    status="complete"
                )
                db_session.add(user_msg)

                # Store assistant answer message
                asst_msg = ConversationMessage(
                    conversation_id=conv.id,
                    role="assistant",
                    content=answer,
                    generated_sql=validated_sql,
                    result_data={"rows": result_data, "columns": columns, "row_count": row_count, "visualization": vis_type, "title": title, "column_types": vis_payload.get("profile", {}).get("column_types", {})},
                    chart_recommendation=vis_type,
                    execution_time_ms=int(execution_time_ms),
                    status="complete"
                )
                db_session.add(asst_msg)
                db_session.commit()
            except Exception as exc:
                log.warning("failed_to_persist_chat_messages", error=str(exc))
                try:
                    db_session.rollback()
                except Exception:
                    pass

        return {
            "success": True,
            "conversation_id": res_conv_id,
            "question": question,
            "summary": answer,
            "answer": answer,
            "sql": validated_sql,
            "result_data": result_data,
            "rows": result_data,
            "columns": columns,
            "row_count": row_count,
            "column_count": len(columns),
            "visualization": vis_type,
            "title": title,
            "profile": vis_payload.get("profile"),
            "statistics": {"row_count": row_count, "column_count": len(columns), "execution_time_ms": execution_time_ms},
            "recommended_visualization": vis_payload,
            "execution_time_ms": execution_time_ms,
            "generated_at": generated_at,
            "database": db_name,
            "column_types": vis_payload.get("profile", {}).get("column_types", {}),
        }
