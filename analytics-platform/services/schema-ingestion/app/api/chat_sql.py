from __future__ import annotations

import asyncio
import json
from fastapi.responses import StreamingResponse

import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_user_has_source_access, verify_user_has_domain_access
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
    verify_user_has_source_access(db, user, req.source_id)
    if req.domain_id:
        from app.models import Domain
        domain = db.query(Domain).filter(Domain.id == req.domain_id, Domain.tenant_id == user.tenant_id).first()
        if not domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
        verify_user_has_domain_access(db, user, domain)
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

@router.post("/sql/stream")
async def generate_sql_from_question_stream(
    req: SQLQueryRequest,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Stream stages, tokens, and final analytical payload over Server-Sent Events (SSE)."""
    # 1. Enforce strict multi-tenant access control (same as standard endpoint)
    verify_user_has_source_access(db, user, req.source_id)
    if req.domain_id:
        from app.models import Domain
        domain = db.query(Domain).filter(Domain.id == req.domain_id, Domain.tenant_id == user.tenant_id).first()
        if not domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
        verify_user_has_domain_access(db, user, domain)

    async def event_generator():
        # Event 1: Initial status update (sent to UI immediately in ~20ms)
        yield f"data: {json.dumps({'type': 'status', 'stage': 'planning', 'message': 'Analyzing question & schema context...'})}\n\n"
        await asyncio.sleep(0.05)

        # Event 2: Execution stage status
        yield f"data: {json.dumps({'type': 'status', 'stage': 'executing', 'message': 'Generating & running SQL on warehouse...'})}\n\n"
        await asyncio.sleep(0.05)

        try:
            # Run the heavy query in a worker thread so the server's async event loop never blocks
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: chat_service.process_text_to_sql(
                    question=req.question.strip(),
                    source_id=req.source_id,
                    conversation_id=req.conversation_id,
                    domain_id=req.domain_id,
                    requested_mode=req.mode,
                    db_session=db,
                    user=user,
                ),
            )

            # Event 3: If SQL was generated, send it immediately
            if result.get("sql"):
                yield f"data: {json.dumps({'type': 'sql', 'sql': result['sql']})}\n\n"

            # Event 4: Line-by-line progression like ChatGPT
            answer_text = result.get("answer_markdown") or result.get("answer") or ""
            lines = answer_text.splitlines(keepends=True)

            for line in lines:
                # If it's an empty line (paragraph spacer), send it quickly
                if not line.strip():
                    yield f"data: {json.dumps({'type': 'token', 'delta': line})}\n\n"
                    await asyncio.sleep(0.001)
                    continue

                # Stream in fast 2-word phrases (cuts backend streaming time by 60%)
                words = line.split(" ")
                chunk_size = 2
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i : i + chunk_size])
                    suffix = " " if (i + chunk_size) < len(words) else ""
                    yield f"data: {json.dumps({'type': 'token', 'delta': chunk + suffix})}\n\n"
                    await asyncio.sleep(0.002)

                # Crisp micro-pause between lines
                await asyncio.sleep(0.002)



            # Event 5: Complete payload (contains full rows, columns, charts, follow-ups)
            yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"

        except Exception as exc:
            log.exception("streaming_chat_sql_failed", error=str(exc))
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disables proxy buffering so chunks reach the browser instantly
        },
    )
