# Prompt for Antigravity: Dashboards and "Save insight" from chat

Paste everything below into Antigravity as the task prompt. Work on the
`Customer360` branch.

---

## Context

This is the `analytics-platform` repo: a FastAPI backend in
`services/schema-ingestion/` and a React 19 + TypeScript + Vite frontend in
`apps/web/`. Read `analytics-platform/CLAUDE.md` first and respect every
invariant in it: tenant isolation, read-only customer data, PII masking
before persistence or any LLM call, audit logging for review and sharing
actions, DDL migrations as the source of truth (the ORM must match), tests
with every behavior change, an ADR for structural changes, and no AGPL
dependencies.

## The feature (three parts)

1. **Users can create dashboards.**
2. **Dashboards are customizable playgrounds.** A user can add insights from
   several different chats, remove them, drag and resize them, and customize
   the dashboard, in the spirit of tools like WisdomAI. Copy the interaction
   ideas only, not any branding, wording or icons. Use this app's design
   tokens (`apps/web/src/index.css`) and `lucide-react`.
3. **Save insight from chat.** Charts in the Ask AI chat already have a save
   option. When a user saves an insight, a dialog must ask which dashboard to
   save it to, list the user's available dashboards, and offer a **"Create
   new dashboard"** option. Word the question as "Save to which dashboard?"
   or another suitable, professional phrasing (for example "Choose a
   dashboard" or "Add to dashboard"), in a tone consistent with the rest of
   the app.

## What already exists (verify each point in the code first)

- **Backend:** `app/api/dashboards.py` (prefix `/dashboards`) has
  `POST /insights`, `GET /insights`, `POST ""` (create), `GET ""` (list),
  `GET /{id}` and `PATCH /{id}` (replaces all widgets). Models `SavedInsight`,
  `Dashboard` and `DashboardWidget` are in `app/models.py`, created by
  `migrations/004_dashboards.sql`. The newest migration is
  `018_rag_chunks.sql`, so use the next free number.
- **Dashboards page:** `apps/web/src/pages/business/Dashboards.tsx` (about 400
  lines) uses `react-grid-layout` (already installed, with
  `react-resizable`). It has an edit mode, drag and resize, remove widget,
  full-screen, export CSV and JSON, a saved-insights library sidebar, and a
  create form. It is routed at `/dashboards`.
- **Chat:** `apps/web/src/pages/business/ChatInterface.tsx` has
  `handleSaveInsight`, which uses `window.prompt()` for a name and `alert()`
  for the result, and posts the SQL plus a snapshot of the chart data to
  `/dashboards/insights`. The button is next to the chart card.
- **Charts:** `components/visualizations/ChartRenderer.tsx` renders a chart
  from `data`, `chartType`, `columns` and `columnTypes`, and already has a
  chart-type switcher and export.
- **Roles:** the user model has `ADMIN`, `USER`, `ANALYST` and `VIEWER`. The
  add-user dialog describes **Observer** as "read-only access to published
  dashboards", but there is no "published" concept in the data model.

## Problems in the existing code that this work must fix

These are the reasons the existing feature cannot simply be extended.
Confirm each one before changing it.

1. **No ownership checks.** `GET /dashboards` and `GET /dashboards/insights`
   return everything in the tenant. `PATCH /dashboards/{id}` lets any user in
   the tenant overwrite any dashboard. `user_id` is stored but never used for
   authorization.
2. **Stored data snapshots bypass access control.** Widgets draw from
   `chart_config.data`, which holds the result rows captured at save time.
   Anyone who can open a dashboard sees rows from tables they may not have
   permission to read (see migrations 015 and 016), the rows are stored
   without PII masking, they never refresh, and large results bloat the JSONB
   column.
3. **No source scoping.** `saved_insights` has no `source_id`, `domain_id` or
   link to the conversation and message it came from, so an insight cannot be
   re-run or permission-checked.
4. **Unique names.** `UNIQUE (tenant_id, name)` on both insights and
   dashboards means two users cannot use the same name, and a duplicate raises
   an unhandled database error.
5. **Silent promotion of SQL.** Saving an insight adds its SQL to
   `ApprovedSQLExample` for the whole tenant, which later steers AI answers.
   The only safety check is a `startswith("SELECT")` test plus a few keyword
   substrings. The UI even says the insight "will automatically guide future
   AI answers". A dashboard save must not approve SQL by itself.
6. **Missing operations.** There is no delete or rename for dashboards or
   insights. `PATCH` deletes and recreates every widget, so widget ids change
   on each save and concurrent edits overwrite each other.
7. **Surprising create.** Creating a dashboard automatically fills it with the
   first four saved insights.
8. **Only the `lg` layout** is built, so layouts at other breakpoints are not
   saved.

## Decisions assumed (confirm with me; do not silently change them)

| # | Decision | Assumed default |
| :- | :--- | :--- |
| 1 | Live data or snapshot | **Live.** A widget stores the SQL, source and chart settings. It runs the SQL when opened, using the viewer's own permissions. A cached snapshot is only a fallback, shown with a "last refreshed" time. |
| 2 | Who can see a dashboard | **Private to its owner by default.** The owner can publish it to the tenant (read-only for others, which is what Observers get). Existing dashboards stay tenant-visible so nothing disappears. |
| 3 | Approved-SQL promotion | **Removed from the save path.** It may return later as an explicit, reviewed action. |
| 4 | Insights from several chats | Insights are reusable items. The same insight can sit on several dashboards. Removing a widget does not delete the insight. |
| 5 | Mixing data sources | Allowed. Each widget carries its own source and is permission-checked per viewer. A viewer without access sees a locked placeholder, not an error. |
| 6 | Customization in version one | Drag, resize, rename a widget, switch chart type, remove, duplicate, full-screen, rename and delete a dashboard. **Not** in version one: global filters, text or note widgets, scheduled refresh or email, sharing with individual users, PDF export. |
| 7 | Who may create dashboards | `ADMIN`, `ANALYST` and `USER`. `VIEWER` (Observer) is read-only. |
| 8 | Saveable answers | Only answers that have SQL and a chart or table. Not code-repository answers. |

## Tasks (in order)

### Task 1: Data model and migration
- Add a migration (next free number) and update `app/models.py` to match.
- `saved_insights`: add `source_id`, `domain_id` (nullable), `conversation_id`
  and `message_id` (nullable), the chart type, and `last_run_at`. Replace the
  `(tenant_id, name)` uniqueness with something that allows the same name for
  different users (or no uniqueness). Keep `chart_config` for chart settings,
  and keep a size-capped cached snapshot only if you can justify it.
- `dashboards`: add `visibility` (`private` or `published`) and `updated_at`.
  Replace the `(tenant_id, name)` uniqueness with uniqueness per owner.
- `dashboard_widgets`: add `title_override`, `chart_type_override`, and a
  `settings` JSONB, plus `layouts` or per-breakpoint positions.
- Backfill: existing dashboards become `published` so current users keep
  access, and existing widgets keep their positions.
- Indexes for `(tenant_id, user_id)` and `dashboard_id`.

### Task 2: Backend API
- Dashboards: list (own plus published), create (empty by default), get,
  rename or edit description, change visibility, delete. All scoped by tenant,
  and write actions limited to the owner or an admin.
- Widgets: add, update (layout and settings), remove, duplicate. Layout saves
  must update widgets in place instead of delete-and-recreate, and must reject
  stale writes (for example with an `updated_at` or version check).
- Insights: list (own plus those on dashboards the user can see), get, rename,
  delete. Deleting an insight that is on dashboards must warn or be blocked,
  and the behavior must be defined and tested.
- **Run endpoint:** run an insight's SQL for the current viewer. It must verify
  the viewer's source and table access with the existing helpers (for example
  `verify_user_has_source_access` and the table-permission checks), validate
  the SQL with the existing sqlglot validator (not string checks), use the
  read-only executor with a row limit and timeout, apply PII masking to
  returned samples as the rest of the app does, and return a clear "no access"
  result for a viewer who lacks permission. Never log SQL results.
- Remove the automatic `ApprovedSQLExample` promotion from the save path and
  fix the UI text that promises it.
- Handle duplicate names gracefully (a clear 409 or an automatic suffix), and
  write audit log entries for create, delete, publish and share changes.

### Task 3: Save-insight dialog in the chat
- Replace `prompt()` and `alert()` in `handleSaveInsight` with a modal dialog.
- Content: a name field prefilled from the chart title or the question, an
  optional description, and a clearly worded question asking which dashboard
  to save to (use the wording from the feature description above), with the
  user's dashboards as a searchable list (name, widget count, last updated)
  and a **Create new dashboard** option that expands an inline name field.
  Save is disabled until a name and a destination exist.
- After saving: close the dialog, show a toast with an **Open dashboard** link,
  and mark the chart as saved so it cannot be saved twice by accident. Show
  loading and error states in the dialog.
- The dialog is accessible: focus moves into it and returns afterwards, Esc
  closes it, fields have labels, and the dashboard list is keyboard navigable.
- The save button appears only for answers with SQL and a chart or table. Send
  the source, domain, conversation and message ids with the request. Do not
  send result rows unless the decision above says to keep a snapshot.
- The new widget gets a sensible default size for its chart type and is placed
  in the first free spot.

### Task 4: Dashboards page
- Create a dashboard from the page (empty), rename it, delete it with a
  confirmation, and see which dashboards are private or published.
- Edit mode: drag and resize (using the existing `react-grid-layout`), rename
  a widget, switch its chart type, remove, duplicate, and full-screen. Save
  layouts for every breakpoint, with a clear unsaved-changes state and a
  warning when leaving with unsaved changes.
- **Add insights:** an "Add insight" panel that lists reusable insights with
  search, grouped or filterable by data source and by the chat they came from,
  so a dashboard can combine insights from different chats.
- Each widget loads its data through the run endpoint with a loading skeleton,
  an error state, a locked "no access" state, a "last refreshed" time and a
  manual refresh.
- Empty states for no dashboards and for an empty dashboard. Observers see
  published dashboards without any edit controls.

### Task 5: Tests
- **Backend (pytest):** an authorization matrix (owner, other user in the same
  tenant, user in another tenant, viewer), private versus published
  visibility, insights run with and without table permission, no raw rows
  stored when snapshots are off, duplicate-name handling, layout save keeps
  widget ids, delete behavior for insights used on dashboards, and that saving
  an insight no longer touches `ApprovedSQLExample`.
- **Frontend (vitest and testing-library):** the save dialog flow (select an
  existing dashboard, create a new one inline, validation, error, success
  toast), focus handling, the edit-mode actions, layout persistence, and the
  locked and error widget states.
- A migration test or check that the backfill keeps existing dashboards
  visible.

### Task 6: Documentation
- Add an ADR for the dashboard data model (live data versus snapshot, private
  versus published, and removing the approved-SQL promotion).
- Update `README.md` with how to create dashboards and save insights, and list
  any new settings or limits.

## Constraints
- Reuse `ChartRenderer`, `react-grid-layout` and the existing design tokens.
  Add no new dependency without stating its license. No AGPL.
- Keep existing behavior that is not listed above, including the other chat
  actions (copy, regenerate, feedback, stop generation).
- Never store credentials, tokens or unmasked sensitive values in dashboards.
- If any assumed decision conflicts with what you find in the code, stop and
  tell me before changing it.

## Definition of done
- All six tasks are complete and the tests pass (`pytest` in
  `services/schema-ingestion/`, plus `tsc --noEmit` and the linter in
  `apps/web/`).
- A user can create a dashboard, save charts from two different chats into it
  using the dialog, rearrange and resize them, reload the page, and see the
  same layout with live data.
- A user without permission to a table sees a locked placeholder and none of
  that table's rows.
- No user can read or edit another user's private dashboard.
- Nothing is promoted to approved SQL examples by saving an insight.
- The PR description lists every decision made, any assumption that changed,
  and each `CLAUDE.md` invariant that was touched.
