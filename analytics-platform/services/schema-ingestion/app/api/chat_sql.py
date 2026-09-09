from __future__ import annotations

import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.chat_sql.chat_service import ChatService, SourceNotFoundError
from app.chat_sql.llm_provider import LLMTimeoutError, LLMUnavailableError
from app.db import get_session
from app.models import User


log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["ask-ai-sql"])
chat_service = ChatService()

RequestMode = Literal["auto", "data", "strategy", "hybrid"]
ResolvedIntent = Literal["data", "strategy", "hybrid"]


class SQLQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    source_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    domain_id: uuid.UUID | None = None
    mode: RequestMode = "auto"


class SQLQueryResponse(BaseModel):
    success: bool
    intent: ResolvedIntent
    conversation_id: str | None = None
    question: str

    answer: str
    answer_markdown: str
    summary: str

    sql: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    result_data: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    column_types: dict[str, str] = Field(default_factory=dict)

    row_count: int = 0
    column_count: int = 0
    data_truncated: bool = False

    visualization: str = "text"
    title: str
    recommended_visualization: dict[str, Any] = Field(default_factory=dict)
    follow_up_questions: list[str] = Field(default_factory=list)

    execution_time_ms: float = 0.0
    generated_at: str
    database: str


@router.post("/sql", response_model=SQLQueryResponse)
def generate_sql_from_question(
    req: SQLQueryRequest,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return chat_service.process_text_to_sql(
            question=req.question.strip(),
            source_id=req.source_id,
            conversation_id=req.conversation_id,
            domain_id=req.domain_id,
            requested_mode=req.mode,
            db_session=db,
            user=user,
        )

    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI model timed out while processing the request.",
        ) from exc

    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI model is currently unavailable.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        log.exception(
            "api_chat_sql_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The analytics request could not be completed.",
        ) from exc