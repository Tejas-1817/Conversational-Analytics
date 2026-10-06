"""FastAPI endpoints for Code Intelligence (GraphRAG over repositories)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import User, Conversation, ConversationMessage


import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.code_intel.graph_writer import GraphWriter
from app.code_intel.graphrag_query import GraphRAGQueryEngine
from app.code_intel.pipeline import CodeIntelPipeline, get_pipeline_status
from app.models import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/code-repos", tags=["code-intelligence"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConnectRepoRequest(BaseModel):
    url: str = Field(..., description="Git clone URL (HTTPS or SSH)", example="https://github.com/fastapi/fastapi.git")
    name: str | None = Field(default=None, description="Optional custom name for repository")
    branch: str = Field(default="main", description="Git branch to clone/index")


class ConnectRepoResponse(BaseModel):
    repo_id: str
    status: str
    message: str


class RepoStatusResponse(BaseModel):
    repo_id: str
    status: str
    total_files: int = 0
    processed_files: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0
    error_message: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)


class CodeQueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about codebase or architecture", example="How does request authentication and token verification work?")
    n_chunks: int = Field(default=5, description="Number of vector code chunks to retrieve")
    conversation_id: str | None = Field(default=None, description="Active conversation UUID to persist messages into")

class CodeQueryResponse(BaseModel):
    conversation_id: str | None = None
    query: str
    repo_id: str
    answer: str
    referenced_files: list[str] = Field(default_factory=list)
    referenced_symbols: list[str] = Field(default_factory=list)
    graph_facts: list[str] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)


class RepoSummary(BaseModel):
    repo_id: str
    name: str
    url: str
    last_ingested_at: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/connect", response_model=ConnectRepoResponse, status_code=status.HTTP_202_ACCEPTED)
def connect_and_ingest_repo(
    payload: ConnectRepoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> ConnectRepoResponse:
    """Connect a Git repository and start the background AST parsing, Graph building, and Vector embedding pipeline."""
    repo_id = str(uuid.uuid4())
    tenant_id = str(current_user.tenant_id)

    log.info("triggering_repo_connect", repo_id=repo_id, url=payload.url, tenant_id=tenant_id)

    def _execute_ingestion():
        try:
            pipeline = CodeIntelPipeline()
            pipeline.run_pipeline(
                tenant_id=tenant_id,
                repo_url=payload.url,
                repo_name=payload.name,
                branch=payload.branch,
                repo_id=repo_id,
            )
        except Exception as exc:
            log.error("background_repo_ingestion_error", repo_id=repo_id, error=str(exc))

    background_tasks.add_task(_execute_ingestion)

    return ConnectRepoResponse(
        repo_id=repo_id,
        status="queued",
        message=f"Repository ingestion started for {payload.url}.",
    )


@router.get("/{repo_id}/status", response_model=RepoStatusResponse)
def get_repo_ingestion_status(
    repo_id: str,
    current_user: User = Depends(get_current_user),
) -> RepoStatusResponse:
    """Check the real-time ingestion progress or completion stats for a repository."""
    in_memory = get_pipeline_status(repo_id)
    if in_memory:
        return RepoStatusResponse(
            repo_id=in_memory.repo_id,
            status=in_memory.status,
            total_files=in_memory.total_files,
            processed_files=in_memory.processed_files,
            total_chunks=in_memory.total_chunks,
            embedded_chunks=in_memory.embedded_chunks,
            error_message=in_memory.error_message,
            stats=in_memory.stats,
        )

    # If not currently running in-memory, query Neo4j for repository node
    try:
        gw = GraphWriter()
        with gw._session() as session:
            res = session.run(
                "MATCH (r:Repository {repo_id: $repo_id}) RETURN r.name AS name, r.url AS url",
                repo_id=repo_id,
            ).single()

            if not res:
                raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

            stats = gw.get_stats(repo_id)
            return RepoStatusResponse(
                repo_id=repo_id,
                status="completed",
                stats={"repo_id": repo_id, "name": res["name"], "url": res["url"], "graph": stats},
            )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("error_fetching_repo_status", repo_id=repo_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to fetch status: {exc}")


@router.post("/{repo_id}/sync", response_model=ConnectRepoResponse, status_code=status.HTTP_202_ACCEPTED)
def sync_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> ConnectRepoResponse:
    """Pull latest Git changes and re-index the repository in Neo4j and ChromaDB."""
    tenant_id = str(current_user.tenant_id)

    # Fetch repository URL from Neo4j
    gw = GraphWriter()
    repo_url = None
    repo_name = None
    with gw._session() as session:
        record = session.run(
            "MATCH (r:Repository {repo_id: $repo_id}) RETURN r.name AS name, r.url AS url",
            repo_id=repo_id,
        ).single()
        if record:
            repo_url = record["url"]
            repo_name = record["name"]

    if not repo_url:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    def _execute_sync():
        try:
            pipeline = CodeIntelPipeline()
            pipeline.run_pipeline(
                tenant_id=tenant_id,
                repo_url=repo_url,
                repo_name=repo_name,
                repo_id=repo_id,
            )
        except Exception as exc:
            log.error("background_repo_sync_error", repo_id=repo_id, error=str(exc))

    background_tasks.add_task(_execute_sync)

    return ConnectRepoResponse(
        repo_id=repo_id,
        status="queued",
        message=f"Sync and re-indexing queued for repository {repo_id}.",
    )


@router.post("/{repo_id}/query", response_model=CodeQueryResponse)
def query_repository_code(
    repo_id: str,
    payload: CodeQueryRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CodeQueryResponse:
    """Execute a GraphRAG question against the repository knowledge graph and vector index."""
    tenant_id = str(current_user.tenant_id)
    query_engine = GraphRAGQueryEngine()

    try:
        result = query_engine.query(
            question=payload.question,
            repo_id=repo_id,
            tenant_id=tenant_id,
            n_chunks=payload.n_chunks,
        )
        # 2. Find or create the conversation record in PostgreSQL
        conv = None
        if payload.conversation_id:
            try:
                conv_uuid = uuid.UUID(payload.conversation_id)
                conv = db.scalar(
                    select(Conversation).where(
                        Conversation.id == conv_uuid,
                        Conversation.tenant_id == current_user.tenant_id,
                    )
                )
            except Exception:
                conv = None
        if not conv:
            conv = Conversation(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                title=payload.question[:60] if payload.question else "Code Intelligence Chat",
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
        # 3. Persist User Message
        user_msg = ConversationMessage(
            conversation_id=conv.id,
            role="user",
            content=payload.question,
            status="complete",
        )
        db.add(user_msg)
        # 4. Persist Assistant Response with Code Intelligence Metadata
        asst_msg = ConversationMessage(
            conversation_id=conv.id,
            role="assistant",
            content=result.answer,
            status="complete",
            route="code_intel",
            result_data={
                "is_code_intel": True,
                "repo_id": repo_id,
                "referenced_files": result.referenced_files,
                "referenced_symbols": result.referenced_symbols,
                "graph_facts": result.graph_facts,
                "retrieved_chunks": result.retrieved_chunks,
            },
        )
        db.add(asst_msg)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()

        return CodeQueryResponse(
            conversation_id=str(conv.id),
            query=result.query,
            repo_id=result.repo_id,
            answer=result.answer,
            referenced_files=result.referenced_files,
            referenced_symbols=result.referenced_symbols,
            graph_facts=result.graph_facts,
            retrieved_chunks=result.retrieved_chunks,
        )
    except Exception as exc:
        log.error("code_query_failed", repo_id=repo_id, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Code query failed: {exc}")


@router.get("", response_model=list[RepoSummary])
def list_repositories(
    current_user: User = Depends(get_current_user),
) -> list[RepoSummary]:
    """List all ingested and in-progress code repositories."""
    from app.code_intel.pipeline import _INGESTION_STATUS_STORE
    gw = GraphWriter()
    repos: list[RepoSummary] = []
    seen_ids = set()

    try:
        with gw._session() as session:
            results = session.run(
                """
                MATCH (r:Repository)
                RETURN r.repo_id AS repo_id, r.name AS name, r.url AS url,
                       toString(r.last_ingested_at) AS last_ingested_at
                ORDER BY r.name
                """
            )
            for rec in results:
                rid = rec["repo_id"] or ""
                seen_ids.add(rid)
                repos.append(RepoSummary(
                    repo_id=rid,
                    name=rec["name"] or "",
                    url=rec["url"] or "",
                    last_ingested_at=rec["last_ingested_at"],
                ))
    except Exception as exc:
        log.warning("error_listing_repos_from_neo4j", error=str(exc))

    # Also include any repos currently cloning/indexing in the background
    for rid, prog in _INGESTION_STATUS_STORE.items():
        if rid not in seen_ids:
            repos.append(RepoSummary(
                repo_id=rid,
                name=getattr(prog, "name", "Git Repository"),
                url=getattr(prog, "url", ""),
                last_ingested_at=None,
            ))

    return repos



@router.delete("/{repo_id}", status_code=status.HTTP_200_OK)
def delete_repository(
    repo_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a repository graph from Neo4j and code vectors from ChromaDB."""
    tenant_id = str(current_user.tenant_id)

    try:
        gw = GraphWriter()
        gw.clear_repository(repo_id)

        from app.code_intel.vector_writer import VectorWriter
        vw = VectorWriter()
        vw.delete_repo_chunks(tenant_id=tenant_id, repo_id=repo_id)

        log.info("repository_deleted", repo_id=repo_id)
        return {"repo_id": repo_id, "status": "deleted", "message": "Repository removed from graph and vector store."}
    except Exception as exc:
        log.error("error_deleting_repo", repo_id=repo_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to delete repository: {exc}")
