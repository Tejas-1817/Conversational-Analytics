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
from app.models import Conversation, ConversationMessage, DataSource


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

        # 2. Dynamically load active schema from SchemaRegistry or active DataSource
        db_name, schema_text = self.schema_provider.get_connected_schema(
            db_session=db_session,
            user=user,
            source=active_source
        )
        if active_source and active_source.database_name:
            db_name = active_source.database_name

        # 3. Domain context & table scoping
        domain_context_str = ""
        if domain_id and db_session:
            try:
                from app.models import Domain, DomainTable, DomainTerm, TableMeta
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

        # 4. Build system prompt using loaded active schema text and optional domain context
        prompt = self.prompt_builder.build_prompt(
            question=question,
            schema_text=schema_text,
            database_name=db_name,
            domain_context=domain_context_str
        )

        # 4. Call LLM for raw PostgreSQL SQL generation
        try:
            raw_sql = self.llm_provider.generate_sql(prompt, question=question)
        except Exception as exc:
            log.error("chat_sql_generation_error", error=str(exc))
            raw_sql = "UNANSWERABLE"

        # 5. Validate SQL query safety & schema adherence
        validated_sql = self.sql_validator.validate_sql(raw_sql)

        # 6. Execute read-only SELECT query against active customer DataSource
        result_data, row_count, execution_time_ms, columns = self.sql_executor.execute_query(
            validated_sql,
            source=active_source
        )

        # 7. Synthesize plain English business executive summary
        answer = self.answer_synthesizer.synthesize_answer(question, result_data, validated_sql)

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
