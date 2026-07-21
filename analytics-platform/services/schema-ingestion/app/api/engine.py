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

from rq import Queue
from redis import Redis
from app.config import get_settings
from app.tasks.chat_tasks import process_chat_message

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



    db.commit()
    db.refresh(asst_msg)

    # Enqueue background task
    try:
        redis_conn = Redis.from_url(get_settings().redis_url)
        q = Queue("chat", connection=redis_conn)
        q.enqueue(
            process_chat_message,
            args=(user.tenant_id, conv_id, asst_msg.id, req.message),
            job_timeout=600  # 10 minutes timeout
        )
    except Exception as e:
        import structlog
        structlog.get_logger().error("Failed to enqueue chat task", error=str(e))
        asst_msg.status = "error"
        asst_msg.content = "Failed to start processing task. Please try again."
        db.commit()

    return asst_msg

@router.get("/conversations/{conv_id}/messages/{msg_id}", response_model=ChatMessageOut)
def get_message_status(conv_id: uuid.UUID, msg_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
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

    # Layer C backstop: if message is still "processing" but older than
    # job_timeout (600s) + grace period (60s), treat it as timed out.
    # This guarantees the UI never spins forever regardless of how the worker died.
    if msg.status == "processing":
        from datetime import datetime, timezone
        JOB_TIMEOUT_PLUS_GRACE = 660  # 600s timeout + 60s grace
        age_seconds = (datetime.now(timezone.utc) - msg.created_at).total_seconds()
        if age_seconds > JOB_TIMEOUT_PLUS_GRACE:
            msg.status = "error"
            msg.content = "The request timed out. Please try again with a simpler question."
            msg.error = f"Server-side staleness backstop: message was processing for {int(age_seconds)}s"
            db.commit()

    return msg

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
