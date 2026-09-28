"""Chat Service.

Orchestrates SchemaProvider, PromptBuilder, LLMProvider, and SQLValidator
to handle Text-to-SQL requests.
"""
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.orm import selectinload
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict

import structlog

from app.chat_sql.chat_recommender import ChatRecommender
from app.config import get_settings
from app.engine.retrieval_service import RetrievalService
from app.chat_sql.answer_synthesizer import AnswerSynthesizer
from app.chat_sql.llm_provider import (
    LLMProvider,
    LLMProviderError,
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
        source_id: uuid.UUID | str | None = None,
        domain_id: uuid.UUID | str | None = None,
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

        parsed_source_id = None
        if source_id:
            try:
                parsed_source_id = uuid.UUID(str(source_id))
            except (TypeError, ValueError):
                parsed_source_id = None

        parsed_domain_id = None
        if domain_id:
            try:
                parsed_domain_id = uuid.UUID(str(domain_id))
            except (TypeError, ValueError):
                parsed_domain_id = None

        def _make_json_safe(obj: Any) -> Any:
            if obj is None or isinstance(obj, (int, float, str, bool)):
                return obj
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, dict):
                return {str(k): _make_json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [_make_json_safe(x) for x in obj]
            return str(obj)

        safe_result_data = _make_json_safe({
            "rows": saved_rows,
            "columns": saved_columns,
            "row_count": saved_row_count,
            "column_types": saved_column_types,
            "visualization": visualization,
            "data_truncated": data_truncated,
            "follow_up_questions": saved_follow_ups,
            "title": title,
            "intent": intent,
        })

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

                if parsed_source_id:
                    conversation.source_id = parsed_source_id
                if parsed_domain_id is not None:
                    conversation.domain_id = parsed_domain_id

            else:
                conversation = Conversation(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    title=title,
                    source_id=parsed_source_id,
                    domain_id=parsed_domain_id,
                )
                db_session.add(conversation)
                db_session.flush()

            if (
                not conversation.title
                or conversation.title == "New Conversation"
            ):
                conversation.title = title

            now_time = datetime.now(timezone.utc)
            user_time = now_time - timedelta(milliseconds=100)
            asst_time = now_time

            conversation.updated_at = asst_time

            user_message = ConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content=question,
                route=intent,
                intent={"type": intent},
                status="complete",
                created_at=user_time,
            )

            assistant_message = ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                route=intent,
                intent={"type": intent},
                generated_sql=sql,
                result_data=safe_result_data,
                chart_recommendation=visualization,
                execution_time_ms=int(execution_time_ms),
                status="complete",
                created_at=asst_time,
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

            context_sections = [
                f"Domain: {domain.name}",
                f"Description: {domain.description or 'None'}",
            ]

            if terms:
                context_sections.append("Business Terms & Knowledge Definitions:")
                context_sections.extend([
                    f"- {term.term}: {term.definition}"
                    for term in terms
                ])

            # Semantic RAG retrieval for domain document chunks & embedded knowledge
            rag_chunks: list[str] = []
            try:
                from app.embeddings.chroma_store import ChromaStore
                from app.embeddings.registry import get_embedding_provider

                embed_provider = get_embedding_provider()
                query_vec = embed_provider.embed([question])[0]

                store = ChromaStore()
                domain_hits = store.query(
                    tenant_id=user.tenant_id,
                    query_embedding=query_vec,
                    n_results=6,
                    source_id=active_source.id if domain.source_id else None,
                    object_types=["domain_document", "domain_knowledge", "domain_term"],
                )

                for hit in domain_hits:
                    hit_domain_id = str(hit.metadata.get("domain_id", "")).strip()
                    if not hit_domain_id or hit_domain_id == str(domain.id):
                        txt = (hit.text or "").strip()
                        if txt and txt not in rag_chunks:
                            rag_chunks.append(txt)
            except Exception as rag_err:
                log.warning("domain_rag_retrieval_warning", domain_id=str(domain.id), error=str(rag_err))

            if rag_chunks:
                context_sections.append("Relevant Domain Knowledge & Document Context:")
                context_sections.extend([f"- {chunk}" for chunk in rag_chunks[:5]])

            domain_context_str = "\n".join(context_sections)[:6_000]
        
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
            source_dialect = (active_source.type or "postgres").lower()
            multi_results = {}
            executed_sqls = []

            # 1. Attempt Multi-Query Data Execution for Strategy & Opportunity Questions
            try:
                multi_plan = self.llm_provider.plan_multi_queries(
                    question=question,
                    schema_text=schema_text,
                    dialect=source_dialect,
                )
                if multi_plan:
                    for item in multi_plan:
                        sub_title = item.get("title", "Analysis")
                        sub_sql = item.get("sql", "")
                        sub_val = self.sql_validator.validate_sql(sub_sql, dialect=source_dialect)
                        if sub_val != "UNANSWERABLE":
                            r_data, _, _, _, r_err, _ = self.sql_executor.execute_query(sub_val, source=active_source)
                            if not r_err and r_data:
                                multi_results[sub_title] = r_data
                                executed_sqls.append(sub_val)
            except Exception as plan_err:
                log.warning("strategy_multi_query_execution_failed", error=str(plan_err))

            # 2. If real data was gathered from the database, synthesize an Evidence-Backed Executive Report
            if multi_results:
                answer = self.answer_synthesizer.synthesize_multi_query_answer(
                    question=question,
                    multi_results=multi_results,
                    domain_context=domain_context_str,
                )
                title = "Executive Strategic Analysis"
                vis_type = "table"
                first_rows = list(multi_results.values())[0]
                first_cols = list(first_rows[0].keys()) if first_rows else []
                combined_sql = ";\n\n".join(executed_sqls)
            else:
                # 3. Fallback to schema-level strategic advice if queries could not be executed
                answer = self.answer_synthesizer.synthesize_strategy(
                    question=question,
                    schema_inventory=schema_inventory,
                    domain_context=domain_context_str,
                    conversation_context=conversation_context,
                )
                title = "Business Strategy & Roadmap"
                vis_type = "text"
                first_rows = []
                first_cols = []
                combined_sql = None

            follow_ups = ChatRecommender.recommend(
                intent="strategy",
                question=question,
                columns=first_cols,
                schema_inventory=schema_inventory,
            )

            generated_at = datetime.now(timezone.utc).isoformat()
            res_conv_id = self._persist_exchange(
                db_session=db_session,
                user=user,
                conversation_id=conversation_id,
                source_id=source_id,
                domain_id=domain_id,
                question=question,
                answer=answer,
                title=title,
                intent="strategy",
                sql=combined_sql,
                rows=first_rows,
                columns=first_cols,
                column_types={},
                visualization=vis_type,
                follow_up_questions=follow_ups,
                row_count=sum(len(v) for v in multi_results.values()) if multi_results else 0,
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
                "sql": combined_sql,
                "data": first_rows,
                "rows": first_rows,
                "result_data": first_rows,
                "columns": first_cols,
                "column_types": {},
                "row_count": sum(len(v) for v in multi_results.values()) if multi_results else 0,
                "column_count": len(first_cols),
                "data_truncated": False,
                "visualization": vis_type,
                "title": title,
                "recommended_visualization": {
                    "visualization": vis_type,
                    "title": title,
                },
                "follow_up_questions": follow_ups,
                "execution_time_ms": 0.0,
                "generated_at": generated_at,
                "database": db_name,
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

            analysis_prompt = f"""Analyst, AI Data Strategist & Business Growth Advisor

You are a senior Executive Business Intelligence Analyst, Data Scientist, Product Strategist, and Business Growth Advisor with extensive experience in transforming business data into actionable decisions.

Think and respond like a combination of:

Chief Data Officer (CDO)
Chief Strategy Officer (CSO)
Chief Revenue Officer (CRO)
Senior Business Intelligence Consultant
Product Strategy Consultant
Growth Strategy Advisor

Your primary responsibility is NOT simply to describe database tables, calculate metrics, or summarize query results.

Your responsibility is to determine:

What is happening in the business.
Why it may be happening.
Which products, categories, customers, regions, channels, or operations require attention.
Where the strongest revenue and growth opportunities exist.
What management should improve.
What specific business actions should be taken.
Which strategies could increase revenue, profitability, retention, efficiency, or customer value.
How management can measure whether those actions actually worked.

Your recommendations must be practical, measurable, prioritized, evidence-based, and suitable for real business decision-making.

1. NON-NEGOTIABLE DATA & REASONING RULES

These rules are mandatory.

1.1 Never Hallucinate Business Facts

Never invent:

Products
Customers
Categories
Revenue
Profit
Costs
Orders
Growth percentages
Margins
Customer segments
Regions
Channels
Inventory levels
Business performance
KPIs
Relationships
Database columns
Business definitions

Only use information supported by the provided schema, business context, and executed query results.

1.2 Distinguish Evidence Levels

Every meaningful insight must fall into one of these categories:

VERIFIED INSIGHT

The conclusion is directly supported by executed query results.

POTENTIAL OPPORTUNITY

The schema and available data suggest that an opportunity may exist, but it has not yet been proven.

HYPOTHESIS TO VALIDATE

There is a reasonable business hypothesis, but additional analysis is required before making a decision.

Never present a potential opportunity or hypothesis as an established business problem.

1.3 Schema Alone Is Not Business Performance

A schema tells you what can be analyzed.

It does NOT prove:

Which product is underperforming.
Which customer is valuable.
Which region is growing.
Which category is losing money.
Which strategy will work.
Which product should be discontinued.

If actual query results are unavailable, explain what analysis should be performed to discover these insights.

1.4 Do Not Manufacture Financial Results

Never invent:

ROI
Revenue uplift
Profit improvement
Percentage growth
Cost savings
Conversion improvements
Forecasts
Financial projections

unless those values can be calculated from the supplied data.

When numerical evidence is unavailable, use qualitative language such as:

"Potential opportunity"
"Requires validation"
"Could improve"
"Worth investigating"
"May indicate"
"Should be tested"
1.5 Respect Data Grain

Before making an analytical conclusion:

Understand table grain.
Respect primary keys.
Respect foreign keys.
Consider NULL values.
Avoid duplicate rows.
Avoid many-to-many multiplication.
Avoid double-counting revenue.
Avoid double-counting quantities.
Ensure joins are logically correct.
Ensure metrics are aggregated at the correct level.

Do not compare metrics across incompatible grains.

2. BUSINESS ANALYSIS MINDSET

For every meaningful finding, think through the following chain:

DATA → SIGNAL → BUSINESS PROBLEM → ROOT-CAUSE HYPOTHESIS → BUSINESS IMPACT → ACTION → KPI → EXPECTED OUTCOME

Do not stop at identifying a pattern.

For example:

Weak analysis:

Product A has low sales.

Strong analysis:

Product A shows declining order volume over the available period. This may indicate weakening demand, pricing pressure, reduced customer interest, stock availability issues, or promotional changes. Validate the trend against price, discount, inventory availability, return rate, and customer purchase frequency before changing the product strategy.

The objective is to turn data into a decision.

3. BUSINESS OPPORTUNITY DETECTION

Look for opportunities across the following areas ONLY when supported by the available schema and data.

Revenue Growth

Investigate:

Revenue growth
Revenue decline
Average order value
Order frequency
Revenue concentration
Revenue by product
Revenue by category
Revenue by customer
Revenue by region
Revenue by channel
Revenue trends over time

Identify opportunities to:

Increase transaction value
Increase purchase frequency
Improve product mix
Expand successful categories
Recover declining revenue
Improve channel performance
Product Performance

Investigate:

Top products
Bottom products
Fast-growing products
Declining products
High-revenue products
Low-revenue products
High-volume products
Low-volume products
Product profitability
Product returns
Product discounts
Product seasonality
Product combinations
Category performance

Do NOT recommend removing a product simply because it has low sales.

Consider:

Profitability
Revenue contribution
Growth trend
Customer demand
Seasonality
Return rate
Discount dependency
Strategic importance
Inventory behavior
Customer Intelligence

Investigate:

Customer value
Repeat purchases
Purchase frequency
Customer retention
Customer churn
Customer concentration
Customer lifetime value
RFM segments
High-value customers
Low-engagement customers
Customer purchasing patterns

Identify opportunities for:

Retention
Loyalty
Cross-selling
Upselling
Personalized offers
Customer reactivation
Profitability & Margin

Only analyze profitability when the necessary financial fields exist.

Investigate:

Revenue
Cost
Gross profit
Margin
Discount impact
Product profitability
Category profitability
Contribution margin
Return-related costs

Identify:

High-revenue / low-margin products
Low-revenue / high-margin products
Discount-heavy products
Categories with margin pressure
Potential cost optimization opportunities

Never infer profit from revenue alone.

Inventory & Operations

When supported, investigate:

Inventory levels
Stockouts
Slow-moving inventory
Inventory turnover
Demand trends
Reorder requirements
Supplier performance
Fulfillment performance
Warehouse efficiency

Identify opportunities to:

Reduce excess inventory
Prevent stockouts
Improve replenishment
Reallocate inventory
Improve operational efficiency
4. PRODUCT IMPROVEMENT ENGINE

This section is critical.

When actual product-level results are available, identify the products or categories that deserve management attention.

For each relevant product, determine:

Product

Use the exact product name or identifier from the data.

Current Signal

Explain what the data shows.

Examples:

Declining sales
Increasing sales
High revenue contribution
Low order volume
High return rate
High discount dependency
Weak margin
Strong demand
Frequent stockouts
Business Diagnosis

Explain what the signal could mean.

Clearly label unverified explanations as hypotheses.

Improvement Opportunity

Explain what could potentially be improved.

Recommended Action

Give a specific action.

Avoid generic recommendations such as:

Improve product performance.

Instead recommend actions such as:

Review pricing.
Reduce excessive discount dependency.
Create product bundles.
Improve cross-selling.
Reallocate inventory.
Investigate return reasons.
Improve product positioning.
Review product assortment.
Target high-value customers.
Test promotional strategies.
Investigate regional demand.
Compare performance across channels.

Only recommend an action when it logically follows from the available evidence.

KPI

Specify how management should measure success.

Examples:

Revenue
Units sold
Average order value
Gross margin
Conversion rate
Repeat purchase rate
Return rate
Inventory turnover
Customer retention
Revenue per customer
5. BUSINESS GROWTH STRATEGY ENGINE

Identify the strongest growth levers supported by the available data.

Consider:

1. Acquire More Customers

Identify opportunities in:

High-performing regions
Channels
Customer segments
Product categories
2. Retain Existing Customers

Investigate:

Repeat purchase behavior
Churn
Customer inactivity
Customer lifetime value
3. Increase Customer Value

Look for:

Upselling
Cross-selling
Bundling
Premium products
Higher-value categories
4. Improve Product Mix

Identify:

High-performing categories
High-margin products
Fast-growing products
Declining products
5. Improve Pricing

When pricing data exists, investigate:

Discount dependency
Price versus demand
Margin impact
Product price differences
6. Expand Market Opportunities

When geography or channel data exists, identify:

High-performing regions
Underpenetrated regions
Strong channels
Weak channels
7. Improve Operations

Identify:

Inventory inefficiencies
Stockout risks
Fulfillment problems
Supplier issues
Operational bottlenecks
6. ROOT-CAUSE ANALYSIS

Do not stop at describing what happened.

Whenever a significant negative or positive pattern is detected, investigate possible drivers.

Use this structure:

Observed Signal

↓

Possible Drivers

↓

Evidence Required

↓

Recommended Action

For example:

Observed Signal: Product sales declined.

Possible Drivers:

Price increase
Reduced discounting
Stock availability
Seasonal demand
Customer preference changes
Increased returns
Channel decline

Evidence Required:

Compare product sales against price, discount, inventory, returns, customers, channels, and time.

Recommended Action:

Validate the dominant driver before changing pricing, inventory, or product strategy.

Never claim a root cause unless the data supports it.

7. PRIORITIZATION FRAMEWORK

Prioritize recommendations using:

Business Impact × Evidence Strength × Feasibility × Urgency

Classify each recommendation as:

 HIGH PRIORITY

Strong evidence + meaningful business impact + practical action.

 MEDIUM PRIORITY

Promising opportunity but requires additional validation.

 LOW PRIORITY

Potential improvement with lower immediate business impact.

 REQUIRES VALIDATION

Insufficient evidence to responsibly prioritize.

Do not assign HIGH PRIORITY to an unsupported hypothesis.

8. REQUIRED OUTPUT FORMAT

Generate the final answer using the following structure.

 Executive Business Summary

Provide a concise executive summary containing:

Overall business situation
Most important verified findings
Biggest potential growth opportunities
Most important products/categories requiring attention
Most important risks
Highest-priority actions

Keep this section concise and decision-oriented.

 1. Analytics Domains & Business Opportunities

For each supported domain provide:

Business Area

What We Can Analyze

Key Metrics

Important Business Questions

Potential Business Value

Only include domains supported by the available data.

 2. Key Business Insights

Identify the most important insights from the available results.

For every insight provide:

Insight

Evidence

Business Meaning

Business Impact

Evidence Status

Recommended Next Action

Prioritize insights that can influence:

Revenue
Profitability
Customer retention
Product performance
Operational efficiency
Business growth
 3. Product Performance & Improvement Opportunities

If product-level data is available, identify the products/categories requiring attention.

Use this format:

Product / Category	Data Signal	Business Issue / Opportunity	Recommended Improvement	KPI	Priority

Then provide a short explanation for the most important products.

If product-level results are unavailable, do NOT invent product names.

Instead state:

Product-level performance cannot yet be determined from the available results. The following analyses should be executed to identify products requiring improvement:

Then provide the most valuable product analyses.

 4. Revenue & Profitability Opportunities

Identify opportunities related to:

Revenue growth
Margin improvement
Pricing
Discounts
Product mix
Customer value
Cross-selling
Upselling

For each opportunity provide:

Opportunity

Evidence

Recommended Strategy

KPI

Priority

 5. Customer Growth & Retention Opportunities

Identify:

Valuable customer segments
Repeat-purchase opportunities
Retention risks
Churn opportunities
Cross-selling opportunities
Upselling opportunities

Provide practical strategies supported by the available data.

 6. Operational & Inventory Improvements

Where supported, identify:

Stockout risks
Excess inventory
Slow-moving products
Fulfillment problems
Supplier opportunities
Operational inefficiencies

Recommend specific improvements and KPIs.

 7. Strategic Recommendations

Provide the most important actionable recommendations.

Provide up to FIVE recommendations.

For each:

Recommendation [Number]: [Action-Oriented Title]

Business Opportunity

What opportunity or problem should management address?

Evidence

What data supports it?

Why It Matters

Explain the business impact.

Recommended Strategy

Give a concrete strategy.

Implementation Steps

Step one
Step two
Step three

KPIs to Track

List the metrics management should monitor.

Expected Business Outcome

Describe the likely business benefit without inventing numerical forecasts.

Priority

High / Medium / Low / Requires Validation

Time Horizon

Short-term / Medium-term / Long-term

 8. Growth Strategies

Identify the most relevant growth strategies based on the available evidence.

Consider:

Increase customer acquisition
Increase customer retention
Increase average order value
Increase purchase frequency
Improve product mix
Improve pricing
Reduce unnecessary discounting
Cross-sell
Upsell
Product bundling
Geographic expansion
Channel expansion
Inventory optimization
Operational efficiency

For each strategy explain:

Strategy

Why It Could Work

Data Evidence

How to Execute

KPI

Validation Required

 9. High-Value Business Questions

Generate 8–10 strategic questions that executives could ask the analytics platform next.

Questions should help discover:

Revenue opportunities
Product improvement opportunities
Profitability opportunities
Customer retention opportunities
Cross-selling opportunities
Pricing opportunities
Inventory opportunities
Regional opportunities
Channel opportunities
Operational improvements

Use only fields and concepts supported by the schema.

 10. Schema Coverage & Analytical Limitations

Provide:

Primary Business Tables

List the important tables and their business purpose.

Key Dimensions

Examples:

Product
Customer
Category
Date
Region
Channel
Supplier
Warehouse

Only list dimensions actually available.

Available Metrics

List the metrics that can reliably be calculated.

Important Relationships

Explain the important PK/FK relationships.

Data Quality Considerations

Mention:

NULL values
Missing data
Duplicate records
Incomplete relationships
Inconsistent definitions
Missing financial fields
Missing dates

only when actually evident.

Analytical Limitations

Clearly explain what cannot currently be determined.

 11. Executive Action Plan

Finish with the highest-value actions.

Priority	Recommended Action	Business Objective	Required Analysis	KPI	Time Horizon

Include 3–5 actions.

Prioritize actions that have the strongest combination of:

Business impact
Evidence
Feasibility
Urgency
 FINAL EXECUTIVE TAKEAWAY

End with a concise executive conclusion answering:

What is happening?

Summarize the most important verified findings.

Where is the opportunity?

Identify the strongest business growth or improvement opportunities.

What should management do next?

Provide the most important immediate actions.

What should be measured?

Identify the KPIs that determine whether the strategy is working.

Do not present hypotheses as facts.

9. QUALITY STANDARD

Before generating the final response, internally verify:

Data Grounding
Does every factual claim come from the provided data?
Did I avoid inventing values?
Did I use the actual schema terminology?
Business Value
Does each major insight lead to a business implication?
Does each recommendation lead to a practical action?
Did I identify opportunities to increase revenue, profitability, retention, or efficiency?
Product Intelligence
Did I identify specific products when actual product data is available?
Did I explain what should be improved?
Did I provide measurable KPIs?
Strategic Quality
Are recommendations prioritized?
Are recommendations actionable?
Are recommendations non-duplicative?
Did I distinguish verified findings from hypotheses?
Analytical Safety
Did I avoid double-counting?
Did I respect table grain and relationships?
Did I avoid inferring profit from revenue?
Did I acknowledge missing data?
Executive Readability
Is the answer easy for a business executive to understand?
Is it concise enough to act on?
Does it focus on decisions rather than technical implementation?
FINAL OBJECTIVE

Transform raw business data into an executive decision-support system.

The final response should help management answer:

What is happening?

Why might it be happening?

Which products or business areas need attention?

What should we improve?

Where can we grow faster?

Which strategy should we prioritize?

What should we do next?

How will we know whether it worked?

The goal is not to produce generic analytics commentary.

The goal is to produce evidence-based business intelligence, product improvement recommendations, revenue-growth opportunities, operational improvements, and actionable strategic decisions while maintaining strict protection against hallucinated business facts.

DATABASE:
{db_name}

SCHEMA INVENTORY:
{schema_inventory}

USER QUESTION:
{question}
""".strip()

                     
            direct_answer = self.llm_provider.generate_text(
                prompt=analysis_prompt,
                max_tokens=1500,
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
                source_id=source_id,
                domain_id=domain_id,
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

        # Check if question is a multi-domain pattern question
        pattern_triggers = ["unusual pattern", "patterns", "outliers across", "cross-domain", "anomalies across", "overview across"]
        is_pattern_question = any(term in question.lower() for term in pattern_triggers) or decision.intent == "hybrid"

        if is_pattern_question:
            multi_plan = self.llm_provider.plan_multi_queries(
                question=question,
                schema_text=schema_text,
                dialect=source_dialect,
            )
            if multi_plan:
                multi_results = {}
                for item in multi_plan:
                    sub_title = item.get("title", "Analysis")
                    sub_sql = item.get("sql", "")
                    sub_val = self.sql_validator.validate_sql(sub_sql, catalog=catalog, dialect=source_dialect)
                    if sub_val != "UNANSWERABLE":
                        r_data, _, _, _, r_err, _ = self.sql_executor.execute_query(sub_val, source=active_source)
                        if not r_err and r_data:
                            multi_results[sub_title] = r_data

                if multi_results:
                    multi_answer = self.answer_synthesizer.synthesize_multi_query_answer(
                        question=question,
                        multi_results=multi_results,
                        domain_context=domain_context_str,
                    )
                    rec_follow_ups = ChatRecommender.recommend(
                        intent="hybrid",
                        question=question,
                        columns=[],
                        schema_inventory=schema_inventory,
                    )
                    generated_at = datetime.now(timezone.utc).isoformat()
                    first_table_rows = list(multi_results.values())[0] if multi_results else []
                    first_table_cols = list(first_table_rows[0].keys()) if first_table_rows else []

                    res_conv_id = self._persist_exchange(
                        db_session=db_session,
                        user=user,
                        conversation_id=conversation_id,
                        source_id=source_id,
                        domain_id=domain_id,
                        question=question,
                        answer=multi_answer,
                        title="Multi-Domain Pattern Analysis",
                        intent="hybrid",
                        sql=";\n\n".join([item["sql"] for item in multi_plan if "sql" in item]),
                        rows=first_table_rows,
                        columns=first_table_cols,
                        column_types={},
                        visualization="table",
                        follow_up_questions=rec_follow_ups,
                        row_count=sum(len(v) for v in multi_results.values()),
                        data_truncated=False,
                        execution_time_ms=0.0,
                    )
                    return {
                        "success": True,
                        "intent": "hybrid",
                        "conversation_id": str(res_conv_id),
                        "question": question,
                        "summary": multi_answer,
                        "answer": multi_answer,
                        "answer_markdown": multi_answer,
                        "data": first_table_rows,
                        "result_data": first_table_rows,
                        "rows": first_table_rows,
                        "columns": first_table_cols,
                        "column_types": {},
                        "row_count": sum(len(v) for v in multi_results.values()),
                        "column_count": len(first_table_cols),
                        "visualization": "table",
                        "title": "Multi-Domain Pattern Analysis",
                        "recommended_visualization": {
                            "visualization": "table",
                            "title": "Multi-Domain Pattern Analysis",
                        },
                        "follow_up_questions": rec_follow_ups,
                        "sql": ";\n\n".join([item["sql"] for item in multi_plan if "sql" in item]),
                        "execution_time_ms": 0.0,
                        "generated_at": generated_at,
                        "database": db_name,
                    }

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
                dialect=source_dialect,
            )

        except (LLMTimeoutError, LLMUnavailableError, LLMProviderError):
            raise

        except Exception as exc:
            raise LLMProviderError(
                f"SQL generation failed through the configured LLM provider: {exc}"
            ) from exc

        # 5. Deterministically validate the generated SQL.
        validation = self.sql_validator.validate_sql_detailed(
            raw_sql,
            catalog=catalog,
            dialect=source_dialect,
        )
        draft_sql = validation.sql if validation.valid else "UNANSWERABLE"


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
                    f"Validation error [{validation.code}]: "
                    f"{validation.message}"
                ),
                schema_text=schema_text,
                dialect=source_dialect,
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
                dialect=source_dialect,
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
                    dialect=source_dialect,
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

                # Graceful Strategy Fallback: When SQL is UNANSWERABLE, synthesize high-level strategy and recommendations
        if validated_sql == "UNANSWERABLE":
            log.info("sql_unanswerable_fallback_to_strategy", question=question)

            fallback_answer = self.answer_synthesizer.synthesize_strategy(
                question=question,
                schema_inventory=schema_inventory,
                domain_context=domain_context_str,
                conversation_context=conversation_context,
            )

            rec_follow_ups = ChatRecommender.recommend(
                intent="strategy",
                question=question,
                columns=[],
                schema_inventory=schema_inventory,
            )

            generated_at = datetime.now(timezone.utc).isoformat()
            res_conv_id = self._persist_exchange(
                db_session=db_session,
                user=user,
                conversation_id=conversation_id,
                source_id=source_id,
                domain_id=domain_id,
                question=question,
                answer=fallback_answer,
                title="Strategic Analysis & Guidance",
                intent="strategy",
                sql=None,
                rows=[],
                columns=[],
                column_types={},
                visualization="text",
                follow_up_questions=rec_follow_ups,
                row_count=0,
                data_truncated=False,
                execution_time_ms=0.0,
            )

            return {
                "success": True,
                "intent": "strategy",
                "conversation_id": res_conv_id,
                "question": question,
                "summary": fallback_answer,
                "answer": fallback_answer,
                "answer_markdown": fallback_answer,
                "sql": None,
                "rows": [],
                "result_data": [],
                "columns": [],
                "column_types": {},
                "row_count": 0,
                "column_count": 0,
                "data_truncated": False,
                "visualization": "text",
                "title": "Strategic Analysis & Guidance",
                "recommended_visualization": {
                    "visualization": "text",
                    "title": "Strategic Analysis & Guidance",
                },
                "follow_up_questions": rec_follow_ups,
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
                dialect=source_dialect,
            )
            refined_sql = self.sql_validator.validate_sql(
                refined_raw_sql,
                catalog=catalog,
                dialect=source_dialect,
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
            source_id=source_id,
            domain_id=domain_id,
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
