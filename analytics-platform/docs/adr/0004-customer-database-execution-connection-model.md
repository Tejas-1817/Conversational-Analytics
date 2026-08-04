# 4. Customer Database Execution Connection Model

* **Status**: Accepted
* **Date**: 2026-08-03
* **Deciders**: Architecture Team, Core Engineering

## Context

Previously, `ExecutorService.execute` ran compiled Text-to-SQL queries against the application's internal metadata PostgreSQL session. Customer databases were only connected to during schema ingestion via `build_engine(source)`. This created an execution model gap where compiled queries were run against the metadata store rather than the customer's target database.

In addition, invariant #1 in `CLAUDE.md` requires that all customer database connections be strictly read-only, enforced via `build_engine(source)`.

## Decision

1. **Target Database Resolution**:
   At query execution time in `chat_tasks.py`, the pipeline resolves the `DataSource` corresponding to the metric/semantic model requested (or the active `DataSource` for the tenant).

2. **Read-Only Connector Execution**:
   `ExecutorService.execute` receives the resolved `DataSource` and calls `app.connectors.factory.build_engine(source)` to create a short-lived, read-only engine.

3. **Short-Lived Engine Lifecycle**:
   Queries are executed inside a `with engine.connect() as conn:` block. The target engine is explicitly disposed (`engine.dispose()`) inside a `finally:` block after execution succeeds or fails.

4. **Trace Separation**:
   Surfaces `"connecting_to_source"` as a discrete stage prior to `"executing_query"` so that data source connection errors can be distinguished from SQL syntax/execution errors in trace polling.

## Consequences

* **Positive**:
  - Compiled SQL queries execute on the customer's actual target database.
  - Read-only transaction guards and session restrictions (`SET TRANSACTION READ ONLY`) are strictly enforced.
  - Short-lived connection lifecycles prevent connection pool leaks on customer databases.
  - Metadata DB sessions remain isolated to system data queries.
