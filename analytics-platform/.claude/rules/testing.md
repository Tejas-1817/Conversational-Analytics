# Testing Rules

- Every behavior change ships with tests in the same PR. No test, no merge.
- Layout: `tests/unit/` (no I/O, no DB — pure logic) and `tests/integration/` (docker compose services required, marked `@pytest.mark.integration`).
- Unit tests must run without network, database, or ENCRYPTION_KEY secrets — use fixtures in conftest.py.
- Test the guardrails hardest: PII masking, read-only enforcement, draft-never-auto-approved, human-edits-never-overwritten. A regression there is a security incident, not a bug.
- Coverage floor is enforced in CI (see workflow). Raising it over time is good; lowering it requires an ADR.
- Test names describe behavior: `test_sensitive_column_stores_no_raw_samples`, not `test_mask_2`.
- When fixing a bug: first write the failing test that reproduces it, then fix.
