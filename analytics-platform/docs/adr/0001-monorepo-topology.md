# ADR 0001: Monorepo topology

Date: 2026-07-09 · Status: Accepted

## Context
The platform will grow from one service (schema-ingestion) to several (semantic layer,
agent orchestration, dashboards). Team is small (~4–6 engineers). Per-service repos
duplicate CI, `.claude/` config, and governance files, which drift.

## Decision
Single monorepo. Services live under `services/<name>/`, each self-contained
(own requirements, Dockerfile, tests). Shared governance at root: `CLAUDE.md`,
`.claude/`, `.github/`, `docs/adr/`.

## Consequences
- One CI pipeline with per-service jobs; path filters can be added when build times demand.
- One set of rules and agents; no drift.
- If a service later needs independent release cadence or a separate team, extraction
  is possible — revisit via a new ADR, do not fork quietly.
