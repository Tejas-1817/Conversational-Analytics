# 5. Excel Data Source Materialization to Per-Source SQLite

* **Status**: Accepted
* **Date**: 2026-09-10
* **Deciders**: Architecture Team, Core Engineering

## Context

Users frequently have tabular data in spreadsheet workbooks (`.xlsx`) that they want to connect as data sources for conversational analytics alongside relational databases (PostgreSQL, MySQL, Snowflake, etc.).

Unlike client-server database engines, an Excel workbook is a static flat file without a native SQL engine, introspection API, or database connection interface. We needed an approach that:
1. Reuses the existing generic SQLAlchemy-based ingestion, profiling, relationship detection, and Text-to-SQL execution pipeline without building parallel query engines.
2. Guarantees non-negotiable read-only safety for customer data.
3. Preserves strict multi-tenant isolation.
4. Handles common spreadsheet quirks: multiple sheets, non-standard column names, duplicate headers, mixed-type columns, empty sheets, and formula evaluation.

## Decision

1. **Per-Source Materialized SQLite Database**:
   Upon uploading an Excel workbook, the backend materializes each selected worksheet into a table within an isolated, per-source SQLite database file stored at:
   `{EXCEL_SQLITE_DIR}/{tenant_id}/{source_id}/materialized.db`

2. **Read-Only SQLite Engine via Connection URI**:
   `app.connectors.factory.build_engine(source)` creates a SQLAlchemy engine using SQLite's read-only URI mode:
   `create_engine(f"sqlite:///{posix_path}?mode=ro", connect_args={"uri": True})`
   This enforces at the SQLite C-library layer that any write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`) raise `sqlite3.OperationalError: attempt to write a readonly database`.

3. **Ingestion & Normalization Rules**:
   - **Sheet & Table Names**: Sanitized to lowercase ASCII snake_case identifiers (`^[a-z0-9_]+$`).
   - **Column Headers**: Sanitized to valid SQL identifiers; duplicates disambiguated with `_1`, `_2` suffixes.
   - **Type Inference & Coercion**: Pandas parses column types; mixed-type columns are coerced to `TEXT` without dropping rows.
   - **Formulas & Empty Sheets**: Evaluated to computed values only via `openpyxl` (`data_only=True`). Empty/zero-row sheets are automatically skipped.

4. **Pipeline & Relationship Detection**:
   The materialized SQLite database seamlessly plugs into `introspect_source` and `profile_source`. Since Excel sheets do not contain declared foreign keys, heuristic relationship detection (`naming` and `value_overlap`) runs to discover cross-sheet join paths for NL-to-SQL synthesis.

## Consequences

* **Positive**:
  - Unified pipeline: Introspection, column profiling, PII masking, schema export, and Text-to-SQL execution work identically across Excel and client-server databases.
  - Zero performance degradation on metadata PostgreSQL; SQL queries against spreadsheet data execute locally against the dedicated SQLite file.
  - Full multi-tenant isolation through tenant-partitioned filesystem paths.
  - Read-only safety guaranteed at the engine level.

* **Trade-offs**:
  - Materialization is a point-in-time snapshot of the uploaded `.xlsx` file; live workbook edits require re-uploading the file.
  - File size limits apply (`EXCEL_MAX_UPLOAD_MB`, default 50MB) to prevent disk exhaustion.
