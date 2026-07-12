# Code Style Rules

- Python 3.12+. Type hints on all public functions; `X | None` over `Optional[X]`.
- SQLAlchemy 2.0 style only (`Mapped`, `mapped_column`); no legacy Query patterns in new code.
- Structured logging via structlog: `log.info("event_name", key=value)` — snake_case event names, never f-string interpolation into the message.
- Never log credentials, tokens, or raw sample values. If a variable might contain them, it does.
- Explicit over clever: no metaclass tricks, no dynamic attribute magic. The team maintaining this is growing its skills — optimize for readability.
- Errors: raise specific exceptions; API layer converts to HTTPException with actionable detail. Never swallow exceptions silently; a caught-and-logged exception must state what degrades as a result.
- Module docstrings explain WHY the module exists and what invariants it holds, not just what it does.
- Linter: ruff (config in pyproject.toml). CI blocks on violations — do not add `# noqa` without a justification comment.
