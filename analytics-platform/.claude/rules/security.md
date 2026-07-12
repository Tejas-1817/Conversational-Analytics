# Security Rules (binding — violations block merge)

1. Customer databases are read-only. The session guards and write-privilege verification in `app/connectors/factory.py` must never be weakened, made optional, or bypassed "temporarily".
2. All profiling/overlap queries run sampled and under statement timeout. New query paths against customer DBs must reuse the guarded engine from the factory — never create ad-hoc engines.
3. PII: sample values are masked before persistence and before ANY external call (LLM included). New data flows carrying customer values must call `app/ingestion/pii.py` masking and add tests.
4. Credentials: Fernet-encrypted at rest; never in logs, error messages, or API responses. `.env` files are never committed.
5. SQL built from identifiers must quote them via `engine.dialect.identifier_preparer.quote` — never f-string raw user/table input into SQL.
6. Dependencies: no AGPL/SSPL licenses; `pip-audit` findings of HIGH+ severity block merge.
7. Auth is a static API key TODAY (skeleton). Any externally reachable deployment requires replacing it with SSO/OIDC first — this is a release blocker, not a backlog item.
