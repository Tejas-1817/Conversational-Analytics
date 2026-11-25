# 6. Dashboards Live Data Execution, Access Scoping, and In-Place Customization

* **Status**: Accepted
* **Date**: 2026-11-23
* **Deciders**: Architecture Team, Core Engineering

## Context

The conversational analytics platform allows users to explore databases and ask complex analytics queries via conversational chat. Users need a persistent way to assemble these insights into customizable, interactive dashboards in the spirit of modern BI playgrounds (e.g., WisdomAI).

Previously:
1. `SavedInsight` stored static result data rows in JSON payloads, causing stale data, bloating storage, and creating security / PII persistence risks.
2. Saving an insight silently created an `ApprovedSQLExample`, conflating end-user dashboard authoring with privileged semantic layer governance.
3. Dashboards lacked visibility scoping (`private` vs. `published`), meaning any dashboard created in a tenant was either globally visible or lacked distinct owner privacy.
4. Dashboard layout updates lacked in-place mutation, risking widget ID churn and race conditions.
5. Observers (`VIEWER` role) were able to mutate dashboards without enforcement of read-only access.

## Decision

1. **Live Data Execution vs. Static Snapshots**:
   - `SavedInsight` never stores raw data snapshot rows. It records the SQL query, resolved chart type, column metadata, and lineage identifiers (`source_id`, `domain_id`, `conversation_id`, `message_id`).
   - Dashboard widgets execute live queries on demand via `POST /dashboards/insights/{id}/run`.
   - The run endpoint validates viewer credentials at query time:
     - Verifies tenant isolation and dashboard access.
     - Enforces data source access permissions via `verify_user_has_source_access`.
     - Parses referenced physical tables using `sqlglot` and verifies table permissions against `get_user_permitted_table_ids`.
     - Returns `{ "status": "locked", "locked": true, "detail": ... }` if the viewer lacks permission to any underlying table or source.
     - Executes queries with strict statement timeouts and read-only connection guards (`SET TRANSACTION READ ONLY`).
     - Applies PII masking (`mask_result_rows`) to all returned rows. Query results are never logged.

2. **Decoupled Governance (No Auto-Promotion)**:
   - Saving an insight from chat only creates a `SavedInsight` and associates it with the chosen dashboard.
   - It strictly does **not** create or modify `ApprovedSQLExample`. Promoting queries to the semantic layer remains an explicit administrative review process in the Semantic Layer / Governance UI.

3. **Visibility & Access Scoping**:
   - Dashboards have explicit `visibility` (`private` | `published`).
   - Default is `private` (visible and editable only by the author and tenant administrators).
   - `published` dashboards can be viewed by any authenticated user in the tenant, while editing remains restricted to the owner and administrators.
   - Users with the `VIEWER` (Observer) role are restricted to read-only access across all dashboard and insight creation, mutation, and deletion endpoints.

4. **In-Place Widget Layout Persistence**:
   - The frontend uses `react-grid-layout` with responsive breakpoints (`lg`, `md`, `sm`, `xs`, `xxs`).
   - Layout coordinate changes are persisted via `PUT /dashboards/{id}/layout`, updating existing widget positions in place without deleting and recreating widgets, preserving widget IDs and preventing layout churn.

5. **Chat Save Insight Dialog**:
   - Replaced legacy browser `prompt()` / `alert()` popups with an accessible `SaveInsightModal` component.
   - Allows users to search and select existing dashboards or create a new dashboard inline, prefilling insight title and question context, and showing a success toast with a direct "Open Dashboard ->" navigation link.

## Consequences

* **Positive**:
   - Fresh, real-time data displayed on all dashboard widgets with zero stale snapshot drift.
   - Viewer-level security: users cannot bypass table-level RBAC or data source access controls by viewing shared dashboards.
   - Clean separation between personal dashboard customization and tenant-wide semantic golden SQL examples.
   - Stable widget IDs eliminate state resets, layout races, and orphaned widget records.
   - Comprehensive test coverage across both FastAPI backend endpoints and React frontend components.
