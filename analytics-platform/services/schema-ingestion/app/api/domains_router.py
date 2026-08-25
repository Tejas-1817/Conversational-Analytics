"""Domain Knowledge Base API Router.

Supports domain management, database connection & table scoping, document processing (PDF/DOCX/CSV/XLSX),
local file storage, LLM term extraction, and plain-English RAG query grounding.
"""
from __future__ import annotations

import os
import hashlib
import uuid
import json
import structlog
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, Domain, DomainTable, DomainDocument, DomainTerm, DataSource, TableMeta, ColumnMeta, Relationship
from app.api.deps import get_current_user, Permission, require_permission 
from sqlalchemy.orm import aliased
from app.audit import AuditEvent, audit
# from app.security.auth import require_permission, Permission, AuditEvent, audit
from app.services.domain_parser import parse_document, chunk_text
from app.services.domain_extractor import extract_domain_terms
from app.embeddings.chroma_store import ChromaStore, EmbeddedObject
from app.embeddings.registry import get_embedding_provider
from app.chat_sql.llm_provider import LLMProvider

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/domains", tags=["domains"])

STORAGE_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "domains"))

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class DomainCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    source_id: Optional[uuid.UUID] = None
    table_ids: List[uuid.UUID] = Field(default_factory=list)


class TableSummary(BaseModel):
    id: uuid.UUID
    table_name: str
    row_count: Optional[int] = None
    relationships: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    id: uuid.UUID
    file_name: str
    file_type: str
    file_size: int
    chunk_count: int = 0
    processing_status: str = "pending"
    created_at: datetime


class TermSummary(BaseModel):
    id: uuid.UUID
    term: str
    definition: str
    synonyms: List[str]
    category: Optional[str] = None


class DomainOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    source_id: Optional[uuid.UUID] = None
    source_name: Optional[str] = None
    table_count: int = 0
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class DomainDetailOut(DomainOut):
    tables: List[TableSummary] = Field(default_factory=list)
    documents: List[DocumentSummary] = Field(default_factory=list)
    terms: List[TermSummary] = Field(default_factory=list)


def _build_table_summary(session: Session, tm: TableMeta) -> TableSummary:
    columns = session.query(ColumnMeta).filter(ColumnMeta.table_id == tm.id).order_by(ColumnMeta.ordinal_position).all()
    
    # Extract explicitly tagged measures and dimensions
    metrics = [c.column_name for c in columns if c.role and str(c.role).lower() in ("measure", "metric")]
    dimensions = [c.column_name for c in columns if c.role and str(c.role).lower() in ("dimension", "attribute")]
    
    # Fallback to column types if no semantic roles are tagged yet
    if not metrics and not dimensions:
        num_types = ("int", "integer", "bigint", "smallint", "numeric", "decimal", "float", "double", "real", "number")
        for c in columns:
            dt = (c.data_type or "").lower()
            if any(nt in dt for nt in num_types) and not c.is_primary_key and not c.column_name.endswith("_id"):
                metrics.append(c.column_name)
            else:
                dimensions.append(c.column_name)

    # Relationships
    relationships = []
    try:
        from_col = aliased(ColumnMeta)
        to_col = aliased(ColumnMeta)
        to_table = aliased(TableMeta)
        
        rels = session.query(from_col.column_name, to_table.table_name, to_col.column_name)\
            .select_from(Relationship)\
            .join(from_col, Relationship.from_column_id == from_col.id)\
            .join(to_col, Relationship.to_column_id == to_col.id)\
            .join(to_table, to_col.table_id == to_table.id)\
            .filter(from_col.table_id == tm.id)\
            .all()
        relationships = [f"{r[0]} -> {r[1]}({r[2]})" for r in rels]
    except Exception as e:
        log.warn("Failed to fetch relationships", error=str(e), table_id=str(tm.id))

    return TableSummary(
        id=tm.id,
        table_name=tm.table_name,
        row_count=tm.row_count,
        relationships=relationships,
        metrics=metrics,
        dimensions=dimensions,
    )


class DomainQueryPayload(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class DomainQueryHit(BaseModel):
    text: str
    distance: float
    metadata: dict


class DomainQueryResponse(BaseModel):
    answer: str
    sources: List[DomainQueryHit]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[DomainOut])
def list_domains(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[DomainOut]:
    """List all domains for current tenant with document & table counts."""
    try:
        domains = (
            session.query(Domain)
            .filter(Domain.tenant_id == current_user.tenant_id)
            .order_by(Domain.created_at.desc())
            .all()
        )
        result = []
        for d in domains:
            table_cnt = session.query(DomainTable).filter(DomainTable.domain_id == d.id).count()
            doc_cnt = session.query(DomainDocument).filter(DomainDocument.domain_id == d.id).count()
            source_name = None
            if d.source_id:
                ds = session.query(DataSource).filter(DataSource.id == d.source_id).first()
                if ds:
                    source_name = ds.name

            result.append(DomainOut(
                id=d.id,
                name=d.name,
                description=d.description,
                status=d.status,
                source_id=d.source_id,
                source_name=source_name,
                table_count=table_cnt,
                document_count=doc_cnt,
                created_at=d.created_at,
                updated_at=d.updated_at,
            ))
        return result
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Backend Error: {str(e)}\n\n{err_msg}")


@router.post("", response_model=DomainDetailOut, status_code=201)
def create_domain(
    payload: DomainCreatePayload,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.MANAGE_SEMANTIC)),
) -> DomainDetailOut:
    """Create a new domain linking connected database source and selected tables."""
    domain = Domain(
        tenant_id=current_user.tenant_id,
        source_id=payload.source_id,
        name=payload.name,
        description=payload.description,
        created_by=current_user.email,
        updated_by=current_user.email,
    )
    session.add(domain)
    session.flush()

    tables_summary = []
    for t_id in payload.table_ids:
        dt = DomainTable(domain_id=domain.id, table_id=t_id)
        session.add(dt)
        tm = session.query(TableMeta).filter(TableMeta.id == t_id).first()
        if tm:
            tables_summary.append(_build_table_summary(session, tm))

    session.commit()

    source_name = None
    if domain.source_id:
        ds = session.query(DataSource).filter(DataSource.id == domain.source_id).first()
        if ds:
            source_name = ds.name

    try:
        audit(
            session,
            tenant_id=current_user.tenant_id,
            entity_type="domains",
            entity_id=domain.id,
            action=AuditEvent.DOMAIN_CREATED,
            actor=current_user.email,
            after={"name": domain.name, "source_id": str(domain.source_id)},
            request=request,
        )
    except Exception as audit_err:
        log.warning("domain_audit_log_failed", error=str(audit_err))

    return DomainDetailOut(
        id=domain.id,
        name=domain.name,
        description=domain.description,
        status=domain.status,
        source_id=domain.source_id,
        source_name=source_name,
        table_count=len(tables_summary),
        document_count=0,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
        tables=tables_summary,
        documents=[],
        terms=[],
    )


@router.get("/{domain_id}", response_model=DomainDetailOut)
def get_domain_detail(
    domain_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DomainDetailOut:
    """Fetch complete domain details, database connection, selected tables, documents & terms."""
    domain = session.query(Domain).filter(Domain.id == domain_id, Domain.tenant_id == current_user.tenant_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    source_name = None
    if domain.source_id:
        ds = session.query(DataSource).filter(DataSource.id == domain.source_id).first()
        if ds:
            source_name = ds.name

    # Tables
    domain_tables = session.query(DomainTable).filter(DomainTable.domain_id == domain.id).all()
    tables_summary = []
    for dt in domain_tables:
        tm = session.query(TableMeta).filter(TableMeta.id == dt.table_id).first()
        if tm:
            tables_summary.append(_build_table_summary(session, tm))

    # Documents
    docs = session.query(DomainDocument).filter(DomainDocument.domain_id == domain.id).all()
    docs_summary = [
        DocumentSummary(
            id=doc.id,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            chunk_count=doc.chunk_count or 0,
            processing_status=doc.processing_status or "complete",
            created_at=doc.created_at
        ) for doc in docs
    ]

    # Terms
    terms = session.query(DomainTerm).filter(DomainTerm.domain_id == domain.id).all()
    terms_summary = [
        TermSummary(
            id=t.id,
            term=t.term,
            definition=t.definition,
            synonyms=t.synonyms or [],
            category=t.category
        ) for t in terms
    ]

    return DomainDetailOut(
        id=domain.id,
        name=domain.name,
        description=domain.description,
        status=domain.status,
        source_id=domain.source_id,
        source_name=source_name,
        table_count=len(tables_summary),
        document_count=len(docs_summary),
        created_at=domain.created_at,
        updated_at=domain.updated_at,
        tables=tables_summary,
        documents=docs_summary,
        terms=terms_summary,
    )


@router.post("/{domain_id}/documents", response_model=DocumentSummary, status_code=201)
async def upload_domain_document(
    domain_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.MANAGE_SEMANTIC)),
) -> DocumentSummary:
    """Upload PDF, DOCX, CSV, or XLSX document. Saves the file immediately and returns a 'pending' record.
    The heavy work (LLM term extraction, embedding, ChromaDB upsert) runs in the background."""
    domain = session.query(Domain).filter(Domain.id == domain_id, Domain.tenant_id == current_user.tenant_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    content_bytes = await file.read()
    file_name = file.filename or "uploaded_document"
    file_size = len(content_bytes)
    sha256_hash = hashlib.sha256(content_bytes).hexdigest()
    ext = file_name.split(".")[-1].lower() if "." in file_name else "txt"

    # Save to local storage directory immediately
    domain_dir = os.path.join(STORAGE_BASE, str(current_user.tenant_id), str(domain.id))
    os.makedirs(domain_dir, exist_ok=True)

    file_id = uuid.uuid4()
    local_file_path = os.path.join(domain_dir, f"{file_id}_{file_name}")
    with open(local_file_path, "wb") as f:
        f.write(content_bytes)

    # Save the document record immediately with status='pending' — return this to the user right away
    doc_record = DomainDocument(
        id=file_id,
        domain_id=domain.id,
        file_name=file_name,
        file_type=ext,
        file_path=local_file_path,
        file_size=file_size,
        sha256=sha256_hash,
        chunk_count=0,
        processing_status="pending"
    )
    session.add(doc_record)
    session.commit()
    session.refresh(doc_record)

    # Schedule the heavy processing as a background task
    background_tasks.add_task(
        _process_document_background,
        file_id=file_id,
        domain_id=domain.id,
        domain_name=domain.name,
        source_id=domain.source_id,
        tenant_id=current_user.tenant_id,
        content_bytes=content_bytes,
        file_name=file_name,
    )

    log.info("domain_document_upload_queued", domain=domain.name, file=file_name, doc_id=str(file_id))

    return DocumentSummary(
        id=doc_record.id,
        file_name=doc_record.file_name,
        file_type=doc_record.file_type,
        file_size=doc_record.file_size,
        chunk_count=doc_record.chunk_count,
        processing_status=doc_record.processing_status,
        created_at=doc_record.created_at
    )


def _process_document_background(
    file_id: uuid.UUID,
    domain_id: uuid.UUID,
    domain_name: str,
    source_id,
    tenant_id: uuid.UUID,
    content_bytes: bytes,
    file_name: str,
) -> None:
    """Background worker: parse text, extract LLM terms, embed chunks, upsert into ChromaDB."""
    from app.db import session_scope
    doc_record = None
    with session_scope() as db:
        try:
            doc_record = db.query(DomainDocument).filter(DomainDocument.id == file_id).first()
            if not doc_record:
                return

            # 1. Parse text
            raw_text = parse_document(content_bytes, file_name)
            chunks = chunk_text(raw_text, max_chars=1000, overlap=100)

            # 2. Extract domain business terms via LLM
            extracted_terms = []
            try:
                extracted_terms = extract_domain_terms(raw_text[:8000], domain_name)
                for term_obj in extracted_terms:
                    term_rec = DomainTerm(
                        domain_id=domain_id,
                        document_id=file_id,
                        term=term_obj.term,
                        definition=term_obj.definition,
                        synonyms=term_obj.synonyms,
                        category=term_obj.category
                    )
                    db.add(term_rec)
                db.flush()
            except Exception as exc:
                log.warning("domain_term_extraction_failed", file=file_name, error=str(exc))

            # 3. Batch embed all chunks at once, then upsert to ChromaDB
            if chunks:
                try:
                    embed_provider = get_embedding_provider()
                    embeddings = embed_provider.embed(chunks)
                    chroma_objects = [
                        EmbeddedObject(
                            id=f"domain_{domain_id}_doc_{file_id}_chunk_{idx}",
                            embedding=emb,
                            text=chunk,
                            metadata={
                                "tenant_id": str(tenant_id),
                                "domain_id": str(domain_id),
                                "document_id": str(file_id),
                                "file_name": file_name,
                                "chunk_index": idx
                            }
                        )
                        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings))
                    ]
                    ChromaStore().upsert(tenant_id, chroma_objects, source_id=source_id)
                except Exception as exc:
                    log.warning("chroma_upsert_domain_document_failed", file=file_name, error=str(exc))

            # 4. Update record with final chunk count and mark as complete
            doc_record.chunk_count = len(chunks)
            doc_record.processing_status = "complete"
            log.info("domain_document_processed", domain=domain_name, file=file_name, chunks=len(chunks), terms=len(extracted_terms))

        except Exception as exc:
            log.error("domain_document_background_failed", file=file_name, error=str(exc))
            if doc_record:
                doc_record.processing_status = "failed"


@router.get("/{domain_id}/documents/{document_id}/download")
def download_domain_document(
    domain_id: uuid.UUID,
    document_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Download a specific domain document."""
    domain = session.query(Domain).filter(Domain.id == domain_id, Domain.tenant_id == current_user.tenant_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    doc_record = session.query(DomainDocument).filter(DomainDocument.id == document_id, DomainDocument.domain_id == domain.id).first()
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if not os.path.exists(doc_record.file_path):
        raise HTTPException(status_code=404, detail="File missing on disk")

    import mimetypes
    mime_type, _ = mimetypes.guess_type(doc_record.file_name)
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(
        path=doc_record.file_path,
        filename=doc_record.file_name,
        media_type=mime_type
    )


@router.delete("/{domain_id}", status_code=204)
def delete_domain(
    domain_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.MANAGE_SEMANTIC)),
) -> None:
    """Delete domain and associated tables, terms, and local files."""
    domain = session.query(Domain).filter(Domain.id == domain_id, Domain.tenant_id == current_user.tenant_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    session.delete(domain)
    session.commit()


@router.post("/{domain_id}/query", response_model=DomainQueryResponse)
def query_domain_knowledge(
    domain_id: uuid.UUID,
    payload: DomainQueryPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DomainQueryResponse:
    """Perform plain-English RAG retrieval and hallucination-free QA grounded in domain documents & terms."""
    domain = session.query(Domain).filter(Domain.id == domain_id, Domain.tenant_id == current_user.tenant_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    embed_provider = get_embedding_provider()
    query_vec = embed_provider.embed_query(payload.question)

    store = ChromaStore()
    retrieval_hits = store.query(current_user.tenant_id, query_vec, n_results=payload.top_k)
    
    # Filter hits for this domain_id
    domain_hits = [h for h in retrieval_hits if h.metadata.get("domain_id") == str(domain.id)]

    # Fetch glossary terms
    terms = session.query(DomainTerm).filter(DomainTerm.domain_id == domain.id).limit(10).all()
    terms_context = "\n".join(f"- {t.term}: {t.definition}" for t in terms)

    doc_context = "\n\n".join(f"[Source: {h.metadata.get('file_name', 'Doc')}]\n{h.text}" for h in domain_hits)

    prompt = f"""You are an expert business assistant grounded in the '{domain.name}' domain knowledge base.

DOMAIN BUSINESS TERMS:
{terms_context if terms_context else "None defined"}

RETRIEVED DOCUMENT CONTEXT:
{doc_context if doc_context else "No document chunks retrieved"}

USER QUESTION:
{payload.question}

Provide a precise, accurate, plain-English answer grounded STRICTLY in the provided domain terms and document context. Do not invent details not present in the reference documents."""

    provider = LLMProvider()
    response = provider.generate_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    sources_out = [
        DomainQueryHit(text=h.text, distance=h.distance, metadata=h.metadata) for h in domain_hits
    ]

    return DomainQueryResponse(answer=response.content.strip(), sources=sources_out)
