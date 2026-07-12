# Analytics Platform

Conversational analytics platform: semantic layer over customer databases, files, and
documents; natural-language questions answered with governed SQL, charts, and dashboards.

## Structure

```
CLAUDE.md            Team instructions for AI-assisted development (committed)
.claude/             Rules (binding), agent personas, slash commands, permissions
.github/             CI (lint, tests, coverage floor, license gate), CODEOWNERS, PR template
docs/adr/            Architecture Decision Records — read before structural changes
services/
  schema-ingestion/  Module 1: schema ingestion & semantic metadata (see its README)
```

Companion documents (project folder, outside the repo):
`Conversational-Analytics-Platform-Architecture.md` (platform architecture) and
`Schema-Ingestion-Module-Spec.docx` (Module 1 spec).

## Engineering gates (enforced, not aspirational)

1. CI blocks merge: ruff, unit tests, coverage ≥60%, banned-license check.
2. CODEOWNERS: security-critical paths need the designated senior reviewer.
3. AI agents (`.claude/agents/`) run pre-PR; they advise, humans approve.
4. Branch protection on `main` must be enabled in GitHub settings: require PR,
   require CI green, require code-owner review, no force-push. (Repo settings,
   cannot be committed — do this on day one.)

## Getting started

See `services/schema-ingestion/README.md` for the quickstart.
