"""Chat Service.

Orchestrates SchemaProvider, PromptBuilder, LLMProvider, and SQLValidator
to handle Text-to-SQL requests.
"""
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from app.chat_sql.chat_recommender import ChatRecommender
from app.config import get_settings
from app.engine.retrieval_service import RetrievalService
from app.chat_sql.answer_synthesizer import AnswerSynthesizer
from app.chat_sql.llm_provider import (
    LLMProvider,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.chat_sql.prompt_builder import PromptBuilder
from app.chat_sql.schema_provider import SchemaProvider
from app.chat_sql.sql_executor import SQLExecutor
from app.chat_sql.sql_validator import SQLValidator

log = structlog.get_logger(__name__)
# MAX_FULL_SCHEMA_CHARS = 18_000

from app.models import (Conversation, 
    ConversationMessage, 
    DataSource, 
    TableMeta, 
    ColumnMeta,
    Domain,
    DomainTable,
    DomainTerm,
)

def _build_table_schema_block(table: TableMeta) -> str:
    """Build compact SQL-generation context for one physical table."""

    lines = [
        f"TABLE: {table.schema_name}.{table.table_name}",
    ]

    if table.business_name:
        lines.append(f"Business name: {table.business_name}")

    if table.description:
        lines.append(f"Description: {table.description}")

    lines.append("COLUMNS:")

    active_columns = sorted(
        (
            column
            for column in table.columns
            if column.is_active
        ),
        key=lambda column: column.ordinal_position or 0,
    )

    for column in active_columns:
        flags: list[str] = []

        if column.is_primary_key:
            flags.append("PRIMARY KEY")

        if not column.is_nullable:
            flags.append("NOT NULL")

        suffix = f" [{', '.join(flags)}]" if flags else ""

        lines.append(
            f"- {column.column_name} ({column.data_type}){suffix}"
        )

    return "\n".join(lines)

ResolvedIntent = Literal["data", "strategy", "hybrid"]
RequestMode = Literal["auto", "data", "strategy", "hybrid"]


class SourceNotFoundError(RuntimeError):
    """Raised when the requested source is unavailable to the current tenant."""


@dataclass(frozen=True, slots=True)
class IntentDecision:
    intent: ResolvedIntent
    reason: str


class IntentRouter:
    STRATEGY_TERMS = (
        "improve",
        "strategy",
        "strategies",
        "recommend",
        "recommendation",
        "opportunity",
        "opportunities",
        "risk",
        "risks",
        "grow",
        "growth",
        "increase",
        "reduce",
        "optimize",
        "business advice",
        "what should we do",
        "unusual",
        "anomaly",
        "anomalies",
        "suspicious",
        "what might",
        "indicate",
        "investigate",
    )

    DATA_TERMS = (
        "revenue",
        "sales",
        "profit",
        "margin",
        "cost",
        "orders",
        "customers",
        "products",
        "inventory",
        "returns",
        "conversion",
        "price",
        "performance",
        "trend",
        "monthly",
        "quarterly",
        "yearly",
        "customer",
        "transaction",
        "transactions",
        "payment",
        "fraud",
    )

    @classmethod
    def classify(
        cls,
        question: str,
        requested_mode: RequestMode = "auto",
    ) -> IntentDecision:
        if requested_mode != "auto":
            return IntentDecision(
                intent=requested_mode,
                reason="The caller explicitly selected the processing mode.",
            )

        normalized = " ".join(question.lower().split())

        has_strategy = any(
            re.search(rf"\b{re.escape(term)}\b", normalized)
            for term in cls.STRATEGY_TERMS
        )
        has_data = any(
            re.search(rf"\b{re.escape(term)}\b", normalized)
            for term in cls.DATA_TERMS
        )

        if has_strategy and has_data:
            return IntentDecision(
                intent="hybrid",
                reason="The question requests advice based on measurable data.",
            )

        if has_strategy:
            return IntentDecision(
                intent="strategy",
                reason="The question requests general strategic guidance.",
            )

        return IntentDecision(
            intent="data",
            reason="The question requests a factual database result.",
        )


class ChatService:
    """Text-to-SQL & Analytics Chat Service."""

    def __init__(self):
        self.schema_provider = SchemaProvider()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = LLMProvider()
        self.sql_validator = SQLValidator()
        self.sql_executor = SQLExecutor()
        self.answer_synthesizer = AnswerSynthesizer()

    def _persist_exchange(
        self,
        *,
        db_session: Any,
        user: Any,
        conversation_id: uuid.UUID | str | None,
        question: str,
        answer: str,
        title: str,
        intent: str,
        sql: str | None = None,
        rows: list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
        column_types: dict[str, Any] | None = None,
        visualization: str = "text",
        follow_up_questions: list[str] | None = None,
        row_count: int | None = None,
        data_truncated: bool = False,
        execution_time_ms: float = 0.0,
    ) -> str:
        """Persist one complete user/assistant exchange."""

        saved_rows = rows or []
        saved_columns = columns or []
        saved_column_types = column_types or {}
        saved_follow_ups = follow_up_questions or []
        saved_row_count = (
            row_count
            if row_count is not None
            else len(saved_rows)
        )

        try:
            conversation = None

            if conversation_id:
                try:
                    parsed_conversation_id = uuid.UUID(
                        str(conversation_id)
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "Invalid conversation ID."
                    ) from exc

                conversation = (
                    db_session.query(Conversation)
                    .filter(
                        Conversation.id == parsed_conversation_id,
                        Conversation.tenant_id == user.tenant_id,
                        Conversation.user_id == user.id,
                    )
                    .one_or_none()
                )

                if conversation is None:
                    raise ValueError(
                        "Conversation was not found."
                    )

            else:
                conversation = Conversation(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    title=title,
                )
                db_session.add(conversation)
                db_session.flush()

            if (
                not conversation.title
                or conversation.title == "New Conversation"
            ):
                conversation.title = title

            conversation.updated_at = datetime.now(timezone.utc)

            user_message = ConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content=question,
                route=intent,
                intent={"type": intent},
                status="complete",
            )

            assistant_message = ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                route=intent,
                intent={"type": intent},
                generated_sql=sql,
                 result_data={
                    "rows": saved_rows,
                    "columns": saved_columns,
                    "row_count": saved_row_count,
                    "column_types": saved_column_types,
                    "visualization": visualization,
                    "data_truncated": data_truncated,
                    "follow_up_questions": saved_follow_ups,
                    "title": title,
                    "intent": intent,
                },
                chart_recommendation=visualization,
                execution_time_ms=int(execution_time_ms),
                status="complete",
            )
            db_session.add(user_message)
            db_session.add(assistant_message)
            db_session.commit()

            return str(conversation.id)

        except Exception as exc:
            log.warning("failed_to_persist_exchange", error=str(exc))
            try:
                db_session.rollback()
            except Exception:
                pass
            return str(conversation_id) if conversation_id else ""


    def process_text_to_sql(
        self,
        question: str,
        source_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
        domain_id: uuid.UUID | None = None,
        requested_mode: RequestMode = "auto",
        db_session: Any | None = None,
        user: Any | None = None,    
    ) -> dict[str, Any]:
        """Loads connected database schema, prompts LLM, executes SQL, synthesizes answer, persists messages, and returns DTO."""
        # 1. Validate request context and resolve the selected source
        if db_session is None or user is None:
            raise ValueError(
                "Database session and authenticated user are required."
            )

        active_source = (
            db_session.query(DataSource)
            .filter(
                DataSource.id == source_id,
                DataSource.tenant_id == user.tenant_id,
                DataSource.status == "connected",
            )
            .one_or_none()
        )

        if active_source is None:
            raise SourceNotFoundError(
                "The selected connected data source was not found."
            )

        decision = IntentRouter.classify(
            question=question,
            requested_mode=requested_mode,
        )

        log.info(
            "chat_intent_resolved",
            intent=decision.intent,
            reason=decision.reason,
            source_id=str(active_source.id),
        )

        conversation_context = ""

        if conversation_id:
            conversation = (
                db_session.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.tenant_id == user.tenant_id,
                    Conversation.user_id == user.id,
                )
                .one_or_none()
            )

            if conversation is None:
                raise ValueError("Conversation was not found.")

            previous_messages = (
                db_session.query(ConversationMessage)
                .filter(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(8)
                .all()
            )

            conversation_context = "\n".join(
                f"{message.role}: {message.content}"
                for message in reversed(previous_messages)
                if message.content
            )[:6_000]

        # 2. Load full schema or retrieve relevant schema sections
        db_name, full_schema_text = (
            self.schema_provider.get_connected_schema(
                db_session=db_session,
                user=user,
                source=active_source,
            )
        )

        if not full_schema_text.strip():
            raise ValueError(
                "No active schema is available for the selected data source."
            )
        settings = get_settings()
        max_schema_chars = settings.chat_sql_max_schema_chars

        source_tables = (
            db_session.query(TableMeta)
            .options(selectinload(TableMeta.columns))
            .filter(
                TableMeta.source_id == active_source.id,
                TableMeta.is_active.is_(True),
            )
            .order_by(
                TableMeta.schema_name,
                TableMeta.table_name,
            )
            .all()
        )

        if not source_tables:
            raise ValueError(
                "No active table metadata is available for the selected data source."
            )
        
        # Build the validation catalog for every execution path.
        catalog: dict[str, set[str]] = {}

        for table in source_tables:
            columns = {
                column.column_name
                for column in table.columns
                if column.is_active
            }

            catalog[
                f"{table.schema_name}.{table.table_name}"
            ] = columns

            catalog[table.table_name] = columns

        if len(full_schema_text) <= max_schema_chars: 
            schema_text = full_schema_text
        else:
            retrieval_query = question

            # Follow-up questions such as "break this down by category"
            # require the previous conversation to resolve "this".
            if conversation_context:
                retrieval_query = (
                    f"CURRENT QUESTION:\n{question}\n\n"
                    f"RECENT CONVERSATION:\n"
                    f"{conversation_context[-2_000:]}"
                )

            retrieval = RetrievalService.retrieve(
                query_text=retrieval_query,
                tenant_id=user.tenant_id,
                db=db_session,
                source_id=active_source.id,
                object_types=[
                    "table",
                    "schema_chunk",
                    "relationship",
                ],
                top_k=settings.chat_sql_rag_top_k,
                distance_threshold=settings.chat_sql_rag_distance_threshold,
            )

            table_chunks: list[str] = []

            # Keep complete schema chunks produced during schema ingestion.
            # Use a case-insensitive comparison for TABLE:/Table:.
            for result in retrieval.raw_results:
                object_type = str(
                    result.metadata.get("object_type", "")
                ).strip().lower()
                result_text = (result.text or "").strip()

                if not result_text:
                    continue

                # Accept actual table objects and schema blocks containing TABLE:.
                if (
                    object_type in {
                        "table",
                        "schema_chunk",
                        "relationship",
                    }
                    or "TABLE:" in result_text.upper()
                ):
                    table_chunks.append(result_text)

            # Hydrated table results contain authoritative physical columns.
            for table, _distance in retrieval.tables:
                table_chunks.append(
                    _build_table_schema_block(table)
                )

            # Remove duplicate chunks without changing their order.
            table_chunks = list(dict.fromkeys(table_chunks))

            if table_chunks:
                selected_chunks: list[str] = []
                selected_length = 0

                for chunk in table_chunks:
                    additional_length = len(chunk) + 2

                    if (
                        selected_chunks
                        and selected_length + additional_length
                        > max_schema_chars
                    ):
                        continue

                    selected_chunks.append(chunk)
                    selected_length += additional_length

                schema_text = "\n\n".join(selected_chunks)
            
            else:
                log.warning(
                    "schema_retrieval_empty_using_compact_fallback",
                    source_id=str(active_source.id),
                    used_rag=retrieval.used_rag,
                    threshold=retrieval.threshold,
                    question=question[:200],
                )

                fallback_blocks: list[str] = []
                fallback_length = 0

                for table in source_tables:
                    block = _build_table_schema_block(table)
                    additional_length = len(block) + 2

                    if (
                        fallback_blocks
                        and fallback_length + additional_length > max_schema_chars
                    ):
                        break

                    fallback_blocks.append(block)
                    fallback_length += additional_length

                if not fallback_blocks:
                    raise ValueError(
                        "No active table metadata is available for schema fallback."
                    )

                schema_text = "\n\n".join(fallback_blocks)
                
        # 3. Load and validate optional domain context
        domain_context_str = ""

        if domain_id:
            domain_uuid = uuid.UUID(str(domain_id))

            domain = (
                db_session.query(Domain)
                .filter(
                    Domain.id == domain_uuid,
                    Domain.tenant_id == user.tenant_id,
                )
                .one_or_none()
            )

            if domain is None:
                raise ValueError("Domain was not found.")

            if (
                domain.source_id is not None
                and domain.source_id != active_source.id
            ):
                raise ValueError(
                    "The selected domain belongs to a different data source."
                )

            terms = (
                db_session.query(DomainTerm)
                .filter(DomainTerm.domain_id == domain.id)
                .order_by(DomainTerm.term)
                .limit(30)
                .all()
            )

            domain_context_str = "\n".join(
                [
                    f"Domain: {domain.name}",
                    f"Description: {domain.description or 'None'}",
                    "Terms:",
                    *[
                        f"- {term.term}: {term.definition}"
                        for term in terms
                    ],
                ]
            )[:4_000]
        
        schema_inventory = "\n".join(
            f"- {table.schema_name}.{table.table_name}: "
            + ", ".join(
                column.column_name
                for column in table.columns
                if column.is_active
            )
            for table in source_tables
        )

        if decision.intent == "strategy":
            answer = self.answer_synthesizer.synthesize_strategy(
                question=question,
                schema_inventory=schema_inventory,
                domain_context=domain_context_str,
                conversation_context=conversation_context,
            )

            follow_ups = ChatRecommender.recommend(
                intent="strategy",
                question=question,
                columns=[],
                schema_inventory=schema_inventory,
            )
            res_conv_id = self._persist_exchange(
                db_session=db_session,
                user=user,
                conversation_id=conversation_id,
                question=question,
                answer=answer,
                title="Business Strategy",
                intent="strategy",
                sql=None,
                rows=[],
                columns=[],
                column_types={},
                visualization="text",
                follow_up_questions=follow_ups,
                row_count=0,
                data_truncated=False,
                execution_time_ms=0.0,
            )

            return {
                "success": True,
                "intent": "strategy",
                "conversation_id": res_conv_id,
                "question": question,
                "answer": answer,
                "answer_markdown": answer,
                "summary": answer,
                "sql": None,
                "rows": [],
                "result_data": [],
                "columns": [],
                "column_types": {},
                "row_count": 0,
                "column_count": 0,
                "data_truncated": False,
                "visualization": "text",
                "title": "Business Strategy",
                "recommended_visualization": {
                    "visualization": "text",
                    "title": "Business Strategy",
                },
                "follow_up_questions": follow_ups,
                "execution_time_ms": 0.0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "database": active_source.database_name,
            }

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
            "insights",
            "insight",
            "give me insights",
            "key insights",
            "provide insights",
            "what insights",
            "summarize data",
            "summarize the data",
            "summary of data",
            "tell me about the data",
            "analyze this data",
            "trends and insights",
            "analytics overview",
            "data overview",
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
                timeout=300,
            )

            direct_follow_ups = ChatRecommender.recommend(
                intent=decision.intent,
                question=question,
                columns=[],
                schema_inventory=schema_inventory,
            )

            res_conv_id = self._persist_exchange(
                db_session=db_session,
                user=user,
                conversation_id=conversation_id,
                question=question,
                answer=direct_answer,
                title="Business and Data Analysis",
                intent=decision.intent,
                sql=None,
                rows=[],
                columns=[],
                column_types={},
                visualization="text",
                follow_up_questions=direct_follow_ups,
                row_count=0,
                data_truncated=False,
                execution_time_ms=0.0,
            )

            generated_at = datetime.now(timezone.utc).isoformat()

            return {
                "success": True,
                "intent": decision.intent,
                "conversation_id": res_conv_id,
                "question": question,
                "summary": direct_answer,
                "answer": direct_answer,
                "answer_markdown": direct_answer,
                "sql": None,
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
                "follow_up_questions": direct_follow_ups,
                "execution_time_ms": 0,
                "generated_at": generated_at,
                "database": db_name,
                "column_types": {},
            }

        source_dialect = (active_source.type or "postgres").lower()

        # 4b. Build a SQL prompt only when the question requires SQL.
        prompt = self.prompt_builder.build_prompt(
            question=question,
            schema_text=schema_text,
            database_name=db_name,
            domain_context=domain_context_str,
            conversation_context=conversation_context,
            dialect=source_dialect,
        )
        # 4b. Generate the initial SQL draft
        try:
            raw_sql = self.llm_provider.generate_sql(
                prompt=prompt,
                question=question,
            )

        except (LLMTimeoutError, LLMUnavailableError):
            raise

        except Exception as exc:
            log.error(
                "chat_sql_generation_error",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise RuntimeError(
                f"Ollama SQL generation failed: {exc}"
            ) from exc

        # 5. Deterministically validate the generated SQL.
        draft_sql = self.sql_validator.validate_sql(
            raw_sql,
            catalog=catalog,
            dialect=source_dialect,
        )

        # Attempt correction when Ollama returned SQL but static validation
        # rejected it. Do not correct an intentional UNANSWERABLE response.
        if (
            draft_sql == "UNANSWERABLE"
            and raw_sql.strip().upper() != "UNANSWERABLE"
        ):
            corrected_raw_sql = self.llm_provider.refine_sql(
                question=question,
                failed_sql=raw_sql,
                error_message=(
                    f"Static validation rejected the query. Use {source_dialect.upper()} "
                    "syntax and only physical tables and columns declared "
                    "in DATABASE SCHEMA."
                ),
                schema_text=schema_text,
            )

            draft_sql = self.sql_validator.validate_sql(
                corrected_raw_sql,
                catalog=catalog,
                dialect=source_dialect,
            )

        validated_sql = draft_sql

        # Optional semantic review. Keep the validated draft if the reviewer
        # returns invalid SQL instead of discarding a usable query.
        if validated_sql != "UNANSWERABLE":
            reviewed_sql = self.llm_provider.review_sql(
                question=question,
                candidate_sql=validated_sql,
                schema_text=schema_text,
                domain_context=domain_context_str,
            )

            reviewed_validated_sql = self.sql_validator.validate_sql(
                reviewed_sql,
                catalog=catalog,
                dialect=source_dialect,
            )

            if reviewed_validated_sql != "UNANSWERABLE":
                validated_sql = reviewed_validated_sql
            else:
                log.warning(
                    "sql_review_rejected_using_validated_draft"
                )

         # Preflight the reviewed SQL and allow one correction attempt.
        if validated_sql != "UNANSWERABLE":
            attempted_sql: list[str] = []
            candidate_sql = validated_sql
            last_error: str | None = None

            for attempt_number in range(2):
                attempted_sql.append(candidate_sql)

                preflight_error = self.sql_executor.preflight_query(
                    candidate_sql,
                    source=active_source,
                )

                if preflight_error is None:
                    break

                last_error = preflight_error

                if attempt_number == 1:
                    candidate_sql = "UNANSWERABLE"
                    break

                corrected_sql = self.llm_provider.refine_sql(
                    question=question,
                    failed_sql=candidate_sql,
                    error_message=(
                        f"{preflight_error}\n\n"
                        "Previously rejected queries:\n"
                        + "\n---\n".join(attempted_sql)
                    ),
                    schema_text=schema_text,
                )

                candidate_sql = self.sql_validator.validate_sql(
                    corrected_sql,
                    catalog=catalog,
                    dialect=source_dialect,
                )

                if candidate_sql == "UNANSWERABLE":
                    break

            validated_sql = candidate_sql

            if validated_sql == "UNANSWERABLE":
                log.warning(
                    "sql_preflight_failed_after_correction",
                    error=last_error,
                    attempted_sql_count=len(attempted_sql),
                )

        # Return a controlled response instead of sending UNANSWERABLE to the database executor.
        if validated_sql == "UNANSWERABLE":
            generated_at = datetime.now(timezone.utc).isoformat()
            clarification_answer = (
                "I could not produce a reliable query for this question. "
                "Please specify which type of unusual behavior you want to "
                "analyze: fraud alerts, failed payments, high-value orders, "
                "refunds, or login activity."
            )

            clarification_questions = [
                "Which customers have the most high-risk fraud alerts?",
                "Which customers have unusually frequent failed payments?",
                "Which orders have unusually high values?",
            ]

            res_conv_id = self._persist_exchange(
                db_session=db_session,
                user=user,
                conversation_id=conversation_id,
                question=question,
                answer=clarification_answer,
                title="Clarification required",
                intent=decision.intent,
                sql="UNANSWERABLE",
                rows=[],
                columns=[],
                column_types={},
                visualization="text",
                follow_up_questions=clarification_questions,
                row_count=0,
                data_truncated=False,
                execution_time_ms=0.0,
            )

            return {
                "success": False,
                "intent": decision.intent,
                "conversation_id": res_conv_id,
                "question": question,
                "summary": clarification_answer,
                "answer": clarification_answer,
                "answer_markdown": clarification_answer,
                "sql": "UNANSWERABLE",
                "rows": [],
                "result_data": [],
                "columns": [],
                "column_types": {},
                "row_count": 0,
                "column_count": 0,
                "data_truncated": False,
                "visualization": "text",
                "title": "Clarification required",
                "recommended_visualization": {
                    "visualization": "text",
                    "title": "Clarification required",
                },
                "follow_up_questions": clarification_questions,
                "execution_time_ms": 0.0,
                "generated_at": generated_at,
                "database": db_name,
            }

        # 6. Execute reviewed and validated SQL
        (
            result_data,
            row_count,
            execution_time_ms,
            columns,
            execution_error,
            result_truncated,
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
                retry_truncated,
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
            result_truncated = retry_truncated

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
            result_truncated=result_truncated,
            force_strategy_format=decision.intent == "hybrid",
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

        follow_ups = ChatRecommender.recommend(
            intent=decision.intent,
            question=question,
            columns=columns,
            schema_inventory=schema_inventory,
        )

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

        # 9. Persist the successful user/assistant exchange.
        column_types = (
            vis_payload.get("profile", {}).get(
                "column_types",
                {},
            )
        )

        res_conv_id = self._persist_exchange(
            db_session=db_session,
            user=user,
            conversation_id=conversation_id,
            question=question,
            answer=answer,
            title=title,
            intent=decision.intent,
            sql=validated_sql,
            rows=result_data,
            columns=columns,
            column_types=column_types,
            visualization=vis_type,
            follow_up_questions=follow_ups,
            row_count=row_count,
            data_truncated=result_truncated,
            execution_time_ms=execution_time_ms,
        )

        return {
            "success": True,
            "intent": decision.intent,
            "conversation_id": res_conv_id,
            "question": question,
            "summary": answer,
            "answer": answer,
            "answer_markdown": answer,
            "sql": validated_sql,
            "result_data": result_data,
            "rows": result_data,
            "columns": columns,
            "row_count": row_count,
            "column_count": len(columns),
            "data_truncated": result_truncated,
            "visualization": vis_type,
            "title": title,
            "profile": vis_payload.get("profile"),
            "statistics": {
                "row_count": row_count,
                "column_count": len(columns),
                "execution_time_ms": execution_time_ms,
            },
            "recommended_visualization": vis_payload,
            "follow_up_questions": follow_ups,
            "execution_time_ms": execution_time_ms,
            "generated_at": generated_at,
            "database": db_name,
            "column_types": column_types,
        }
