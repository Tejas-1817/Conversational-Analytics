# Schema Ingestion & Semantic Metadata Service

Module 1 of the conversational analytics platform ("the robot that fills the notebook").
Connects to customer databases, ingests and profiles schemas, detects relationships,
classifies dimensions/measures, and stores everything as **reviewable metadata** —
the foundation the semantic layer and SQL generation are built on.

Read the companion spec: `Schema-Ingestion-Module-Spec.docx` (in the project folder).

## What's implemented vs stubbed

| Piece | State |
|---|---|
| Metadata repository DDL (`migrations/001_init.sql`) | ✅ Complete |
| Source registration, encrypted credentials, read-only verification | ✅ Implemented (Postgres, MySQL) |
| Schema introspection (tables, columns, keys, comments, diff-aware re-runs) | ✅ Implemented |
| Data profiling (stats + PII-masked samples, guardrails in code) | ✅ Implemented |
| Relationship detection: declared FKs, naming + value-overlap | ✅ Implemented |
| Relationship detection: LLM suggestions | 🔲 Stub (`relationships.py::_llm_suggestions_stub`) |
| Dimension/measure heuristic classification | ✅ Implemented |
| AI enrichment (business names, descriptions, synonyms) | 🔲 Stub (`classifier.py::_llm_enrichment_stub`) |
| Review/approval API with audit trail | ✅ Implemented |
| Snowflake / BigQuery connectors | 🔲 Not wired (clear NotImplementedError) |
| Review UI | 🔲 Not started (API-first; use /docs meanwhile) |
| Auth | ⚠️ Static API key only — replace with SSO/OIDC before real use |

**Honesty note:** this skeleton compiles and its structure has been reviewed, but it has
NOT been run end-to-end against a live database yet. Your first task is to run the
quickstart below and fix whatever surfaces. Expect small issues — that's normal.

## Quickstart

```bash
cp .env.example .env
# set ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up --build
# API docs: http://localhost:8080/docs
```

Register the bundled demo database and ingest it:

```bash
# 1. Register (demo-source-db from docker-compose; hostname as seen from the api container)
curl -s -X POST localhost:8080/sources -H "X-API-Key: change-me" -H "Content-Type: application/json" -d '{
  "name": "demo-shop", "type": "postgres", "host": "demo-source-db", "port": 5432,
  "database_name": "shop", "username": "demo", "password": "demo"
}'
# NOTE: the demo user owns its tables, so read-only verification will REJECT it — that is
# the guardrail working. For local dev, create a read-only user first:
#   docker compose exec demo-source-db psql -U demo -d shop -c \
#     "CREATE USER reader PASSWORD 'reader'; GRANT CONNECT ON DATABASE shop TO reader; \
#      GRANT USAGE ON SCHEMA public TO reader; GRANT SELECT ON ALL TABLES IN SCHEMA public TO reader;"
# then register with username=reader / password=reader.

# 2. Trigger ingestion (use the source id returned above)
curl -s -X POST localhost:8080/jobs/ingest/<source_id> -H "X-API-Key: change-me"

# 3. Watch the job, then browse results
curl -s localhost:8080/jobs/<job_id> -H "X-API-Key: change-me"
curl -s localhost:8080/metadata/sources/<source_id>/tables -H "X-API-Key: change-me"
curl -s localhost:8080/metadata/sources/<source_id>/relationships -H "X-API-Key: change-me"
```

Expected result on the demo DB: declared FKs from `order_items` captured as approved;
`orders.customer_id → customers.id` surfaced as a **draft candidate** via naming +
value-overlap, with evidence — approve it via `POST /metadata/relationships/<id>/review`.

## Layout

```
migrations/001_init.sql      The metadata repository DDL ("the blank notebook")
app/config.py                Settings incl. profiling guardrails
app/models.py                ORM (must stay in sync with the DDL — DDL is source of truth)
app/security/crypto.py       Fernet credential encryption
app/connectors/factory.py    Read-only engines + session guards + write-privilege check
app/ingestion/introspector.py  Stage 1: catalog walk (SQLAlchemy Inspector)
app/ingestion/profiler.py      Stage 2: column stats + PII-masked samples
app/ingestion/relationships.py Stage 3: FK/naming/value-overlap detection (+LLM stub)
app/ingestion/classifier.py    Stage 4: dimension/measure heuristics (+LLM stub)
app/ingestion/pipeline.py      Orchestrates stages; records job status/stats
app/api/                     sources, jobs, metadata (review endpoints with audit log)
app/worker.py                RQ worker (python -m app.worker)
demo/demo_shop.sql           Demo customer DB exercising the detectors
```

## Rules the code enforces (do not weaken)

1. Customer DB sessions are **forced read-only** and carry a **statement timeout** (connection-level, `connectors/factory.py`).
2. Registration **rejects users with write privileges**.
3. Profiling is **always sampled** — no full-table scans for samples.
4. Sample values are **PII-masked before persistence** and must also be masked before any future AI call.
5. Inferred relationships and classifications are **drafts** — only humans approve (declared FKs are the one exception; they're database facts).
6. Re-runs **never overwrite human-edited fields** and never delete — disappeared objects become `is_active=false`.
7. Every review action lands in `audit_log`.

## Where the team picks up

1. Run the quickstart; fix anything that surfaces (then delete the honesty note above).
2. Implement the two LLM stubs (contracts documented in the stub docstrings).
3. Add pytest integration tests against the demo DB (acceptance criteria are in the spec doc, §7).
4. Build the review UI on the existing API.
5. Wire Snowflake/BigQuery dialects when a test account is available.
