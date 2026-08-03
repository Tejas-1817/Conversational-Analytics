"""Ask AI Chat SQL REST API Controller.

Exposes POST /api/v1/chat/sql for natural language to PostgreSQL SQL generation.
"""
from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.chat_sql.chat_service import ChatService
from app.db import get_session
from app.models import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["ask-ai-sql"])

chat_service = ChatService()


class SQLQueryRequest(BaseModel):
    question: str = Field(..., example="How many customers currently have ACTIVE status?")
    conversation_id: Optional[str] = None


class SQLQueryResponse(BaseModel):
    conversation_id: Optional[str] = None
    question: str
    sql: str
    answer: Optional[str] = None
    result_data: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = 0
    execution_time_ms: Optional[float] = 0.0
    generated_at: str
    database: str


@router.post("/sql", response_model=SQLQueryResponse)
def generate_sql_from_question(
    req: SQLQueryRequest,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generates PostgreSQL SQL query from natural language question using connected DB schema."""
    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    try:
        return chat_service.process_text_to_sql(
            question=req.question.strip(),
            conversation_id=req.conversation_id,
            db_session=db,
            user=user,
        )
    except Exception as exc:
        log.error("api_chat_sql_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SQL query: {exc}"
        )
