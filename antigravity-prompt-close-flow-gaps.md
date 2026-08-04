# Prompt for Antigravity: Close the schema→semantic→query→results flow gaps

Paste everything below into Antigravity as the task prompt.

---

## Context

This is the `analytics-platform` repo (FastAPI backend at
`services/schema-ingestion/`, React frontend at `apps/web/`). It's a
conversational analytics tool: connect to a customer DB → ingest/profile the
schema → generate a semantic layer → answer NL questions with SQL + charts.

Read `analytics-platform/CLAUDE.md` first — it defines non-negotiable
invariants (read-only customer DBs, PII masking before persistence/LLM calls,
tenant isolation, audit logging, etc.). Do not weaken any of them while doing
this work.

A reference flowchart for the intended pipeline was compared against the
actual code and three gaps were found. Fix all three. Each gap below has:
current behavior (with file/function references), desired behavior, and
acceptance criteria.

---

## Gap 1 — No schema export/snapshot file is ever produced

**Current behavior:** `app/ingestion/pipeline.py` runs
`introspect → profile → relationships → classify → semantic_generation` and
writes results straight into the metadata DB (`TableMeta`, `ColumnMeta`,
etc. in `app/models.py`). There is no intermediate schema file written
anywhere — I confirmed via grep that no ingestion code writes to disk.

**Desired behavior:** After the `introspect` stage (and again after
`classify`, once roles/relationships are known), serialize the schema
snapshot (tables, columns, types, PK/FK, detected relationships, column
roles — **not** row data, and PII-masked sample values only if included) to
a versioned JSON/YAML file for auditability and offline diffing.

**Requirements:**
- Add a new function, e.g. `app/ingestion/schema_export.py:export_schema_snapshot(session, source, version)`, called from `pipeline.py` as an additional stage (or as a side effect of `introspect`/`classify`) — don't put file I/O inline in the stage runners.
- Store snapshots under a configurable directory (add `SCHEMA_SNAPSHOT_DIR` to `app/config.py`, default something like `./data/schema-snapshots/`, **not** hardcoded to a developer's `Downloads` folder — the diagram said `/downloads in code root`, which is not appropriate for a real deployment; use a proper app-data directory instead and document the naming choice).
- Filename should be namespaced by tenant + source + version, e.g. `{tenant_id}/{source_id}/v{version_number}.json`.
- Snapshot content must go through the same PII-masking path as `app/ingestion/pii.py` before being written — never write raw sample values.
- Write it as its own pipeline stage so it shows up in `job.stats` / `IngestionJob.stage` like the others, and add a stage entry consistent with the existing pattern in `pipeline.py`.
- Add a unit test in `tests/unit/` verifying: (a) the file is written with masked data only, (b) no snapshot is created for stages that fail before introspection completes, (c) re-running ingestion creates a new versioned file rather than overwriting the previous one.

---

## Gap 2 — Chat query execution never reconnects to the customer's actual database

**Current behavior:** `app/db.py` explicitly documents its engine as "our
own Postgres, not customer databases." `app/engine/executor_service.py`
(`ExecutorService.execute`) runs the compiled SQL using the **same session**
that's passed in from `app/tasks/chat_tasks.py` (`session_scope()` →
metadata DB). Nowhere in the chat pipeline (`nlu_service`, `resolver_service`,
`planner_service`, `compiler_service`, `executor_service`) is
`app/connectors/factory.build_engine()` called — that connector factory is
only used during ingestion (`app/ingestion/pipeline.py`). This means
generated SQL is currently executed against the metadata store, not the
customer's real target database.

**Desired behavior:** At execution time, the pipeline should open a
connection to the customer's actual `DataSource` (the one that was
ingested) using the same read-only-enforcing connector factory used during
ingestion, run the compiled query there, and return results — while all
semantic-layer lookups (`ColumnMeta`, `TableMeta`, `SemanticMetric`, etc. in
`compiler_service.py`) continue to come from the metadata DB as they do now.

**Requirements:**
- Add a way to resolve which `DataSource` a given tenant/conversation's semantic model maps to (check `app/models.py` for how `TableMeta`/`SemanticModel` relate to `DataSource` — there should already be a foreign key path; if there isn't one, add it via a migration in `migrations/`, and update the ORM model to match, per the DDL-is-source-of-truth rule in `CLAUDE.md`).
- Modify `ExecutorService.execute` (or add a new method) to accept the resolved `DataSource`, call `app.connectors.factory.build_engine(source)` to get a target engine, execute the compiled SQL there (via a short-lived connection, not the long-lived metadata session), and dispose the engine/connection afterward — mirror the connection lifecycle already used in `app/ingestion/pipeline.py::run_pipeline` (`engine = build_engine(source)` ... `engine.dispose()` in `finally`).
- Preserve the read-only guard behavior from `connectors/factory.py` (invariant #1 in `CLAUDE.md`) — do not bypass it for the query path.
- Preserve the tenant_id RLS predicate injection in `compiler_service.py` — it stays as-is; this change is only about *where* the compiled SQL runs, not how it's built.
- Handle and surface connection failures distinctly from SQL execution failures in the trace (`_append_trace` in `chat_tasks.py`) — e.g. `"connecting_to_source"` as a discrete stage/label before `executing_query`, so the frontend can show "Could not connect to the data source" vs. "Query failed" as different states.
- Add/update tests in `tests/unit/test_compiler_service.py` (or a new `tests/unit/test_executor_service.py`) that mock `build_engine` and confirm: (a) the target engine is used for execution, not the metadata session, (b) the engine is disposed after execution (success and failure paths), (c) read-only violations are still rejected.
- Update `docs/adr/` with a new ADR explaining the before/after connection model, since this is a structural change per `CLAUDE.md`'s instruction to add an ADR for structural changes.

---

## Gap 3 — Verify chart-type selection is not a "1 vs many records" rule

**Current behavior:** This one may already be resolved — `app/engine/chart_recommender.py::ChartRecommender.recommend()` was recently updated to branch on dimension count, time granularity, and measure count (not raw record count), returning `kpi_card`, `line_chart`, `pie_chart`, `bar_chart`, `carousel_cards`, or `table`. Confirm this is the version currently in the repo (check for `PIE_MAX_SLICES` / `CAROUSEL_MAX_CARDS` constants and the `row_count`/`column_count` parameters on `recommend()`).

**Requirements:**
- If the multi-chart-type version is already present, just confirm `tests/unit/test_chart_recommender.py` passes and move on — no changes needed.
- If it's missing (i.e., `recommend()` only returns `kpi_card`/`bar_chart`/`table` based on dimension count alone), reintroduce the richer logic: `pie_chart` for single dimension + single measure + 2–6 rows, `carousel_cards` for multi-measure-per-entity or multi-dimension results capped at ~12 rows, `bar_chart`/`table` as fallback — and wire `row_count`/`column_count` through from `ExecutorResult` in `app/tasks/chat_tasks.py`.
- Confirm the frontend (`apps/web/src/components/visualizations/ChartRenderer.tsx`, `apps/web/src/pages/business/ChatInterface.tsx`) renders `carousel_cards` and exposes the chart-type switcher next to "Save Insight" as already implemented — do not regress this UI.

---

## Definition of done

- All three gaps closed with tests passing (`pytest` in `services/schema-ingestion/`, `tsc --noEmit` + `oxlint` in `apps/web/`).
- No weakening of any invariant in `CLAUDE.md`.
- New ADR added for the Gap 2 connection-model change.
- Update `README.md`'s "Usage Walkthrough" section if the ingestion job now shows an extra stage, and note the new `SCHEMA_SNAPSHOT_DIR` config in the Prerequisites/env-vars section.
- Summarize what changed and why in the PR description, including which invariant(s) each change touches, per the working agreements in `CLAUDE.md`.
