# ADR 0002: Postgres metadata repository; DDL is source of truth

Date: 2026-07-09 · Status: Accepted

## Context
All extracted schema knowledge, drafted semantics, relationship candidates, approval
statuses, and audit history need durable storage. The SQL generator in the next phase
consumes exactly this data. The data model is tenant-aware even though deployment is
single-instance-per-customer (ADR-worthy consequence of the SaaS evolution path).

## Decision
PostgreSQL 16 as the metadata repository. Hand-written DDL in `migrations/` is the
source of truth; SQLAlchemy ORM models must mirror it. Approval workflow
(draft → reviewed → approved) and `audit_log` are structural, not conventions.

## Consequences
- DDL/ORM drift is a real risk → CI reviewers and the code-reviewer agent check both
  sides change together. A schema-diff test should be added (backlog).
- Alembic can replace raw SQL migrations later; sequence-numbered SQL files until then.
