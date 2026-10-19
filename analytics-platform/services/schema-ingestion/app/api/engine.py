import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_user_has_source_access, verify_user_has_domain_access
from app.db import get_session, session_scope
from app.embeddings.feedback_job import embed_approved_examples
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
from app.schemas_engine import ChatMessageOut, ChatRequest, ConversationOut, ConversationCreate, ConversationUpdate, ApprovedExampleCreate, ApprovedExampleOut, UserFeedbackCreate, UserFeedbackOut
from app.audit import audit
from app.engine.query_intelligence_service import QueryIntelligenceService
from app.schemas_engine import QueryIntelligenceRequest

from rq import Queue
from redis import Redis
from app.config import get_settings
from app.tasks.chat_tasks import process_chat_message

router = APIRouter(prefix="/engine", tags=["engine"])

@router.post("/conversations", response_model=ConversationOut)
def create_conversation(req: ConversationCreate | None = None, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if req and req.source_id:
        verify_user_has_source_access(db, user, req.source_id)
    if req and req.domain_id:
        from app.models import Domain
        domain = db.query(Domain).filter(Domain.id == req.domain_id, Domain.tenant_id == user.tenant_id).first()
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        verify_user_has_domain_access(db, user, domain)
    conv = Conversation(
        tenant_id=user.tenant_id,
        user_id=user.id,
        title=req.title if req and req.title else "New Conversation",
        source_id=req.source_id if req else None,
        domain_id=req.domain_id if req else None,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.patch("/conversations/{conv_id}", response_model=ConversationOut)
def update_conversation(conv_id: uuid.UUID, req: ConversationUpdate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user.role != "ADMIN" and conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if req.title is not None:
        conv.title = req.title
    if req.source_id is not None:
        verify_user_has_source_access(db, user, req.source_id)
        conv.source_id = req.source_id
    if req.domain_id is not None:
        from app.models import Domain
        domain = db.query(Domain).filter(Domain.id == req.domain_id, Domain.tenant_id == user.tenant_id).first()
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        verify_user_has_domain_access(db, user, domain)
        conv.domain_id = req.domain_id
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    convs = db.scalars(select(Conversation).where(
        Conversation.tenant_id == user.tenant_id,
        Conversation.user_id == user.id
    ).order_by(Conversation.updated_at.desc())).all()
    return convs

@router.get("/conversations/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user.role != "ADMIN" and conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user.role != "ADMIN" and conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return None


@router.post("/conversations/{conv_id}/query", response_model=ChatMessageOut)
def ask_question(conv_id: uuid.UUID, req: ChatRequest, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    conv = db.scalar(select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.tenant_id == user.tenant_id
    ))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user.role != "ADMIN" and conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.source_id:
        verify_user_has_source_access(db, user, conv.source_id)
    if conv.domain_id:
        from app.models import Domain
        domain = db.query(Domain).filter(Domain.id == conv.domain_id, Domain.tenant_id == user.tenant_id).first()
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        verify_user_has_domain_access(db, user, domain)

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
    if user.role != "ADMIN" and conv.user_id != user.id:
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
    background_tasks: BackgroundTasks,
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

    # --- Automated Learning & Self-Healing ---
    if feedback.is_positive:
        # Locate corresponding user prompt
        user_msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conv.id,
                ConversationMessage.role == "user",
                ConversationMessage.created_at <= msg.created_at
            ).order_by(ConversationMessage.created_at.desc())
        )
        if user_msg:
            existing = db.scalar(
                select(ApprovedSQLExample).where(
                    ApprovedSQLExample.tenant_id == user.tenant_id,
                    ApprovedSQLExample.generated_sql == msg.generated_sql
                )
            )
            if not existing:
                example = ApprovedSQLExample(
                    tenant_id=user.tenant_id,
                    question=user_msg.content,
                    generated_sql=msg.generated_sql,
                    approved_by=user.id
                )
                db.add(example)
                db.commit()
                background_tasks.add_task(_embed_approved_examples_tenant, str(user.tenant_id))
    else:
        # Negative feedback: If this query was previously learned, delete it so it stops poisoning RAG
        bad_example = db.scalar(
            select(ApprovedSQLExample).where(
                ApprovedSQLExample.tenant_id == user.tenant_id,
                ApprovedSQLExample.generated_sql == msg.generated_sql
            )
        )
        if bad_example:
            db.delete(bad_example)
            db.commit()
            background_tasks.add_task(_embed_approved_examples_tenant, str(user.tenant_id))

    db.refresh(fb)
    return fb

@router.delete("/conversations/{conv_id}/messages/{msg_id}/feedback")
def remove_feedback(
    conv_id: uuid.UUID,
    msg_id: uuid.UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # 1. Verify conversation belongs to this tenant
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.tenant_id == user.tenant_id
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. Find and delete existing feedback entries for this message
    feedbacks = db.scalars(
        select(UserFeedback).where(UserFeedback.message_id == msg_id)
    ).all()

    for fb in feedbacks:
        db.delete(fb)
    db.commit()

    return {"status": "feedback_removed", "message_id": str(msg_id)}

    
def _embed_approved_examples_tenant(tenant_id: str) -> None:
    """Safely runs the embedding job in the background with a fresh DB session."""
    with session_scope() as db:
        embed_approved_examples(tenant_id, db)

@router.post("/examples/approve", response_model=ApprovedExampleOut)
def approve_example(
    req: ApprovedExampleCreate,
    background_tasks: BackgroundTasks,          # <--- 1. ADD THIS PARAMETER
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

    background_tasks.add_task(_embed_approved_examples_tenant, str(user.tenant_id))
    
    return example

@router.post("/examples/unapprove")
def unapprove_example(
    req: ApprovedExampleCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # 1. Verify the message belongs to this tenant
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

    # 2. Find the approved example in the database
    example = db.scalar(
        select(ApprovedSQLExample).where(
            ApprovedSQLExample.tenant_id == user.tenant_id,
            ApprovedSQLExample.generated_sql == msg.generated_sql
        )
    )
    if example:
        # 3. Log audit event and delete from Postgres
        audit(
            db,
            tenant_id=user.tenant_id,
            entity_type="approved_sql_example",
            entity_id=example.id,
            action="EXAMPLE_UNAPPROVED",
            actor=user.email,
            after={"question": example.question, "generated_sql": example.generated_sql}
        )
        db.delete(example)
        db.commit()

        # 4. Re-index ChromaDB in the background without this query
        background_tasks.add_task(_embed_approved_examples_tenant, str(user.tenant_id))

    return {"status": "unapproved", "message_id": str(req.message_id)}


@router.post("/{tenant_id}/intelligence/query")
def query_intelligence(tenant_id: uuid.UUID, req: QueryIntelligenceRequest, db: Session = Depends(get_session)):
    """Intelligently converts natural language to SQL and executes it via the semantic layer context."""
    return QueryIntelligenceService.answer_question(db, tenant_id, req.question)

