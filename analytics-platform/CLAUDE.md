# Analytics Platform — Team Instructions

Conversational analytics platform (WisdomAI-class): semantic layer over customer
databases/files/documents, NL→SQL with governed context, dynamic dashboards.
Deployment model: single instance per customer, tenant-aware data model.

## Repository layout

- `services/schema-ingestion/` — Module 1: connects to customer DBs, ingests/profiles schemas, detects relationships, stores reviewable metadata. See its README and `docs/` specs.
- `docs/adr/` — Architecture Decision Records. Read these before proposing structural changes; add a new ADR when you make one.
- `.claude/rules/` — modular engineering rules (code style, testing, security, API conventions). These are binding.
- `.claude/agents/` — subagent personas: `code-reviewer`, `test-writer`, `security-auditor`. Use them before opening a PR, not as a substitute for CI or human review.

## Non-negotiable invariants (do not weaken, ever)

1. Customer databases are READ-ONLY: session guards + write-privilege rejection live in `services/schema-ingestion/app/connectors/factory.py`. Never remove or bypass.
2. Profiling is always sampled and always under a statement timeout.
3. Sample values are PII-masked before persistence and before any LLM call.
4. Inferred metadata (relationships, classifications, descriptions) is `draft` until a human approves. Only declared FKs auto-approve.
5. Re-runs never overwrite human-edited fields (`updated_by != 'system'`) and never delete — deactivate with `is_active=false`.
6. Credentials: encrypted at rest, never logged, never in API responses.
7. Every review action writes to `audit_log`.

## Working agreements

- Python 3.12, FastAPI, SQLAlchemy 2.0 style. Follow `.claude/rules/code-style.md`.
- Every behavior change ships with tests (`.claude/rules/testing.md`). CI blocks merge on lint, tests, and coverage.
- DDL in `migrations/` is the source of truth; ORM models must match it. Changing one means changing both, plus a migration note in the PR.
- No new dependencies without checking license (AGPL is forbidden in this codebase) and adding a line to the PR description explaining why.
- Uncertain about business logic? Stop and ask — do not invent semantics. Mark items `needs_clarification` instead of guessing.

## Commands

```bash
cd services/schema-ingestion
docker compose up --build          # full local stack (API :8000, worker, metadata-db, demo DB)
pip install -r requirements.txt -r requirements-dev.txt
pytest                             # unit tests (no DB needed)
ruff check app tests               # lint
```
