# ADR 0003: Inferred metadata is draft until human approval

Date: 2026-07-09 · Status: Accepted

## Context
Relationships, dimension/measure classifications, and business descriptions are inferred
by heuristics and (later) LLMs. A wrong approved relationship or metric definition
silently corrupts every future generated answer — the platform's accuracy promise
depends on this metadata being trustworthy.

## Decision
Nothing inferred is auto-approved. All inferences persist as `status='draft'` with
confidence + evidence; humans approve via the review API (audited). Single exception:
declared foreign keys are database facts and enter as `approved` with confidence 1.0.
Re-ingestion never overwrites fields where `updated_by != 'system'`.

## Consequences
- Review burden is real; mitigated by LLM-assisted drafting and domain-by-domain rollout
  (top 10–20 tables first).
- The rule for reviewers: descriptions containing business rules (tax, discounts,
  cancellations, currency) require domain-owner confirmation — else `needs_clarification`.
