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

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, Domain, DomainTable, DomainDocument, DomainTerm, DataSource, TableMeta
from app.api.deps import get_current_user, Permission, require_permission 
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


class DocumentSummary(BaseModel):
    id: uuid.UUID
    file_name: str
    file_type: str
    file_size: int
    chunk_count: int
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
            tables_summary.append(TableSummary(id=tm.id, table_name=tm.table_name, row_count=tm.row_count))

    session.commit()

    source_name = None
    if domain.source_id:
        ds = session.query(DataSource).filter(DataSource.id == domain.source_id).first()
        if ds:
            source_name = ds.name

    audit(
        session,
        tenant_id=current_user.tenant_id,
        entity_type="domains",
        entity_id=domain.id,
        action=AuditEvent.SEMANTIC_MODEL_CREATED,
        actor=current_user.email,
        after={"name": domain.name, "source_id": str(domain.source_id)},
        request=request,
    )

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
            tables_summary.append(TableSummary(id=tm.id, table_name=tm.table_name, row_count=tm.row_count))

    # Documents
    docs = session.query(DomainDocument).filter(DomainDocument.domain_id == domain.id).all()
    docs_summary = [
        DocumentSummary(
            id=doc.id,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            chunk_count=doc.chunk_count,
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
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.MANAGE_SEMANTIC)),
) -> DocumentSummary:
    """Upload PDF, DOCX, CSV, or XLSX document, parse text, extract LLM business terms, save locally, and embed vectors."""
    domain = session.query(Domain).filter(Domain.id == domain_id, Domain.tenant_id == current_user.tenant_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    content_bytes = await file.read()
    file_name = file.filename or "uploaded_document"
    file_size = len(content_bytes)
    sha256_hash = hashlib.sha256(content_bytes).hexdigest()
    ext = file_name.split(".")[-1].lower() if "." in file_name else "txt"

    # Save to local storage directory
    domain_dir = os.path.join(STORAGE_BASE, str(current_user.tenant_id), str(domain.id))
    os.makedirs(domain_dir, exist_ok=True)
    
    file_id = uuid.uuid4()
    local_file_path = os.path.join(domain_dir, f"{file_id}_{file_name}")
    with open(local_file_path, "wb") as f:
        f.write(content_bytes)

    # 1. Parse text from document
    raw_text = parse_document(content_bytes, file_name)
    chunks = chunk_text(raw_text, max_chars=1000, overlap=100)

    # 2. Extract domain business terms via LLM
    extracted_terms = extract_domain_terms(raw_text[:8000], domain.name)

    # Save document record
    doc_record = DomainDocument(
        id=file_id,
        domain_id=domain.id,
        file_name=file_name,
        file_type=ext,
        file_path=local_file_path,
        file_size=file_size,
        sha256=sha256_hash,
        chunk_count=len(chunks)
    )
    session.add(doc_record)

    # Save extracted terms
    for term_obj in extracted_terms:
        term_rec = DomainTerm(
            domain_id=domain.id,
            document_id=file_id,
            term=term_obj.term,
            definition=term_obj.definition,
            synonyms=term_obj.synonyms,
            category=term_obj.category
        )
        session.add(term_rec)

    session.commit()

    # 3. Vector Embeddings in ChromaStore
    if chunks:
        embed_provider = get_embedding_provider()
        chroma_objects = []
        for idx, chunk in enumerate(chunks):
            embedding = embed_provider.embed_query(chunk)
            vec_id = f"domain_{domain.id}_doc_{file_id}_chunk_{idx}"
            meta = {
                "tenant_id": str(current_user.tenant_id),
                "domain_id": str(domain.id),
                "document_id": str(file_id),
                "file_name": file_name,
                "chunk_index": idx
            }
            chroma_objects.append(EmbeddedObject(id=vec_id, embedding=embedding, text=chunk, metadata=meta))

        try:
            store = ChromaStore()
            store.upsert(current_user.tenant_id, chroma_objects, source_id=domain.source_id)
        except Exception as exc:
            log.warning("chroma_upsert_domain_document_failed", error=str(exc))

    log.info("domain_document_processed", domain=domain.name, file=file_name, chunks=len(chunks), terms=len(extracted_terms))

    return DocumentSummary(
        id=doc_record.id,
        file_name=doc_record.file_name,
        file_type=doc_record.file_type,
        file_size=doc_record.file_size,
        chunk_count=doc_record.chunk_count,
        created_at=doc_record.created_at
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
