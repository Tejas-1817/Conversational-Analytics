import uuid
import traceback
import structlog
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

log = structlog.get_logger()

def process_chat_message(tenant_id: uuid.UUID, conv_id: uuid.UUID, msg_id: uuid.UUID, raw_query: str):
    log.info("Starting async chat processing", msg_id=str(msg_id))
    with session_scope() as db:
        # Fetch the message
        asst_msg = db.query(ConversationMessage).filter(ConversationMessage.id == msg_id).first()
        conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.tenant_id == tenant_id).first()
        
        if not asst_msg or not conv:
            log.error("Message or conversation not found", msg_id=str(msg_id))
            return

        try:
            # 1. Generate Context
            context = ConversationContextManager.build_context(db, conv_id)
            
            # 2. NLU
            intent = NLUService.parse_intent(raw_query, context)
            asst_msg.intent = intent.model_dump()
            
            if intent.intent in ("clarify", "unknown"):
                asst_msg.content = "I'm not sure I understand. Could you clarify what metric or dimensions you are looking for?"
                asst_msg.status = "complete"
                db.commit()
                return

            # 3. RAG Retrieval
            rag_hits = RetrievalService.retrieve(
                query_text=raw_query,
                tenant_id=tenant_id,
                db=db
            )

            # 4. Entity Resolution
            resolution = ResolverService.resolve_entities(db, tenant_id, intent, rag_hits=rag_hits)

            if resolution.ambiguities:
                asst_msg.content = f"I need some clarification. {resolution.ambiguities[0]}. Which one did you mean?"
                asst_msg.confidence_score = 0.5
                asst_msg.confidence_reason = "Ambiguous metric requested."
                asst_msg.status = "complete"
                db.commit()
                return

            if not resolution.metric:
                asst_msg.content = f"I couldn't find a metric matching '{intent.metric}'. Did you mean something else?"
                asst_msg.confidence_score = 0.0
                asst_msg.confidence_reason = "Unknown metric."
                asst_msg.status = "complete"
                db.commit()
                return

            # 5. Planning
            plan = PlannerService.generate_plan(db, intent, resolution, rag_hits=rag_hits)
            asst_msg.query_plan = plan.model_dump(mode='json')

            # 6. Validation
            ValidationService.validate_plan(db, tenant_id, plan)

            # 7. Compilation
            compiled = CompilerService.compile_plan(db, tenant_id, plan)
            asst_msg.generated_sql = compiled.sql

            # 8. Execution
            result = ExecutorService.execute(db, compiled)
            asst_msg.execution_time_ms = result.execution_time_ms
            asst_msg.result_data = {"columns": result.columns, "rows": result.rows}

            # 9. Confidence Scoring
            confidence = 1.0
            reasons = ["Exact metric match", "Approved joins"]
            if resolution.unresolved_terms:
                confidence -= 0.3 * len(resolution.unresolved_terms)
                reasons.append(f"Unresolved terms: {', '.join(resolution.unresolved_terms)}")

            asst_msg.confidence_score = max(0.0, confidence)
            asst_msg.confidence_reason = " | ".join(reasons)

            # 10. Final generation
            if len(result.rows) == 0:
                asst_msg.content = "I ran the query, but no data was found for the requested filters."
                asst_msg.chart_recommendation = "kpi_card"
            else:
                explanation = NLGenerator.generate_explanation(raw_query, plan, result)
                asst_msg.content = explanation
                asst_msg.chart_recommendation = ChartRecommender.recommend(plan)

            asst_msg.status = "complete"
            
            # Update title
            if conv.title == "New Conversation":
                conv.title = raw_query[:50]

        except SQLSafetyError as e:
            asst_msg.error = str(e)
            asst_msg.content = "The generated query was flagged by the safety validator and blocked."
            asst_msg.status = "error"
        except Exception as e:
            traceback.print_exc()
            asst_msg.error = str(e)
            asst_msg.content = "An error occurred while trying to answer your question."
            asst_msg.status = "error"

        db.commit()
        log.info("Finished async chat processing", msg_id=str(msg_id), status=asst_msg.status)
