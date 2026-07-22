import uuid
import traceback
import structlog
from datetime import datetime, timezone
from rq.timeouts import JobTimeoutException
from app.db import session_scope
from app.models import ConversationMessage, Conversation
from app.engine.context_manager import ConversationContextManager
from app.engine.nlu_service import NLUService
from app.engine.retrieval_service import RetrievalService
from app.engine.resolver_service import ResolverService
from app.engine.planner_service import PlannerService
from app.engine.validation_service import ValidationService
from app.engine.compiler_service import CompilerService, SQLSafetyError
from app.engine.executor_service import ExecutorService
from app.engine.nl_generator import NLGenerator
from app.engine.chart_recommender import ChartRecommender
from app.engine.router_service import RouterService

log = structlog.get_logger()

# Fixed ordered stage definitions for the analytics pipeline.
# Frontend renders these in exactly this order.
ANALYTICS_STAGES = [
    ("parsing_question",   "Classifying your question..."),
    ("resolving_entities", "Identifying relevant metrics and dimensions..."),
    ("planning_query",     "Building the query plan..."),
    ("generating_sql",     "Compiling SQL..."),
    ("executing_query",    "Running the query..."),
    ("generating_insights","Generating natural language insights..."),
]


def _append_trace(db, msg: ConversationMessage, stage: str, label: str, status: str) -> None:
    """Append a stage entry to msg.trace and immediately commit so the polling
    endpoint sees the update before the next stage starts.

    Entries are appended in order so the list acts as a timeline.
    """
    entry = {
        "stage":  stage,
        "label":  label,
        "status": status,
        "at":     datetime.now(timezone.utc).isoformat(),
    }
    # JSONB mutation requires explicit reassignment to trigger SQLAlchemy change detection.
    current = list(msg.trace) if msg.trace else []
    current.append(entry)
    msg.trace = current
    db.commit()


def process_chat_message(tenant_id: uuid.UUID, conv_id: uuid.UUID, msg_id: uuid.UUID, raw_query: str):
    log.info("Starting async chat processing", msg_id=str(msg_id))
    with session_scope() as db:
        asst_msg = db.query(ConversationMessage).filter(ConversationMessage.id == msg_id).first()
        conv = db.query(Conversation).filter(
            Conversation.id == conv_id,
            Conversation.tenant_id == tenant_id
        ).first()

        if not asst_msg or not conv:
            log.error("Message or conversation not found", msg_id=str(msg_id))
            return

        # Initialise trace to empty list on the message row right away so the
        # polling endpoint sees a non-null trace even before the first stage lands.
        asst_msg.trace = []
        db.commit()

        try:
            # ------------------------------------------------------------------
            # 0. Route Classification
            # ------------------------------------------------------------------
            route_result = RouterService.classify_intent(raw_query)
            asst_msg.route = route_result.route
            log.info("Router classification", route=route_result.route, confidence=route_result.confidence)

            # Non-analytics routes get a single trace entry and exit early.
            if route_result.route == "greeting":
                asst_msg.content = RouterService.handle_greeting()
                asst_msg.status = "complete"
                if conv.title == "New Conversation":
                    conv.title = raw_query[:50]
                _append_trace(db, asst_msg, "responding", "Generating response...", "complete")
                return

            if route_result.route == "help":
                asst_msg.content = RouterService.handle_help()
                asst_msg.status = "complete"
                if conv.title == "New Conversation":
                    conv.title = raw_query[:50]
                _append_trace(db, asst_msg, "responding", "Generating response...", "complete")
                return

            if route_result.route == "conversation":
                asst_msg.content = RouterService.handle_conversation(raw_query)
                asst_msg.status = "complete"
                if conv.title == "New Conversation":
                    conv.title = raw_query[:50]
                _append_trace(db, asst_msg, "responding", "Generating response...", "complete")
                return

            # ------------------------------------------------------------------
            # Analytics pipeline — each stage commits its trace entry on completion
            # so the frontend sees real incremental progress via polling.
            # ------------------------------------------------------------------

            # Stage 1: parsing_question (router already ran; we record its outcome here)
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[0], "complete")

            # Stage 2: resolving_entities
            # Mark as in-progress early enough that a fast poll during this slow
            # LLM call still sees the stage landing.
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[1], "in_progress")

            context = ConversationContextManager.build_context(db, conv_id)
            intent  = NLUService.parse_intent(raw_query, context)
            asst_msg.intent = intent.model_dump()

            if intent.intent in ("clarify", "unknown"):
                asst_msg.content = "I'm not sure I understand. Could you clarify what metric or dimensions you are looking for?"
                asst_msg.status  = "complete"
                db.commit()
                return

            rag_hits   = RetrievalService.retrieve(query_text=raw_query, tenant_id=tenant_id, db=db)
            resolution = ResolverService.resolve_entities(db, tenant_id, intent, rag_hits=rag_hits)

            # Overwrite the in_progress entry with complete
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[1], "complete")

            if resolution.ambiguities:
                asst_msg.content          = f"I need some clarification. {resolution.ambiguities[0]}. Which one did you mean?"
                asst_msg.confidence_score = 0.5
                asst_msg.confidence_reason = "Ambiguous metric requested."
                asst_msg.status           = "complete"
                db.commit()
                return

            if not resolution.metric:
                asst_msg.content          = f"I couldn't find a metric matching '{intent.metric}'. Did you mean something else?"
                asst_msg.confidence_score = 0.0
                asst_msg.confidence_reason = "Unknown metric."
                asst_msg.status           = "complete"
                db.commit()
                return

            # Stage 3: planning_query
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[2], "in_progress")
            plan = PlannerService.generate_plan(db, intent, resolution, rag_hits=rag_hits)
            asst_msg.query_plan = plan.model_dump(mode='json')
            ValidationService.validate_plan(db, tenant_id, plan)
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[2], "complete")

            # Stage 4: generating_sql
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[3], "in_progress")
            compiled = CompilerService.compile_plan(db, tenant_id, plan)
            asst_msg.generated_sql = compiled.sql
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[3], "complete")

            # Stage 5: executing_query
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[4], "in_progress")
            result = ExecutorService.execute(db, compiled)
            asst_msg.execution_time_ms = result.execution_time_ms
            asst_msg.result_data       = {"columns": result.columns, "rows": result.rows}
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[4], "complete")

            # Confidence scoring (no stage for this — it's instant)
            confidence = 1.0
            reasons    = ["Exact metric match", "Approved joins"]
            if resolution.unresolved_terms:
                confidence -= 0.3 * len(resolution.unresolved_terms)
                reasons.append(f"Unresolved terms: {', '.join(resolution.unresolved_terms)}")
            asst_msg.confidence_score  = max(0.0, confidence)
            asst_msg.confidence_reason = " | ".join(reasons)

            # Stage 6: generating_insights
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[5], "in_progress")
            if len(result.rows) == 0:
                asst_msg.content           = "I ran the query, but no data was found for the requested filters."
                asst_msg.chart_recommendation = "kpi_card"
            else:
                explanation               = NLGenerator.generate_explanation(raw_query, plan, result)
                asst_msg.content          = explanation
                asst_msg.chart_recommendation = ChartRecommender.recommend(plan)
            _append_trace(db, asst_msg, *ANALYTICS_STAGES[5], "complete")

            asst_msg.status = "complete"
            if conv.title == "New Conversation":
                conv.title = raw_query[:50]

        except SQLSafetyError as e:
            # Record which stage was active when the error was raised by appending
            # an error entry — trace up to this point is already committed.
            _append_trace(db, asst_msg, "safety_check", "SQL safety validation", "error")
            asst_msg.error   = str(e)
            asst_msg.content = "The generated query was flagged by the safety validator and blocked."
            asst_msg.status  = "error"
        except JobTimeoutException:
            # Do NOT append trace here — we may not be able to commit under timeout.
            raise
        except Exception as e:
            traceback.print_exc()
            asst_msg.error   = str(e)
            asst_msg.content = "An error occurred while trying to answer your question."
            asst_msg.status  = "error"

        db.commit()
        log.info("Finished async chat processing", msg_id=str(msg_id), status=asst_msg.status)
