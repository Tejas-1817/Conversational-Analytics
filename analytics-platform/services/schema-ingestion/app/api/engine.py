import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_session
from app.engine.chart_recommender import ChartRecommender
from app.engine.compiler_service import CompilerService, SQLSafetyError
from app.engine.executor_service import ExecutorService
from app.engine.nl_generator import NLGenerator
from app.engine.context_manager import ConversationContextManager
from app.engine.nlu_service import NLUService
from app.engine.planner_service import PlannerService
from app.engine.resolver_service import ResolverService
from app.engine.retrieval_service import RetrievalService
from app.engine.router_service import RouterService
from app.engine.validation_service import ValidationService
from app.models import Conversation, ConversationMessage, User, ApprovedSQLExample, UserFeedback
from app.schemas_engine import ChatMessageOut, ChatRequest, ConversationOut, ApprovedExampleCreate, ApprovedExampleOut, UserFeedbackCreate, UserFeedbackOut
from app.audit import audit

router = APIRouter(prefix="/engine", tags=["engine"])

@router.post("/conversations", response_model=ConversationOut)
def create_conversation(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = Conversation(tenant_id=user.tenant_id, user_id=user.id, title="New Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    convs = db.scalars(select(Conversation).where(
        Conversation.tenant_id == user.tenant_id,
        Conversation.user_id == user.id
    ).order_by(Conversation.created_at.desc())).all()
    return convs

@router.get("/conversations/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.post("/conversations/{conv_id}/query", response_model=ChatMessageOut)
def ask_question(conv_id: uuid.UUID, req: ChatRequest, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. Save user message
    user_msg = ConversationMessage(
        conversation_id=conv.id,
        role="user",
        content=req.message
    )
    db.add(user_msg)
    db.commit()

    # Generate chat history context using the new ConversationContextManager
    context = ConversationContextManager.build_context(db, conv.id)

    # 2. Assistant Message (Placeholder)
    asst_msg = ConversationMessage(conversation_id=conv.id, role="assistant", content="")
    db.add(asst_msg)

    try:
        # Route Intent
        route_result = RouterService.classify_intent(req.message)
        asst_msg.route = route_result.route

        # We'll use trace to store the router result and any downstream execution
        asst_msg.trace = {
            "router": {
                "route": route_result.route,
                "confidence": route_result.confidence,
                "reason": route_result.reason
            }
        }

        if route_result.route == "greeting":
            asst_msg.content = RouterService.handle_greeting()
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        if route_result.route == "help":
            asst_msg.content = RouterService.handle_help()
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        if route_result.route == "conversation":
            asst_msg.content = RouterService.handle_conversation(req.message)
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        if route_result.route == "unknown":
            asst_msg.content = "I'm not sure how to help with that. Try asking a data question, or say 'help' for examples."
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        # Route == "analytics", continue with existing NLU pipeline
        intent = NLUService.parse_intent(req.message, context)
        asst_msg.intent = intent.model_dump()

        if intent.intent in ("clarify", "unknown"):
            asst_msg.content = "I'm not sure I understand. Could you clarify what metric or dimensions you are looking for?"
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        # RAG Retrieval
        rag_hits = RetrievalService.retrieve(
            query_text=req.message,
            tenant_id=user.tenant_id,
            db=db
        )

        # Entity Resolution
        resolution = ResolverService.resolve_entities(db, user.tenant_id, intent, rag_hits=rag_hits)

        # Handle Ambiguities
        if resolution.ambiguities:
            asst_msg.content = f"I need some clarification. {resolution.ambiguities[0]}. Which one did you mean?"
            asst_msg.confidence_score = 0.5
            asst_msg.confidence_reason = "Ambiguous metric requested."
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        if not resolution.metric:
            asst_msg.content = f"I couldn't find a metric matching '{intent.metric}'. Did you mean something else?"
            asst_msg.confidence_score = 0.0
            asst_msg.confidence_reason = "Unknown metric."
            db.commit()
            db.refresh(asst_msg)
            return asst_msg

        # Query Planning
        plan = PlannerService.generate_plan(db, intent, resolution, rag_hits=rag_hits)
        asst_msg.query_plan = plan.model_dump(mode='json')

        # Validation
        ValidationService.validate_plan(db, user.tenant_id, plan)

        # SQL Compilation
        compiled = CompilerService.compile_plan(db, user.tenant_id, plan)
        asst_msg.generated_sql = compiled.sql

        # Execution
        result = ExecutorService.execute(db, compiled)
        asst_msg.execution_time_ms = result.execution_time_ms
        asst_msg.result_data = {"columns": result.columns, "rows": result.rows}

        # Calculate Confidence
        confidence = 1.0
        reasons = ["Exact metric match", "Approved joins"]
        if resolution.unresolved_terms:
            confidence -= 0.3 * len(resolution.unresolved_terms)
            reasons.append(f"Unresolved terms: {', '.join(resolution.unresolved_terms)}")

        asst_msg.confidence_score = max(0.0, confidence)
        asst_msg.confidence_reason = " | ".join(reasons)

        # NL Generation & Chart Recommendation
        if len(result.rows) == 0:
            asst_msg.content = "I ran the query, but no data was found for the requested filters."
            asst_msg.chart_recommendation = "kpi_card"
        else:
            explanation = NLGenerator.generate_explanation(req.message, plan, result)
            asst_msg.content = explanation
            asst_msg.chart_recommendation = ChartRecommender.recommend(plan)

        # Update title if it's the first query
        if conv.title == "New Conversation":
            conv.title = req.message[:50]

    except SQLSafetyError as e:
        asst_msg.error = str(e)
        asst_msg.content = "The generated query was flagged by the safety validator and blocked."
    except Exception as e:
        import traceback
        traceback.print_exc()
        asst_msg.error = str(e)
        asst_msg.content = "An error occurred while trying to answer your question."

    db.commit()
    db.refresh(asst_msg)

    return asst_msg

@router.post("/conversations/{conv_id}/messages/{msg_id}/feedback", response_model=UserFeedbackOut)
def submit_feedback(
    conv_id: uuid.UUID,
    msg_id: uuid.UUID,
    feedback: UserFeedbackCreate,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # Verify conversation belongs to user
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    msg = db.scalar(select(ConversationMessage).where(
        ConversationMessage.id == msg_id,
        ConversationMessage.conversation_id == conv.id
    ))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    if msg.role != "assistant" or not msg.generated_sql:
        raise HTTPException(status_code=400, detail="Feedback can only be provided for assistant messages with SQL")

    fb = UserFeedback(
        message_id=msg.id,
        is_positive=feedback.is_positive,
        correction=feedback.correction
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb

@router.post("/examples/approve", response_model=ApprovedExampleOut)
def approve_example(
    req: ApprovedExampleCreate,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # Verify the message
    msg = db.scalar(
        select(ConversationMessage)
        .join(Conversation)
        .where(
            ConversationMessage.id == req.message_id,
            Conversation.tenant_id == user.tenant_id
        )
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    if not msg.generated_sql:
        raise HTTPException(status_code=400, detail="Message does not contain SQL")

    # Get the original question (the user message before this assistant message)
    # Since messages are ordered by created_at, find the most recent user message in this conversation
    # that is before this message
    user_msg = db.scalar(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == msg.conversation_id,
            ConversationMessage.role == "user",
            ConversationMessage.created_at <= msg.created_at
        )
        .order_by(ConversationMessage.created_at.desc())
    )
    if not user_msg:
        raise HTTPException(status_code=400, detail="Could not find corresponding user question")

    example = ApprovedSQLExample(
        tenant_id=user.tenant_id,
        question=user_msg.content,
        generated_sql=msg.generated_sql,
        approved_by=user.id
    )
    db.add(example)
    db.commit()
    db.refresh(example)

    audit(
        db,
        tenant_id=user.tenant_id,
        entity_type="approved_sql_example",
        entity_id=example.id,
        action="EXAMPLE_APPROVED",
        actor=user.email,
        after={"question": example.question, "generated_sql": example.generated_sql}
    )
    db.commit()
    
    return example
