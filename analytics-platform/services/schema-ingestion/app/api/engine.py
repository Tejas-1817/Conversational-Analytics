import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_session
from app.api.deps import get_current_user
from app.models import User, Conversation, ConversationMessage
from app.schemas_engine import ChatRequest, ChatMessageOut, ConversationOut
from app.engine.nlu_service import NLUService
from app.engine.resolver_service import ResolverService
from app.engine.planner_service import PlannerService
from app.engine.validation_service import ValidationService
from app.engine.compiler_service import CompilerService, SQLSafetyError
from app.engine.executor_service import ExecutorService
from app.engine.nl_generator import NLGenerator
from app.engine.chart_recommender import ChartRecommender
from app.engine.router_service import RouterService

router = APIRouter(prefix="/engine", tags=["engine"])

@router.post("/conversations", response_model=ConversationOut)
def create_conversation(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = Conversation(tenant_id=user.tenant_id, user_id=user.id, title="New Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversations", response_model=List[ConversationOut])
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
    
    # Generate chat history string
    history = "\n".join([f"{m.role}: {m.content}" for m in conv.messages])

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
        intent = NLUService.parse_intent(req.message, history)
        asst_msg.intent = intent.model_dump()
        
        if intent.intent in ("clarify", "unknown"):
            asst_msg.content = "I'm not sure I understand. Could you clarify what metric or dimensions you are looking for?"
            db.commit()
            db.refresh(asst_msg)
            return asst_msg
            
        # Entity Resolution
        resolution = ResolverService.resolve_entities(db, user.tenant_id, intent)
        
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
        plan = PlannerService.generate_plan(intent, resolution)
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
        asst_msg.error = str(e)
        asst_msg.content = "An error occurred while trying to answer your question."
        
    db.commit()
    db.refresh(asst_msg)
    
    return asst_msg
