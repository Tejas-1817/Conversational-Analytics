# Schema Ingestion & Semantic Metadata Service

The core backend service of the Conversational Analytics Platform. 
It connects to customer databases, ingests and profiles schemas, detects relationships, classifies dimensions/measures, builds AI-enriched semantic models, and powers natural language SQL query planning and execution.

---

## 🚀 Pipeline & Feature Implementation Matrix

| Module / Pipeline Stage | Status | Description |
|---|---|---|
| **Metadata Repository (`migrations/`)** | ✅ Complete | Full DDL schema for Multi-tenant Data Sources, Ingestion Jobs, Semantic Layer, RLS & Audit Logs |
| **Source Connection & Security** | ✅ Implemented | Encrypted credentials (Fernet), read-only verification, statement timeouts |
| **Stage 1: Introspection** | ✅ Implemented | Database reflection (tables, columns, primary/foreign keys, schemas) |
| **Stage 2: Data Profiling** | ✅ Implemented | Column stats, distinct values, null rates, PII-masked sampling |
| **Stage 3: Relationship Detection** | ✅ Implemented | Declared FKs + Naming heuristics + Sampled value overlap + Structured LLM suggestions |
| **Stage 4: Role Classification** | ✅ Implemented | Automated labeling of dimensions, measures, keys, and attributes |
| **Stage 5: Semantic Generation** | ✅ Implemented | Copy-on-Write incremental versioning, AI metric/dimension enrichment, semantic graph validation, atomic promotion |
| **Chat & NLU Pipeline** | ✅ Implemented | Router Intent Classification ➔ Hybrid Entity Retrieval ➔ Planner (LLM name-to-UUID resolution) ➔ SQL Compiler & Executor |
| **Multi-Tenancy & RBAC** | ✅ Implemented | Tenant session scoping, Row-Level Security policies, `ADMIN`/`ANALYST`/`VIEWER` roles |
| **Pluggable LLM Registry** | ✅ Implemented | Ollama (local local models), Gemini, HuggingFace, Mock providers |

---

## 🛠️ Quickstart

### 1. Environment Setup
```bash
cp .env.example .env

# Generate Fernet encryption key for stored connection credentials:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Seed Demo Database & Tenant Data
```bash
python scripts/seed_demo.py
```

### 3. Run Backend API & Background Worker

Open two separate terminals:

**Terminal A (API Server):**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# API Documentation: http://127.0.0.1:8000/docs
```

**Terminal B (RQ Worker):**
```bash
python -m app.worker
```

---

## 📁 Repository Layout

```text
migrations/                   PostgreSQL DDL migration scripts (Source of Truth)
app/config.py                 Settings & profiling guardrails
app/models.py                 SQLAlchemy ORM models (DataSource, TableMeta, SemanticModel, etc.)
app/security/crypto.py        Fernet credential encryption
app/connectors/factory.py     Read-only database engine factory + session guards
app/ingestion/
  ├── introspector.py         Stage 1: Catalog walk (SQLAlchemy Inspector)
  ├── profiler.py             Stage 2: Column stats & PII-masked sampling
  ├── relationships.py        Stage 3: FK, naming, value overlap, & structured LLM relationship detection
  ├── classifier.py           Stage 4: Dimension/measure heuristic role classification
  ├── semantic_generator.py   Stage 5: Incremental versioning & AI semantic layer builder
  └── pipeline.py             Orchestrates stages 1-5 as picklable RQ jobs
app/engine/
  ├── router_service.py       Intent classification (analytics vs greeting vs help)
  ├── retrieval_service.py    Keyword & vector hybrid retrieval for metrics/dimensions
  ├── planner_service.py      Prompt engineering & structured JSON query plan generation
  ├── compiler_service.py     Dialect-specific SQL generation & validation
  └── executor_service.py     Tenant-scoped SQL execution & result formatting
app/tasks/
  └── chat_tasks.py           5-Stage chat processing task & live trace updates
app/api/                      API Endpoints (sources, jobs, semantic, metadata, auth, users)
app/worker.py                 RQ background worker process (`python -m app.worker`)
```

---

## 🔐 Core System Guardrails

1. **Read-Only Session Isolation**: External database sessions carry connection-level read-only flags and statement timeouts.
2. **Read-Only Verification**: Source registration rejects credentials with write or DDL privileges.
3. **Sampled Profiling**: Data sampling is strictly bounded by configurable limits to prevent full table scans.
4. **PII Masking**: Sample values are PII-masked before persistence and before being sent to LLM prompts.
5. **Incremental Copy-on-Write Versioning**: Re-running ingestion on existing sources only updates changed tables and preserves human edits via versioning.
6. **Audit Trail**: All administrative and review actions land in `audit_log`.
