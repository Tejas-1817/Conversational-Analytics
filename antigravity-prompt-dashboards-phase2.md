# Prompt for Antigravity: Dashboards phase 2 (tabs, text widgets, filters, combo charts, cache)

Paste everything below into Antigravity as the task prompt. Work on the
`Customer360` branch, **after** the phase 1 prompt
(`antigravity-prompt-dashboards-save-insight.md`) has been implemented.

---

## Context

This is the `analytics-platform` repo: a FastAPI backend in
`services/schema-ingestion/` and a React 19 + TypeScript + Vite frontend in
`apps/web/`. Read `analytics-platform/CLAUDE.md` first and respect every
invariant in it: tenant isolation, read-only customer data, PII masking
before persistence or any LLM call, audit logging, DDL migrations as the
source of truth (the ORM must match), tests with every behavior change, an
ADR for structural changes, and no AGPL dependencies.

Phase 1 added dashboard ownership and visibility, reusable saved insights,
live widget data through a run endpoint that checks the viewer's own
permissions, and the "save to which dashboard" dialog in the chat. **Verify
that phase 1 is in place before starting.** If it is not, stop and tell me.

## Where these ideas come from

The feature set below was shaped by reading the public documentation of a
similar product (WisdomAI dashboards: building dashboards, tabs, instant
filters, turning answers into dashboards, tool-generated visualizations,
dual-axis charts, versioning, and cached data). Implement the **behaviors**
described here in this app's own design. Do not copy that product's
wording, icons, layout or branding. Use this app's design tokens
(`apps/web/src/index.css`) and `lucide-react`.

## Decisions assumed (confirm with me; do not silently change them)

| # | Decision | Assumed default |
| :- | :--- | :--- |
| 1 | Order of work | Tasks 1 to 6 in the order below. Each task must be shippable on its own. |
| 2 | Result cache scope | Cached rows are stored per **viewer** (key includes the user and their permission set), in Redis with a short TTL, never shared across users, never written to the database. |
| 3 | Overview summary | A manually written, editable summary only. No AI-generated summary and no "what changed since" in this phase. |
| 4 | Combo chart setup | Automatic suggestion plus a manual editor, both producing the same layout spec. |
| 5 | Edit permissions | Owners and admins edit. Everyone who can open a dashboard can switch tabs, use instant filters and refresh. |

## Task 1: Add several answers from a chat to a dashboard at once

**Today:** a chart can be saved one at a time through the dialog from phase 1.

**Desired:** a user can select one or more answers in the current chat and
add them together.
- In the chat, add a way to enter selection mode (for example an "In this
  chat" panel listing answers that have a chart or table) with a checkbox per
  answer and a **Select all** option.
- **Add to dashboard** opens the existing phase 1 dialog: choose an existing
  dashboard or create a new one.
- One bulk request creates all insights and widgets in a single transaction.
  Each insight is named from its chart title or question. Answers without SQL
  are listed as not addable, with a reason.
- Placement: new widgets go into the first free positions, in chat order, on
  the dashboard's current tab (or its first tab).
- Duplicate protection: an answer already saved to that dashboard is shown as
  already added and skipped.

## Task 2: Tabs

**Desired behavior:**
- A dashboard can be split into named tabs. The tab bar is shown only when a
  dashboard has two or more tabs, so a single-tab dashboard looks as it does
  today.
- The first time an editor adds a tab, the existing widgets move into a first
  tab (name it "Main" or similar) and the new empty tab appears next to it.
- Editors can add, rename (click the name), reorder (drag) and delete tabs. A
  dashboard always keeps at least one tab. Deleting a tab with widgets asks
  for confirmation and offers to move its widgets to another tab first.
- A widget menu has **Move to tab** and **Clone to tab**. New widgets are
  added to the tab being viewed.
- The active tab is part of the page URL (for example `?tab=<id>`), so a
  shared link opens that tab. The viewer still needs access to the dashboard.
- Everyone who can open the dashboard can switch tabs.
- Existing dashboards are unchanged until someone edits tabs on them.
- Dashboard-wide settings (such as a future filter bar) are shared across all
  tabs; do not build per-tab settings.

**Requirements:** a `dashboard_tabs` table (id, dashboard_id, name, position)
and a nullable `tab_id` on widgets, with a migration, ORM changes and
endpoints for tab create, rename, reorder, delete, and widget move and clone.
Write audit entries for tab and widget changes, and enforce owner or admin
permission server-side.

## Task 3: Text widgets and an Overview section

**Desired behavior:**
- Add a second widget type, **Text**, for narrative content written in
  Markdown, next to the existing chart or table widgets. Add a `widget_type`
  to widgets (default `insight`; `text` needs no insight).
- Text is rendered with the app's safe Markdown renderer: raw HTML is never
  rendered, and links are limited to `http`, `https` and `mailto`.
- Text widgets can be dragged, resized, moved between tabs and removed like
  any other widget.
- A collapsible **Overview** area at the top of a dashboard holds an editable
  executive summary (stored on the dashboard, Markdown, size-capped). It is
  collapsed or expanded per viewer and remembered locally.
- Version one is manual text only (decision 3).

## Task 4: Instant filters on table widgets

**Desired behavior:** a viewer can narrow a results table in place without
changing anything that is saved.
- Each column has a menu with **Filter values**: a checklist of the values in
  that column with a row count for each, a search box for long lists,
  `(Blank)` for empty cells, and **Select all** and **Select none**.
- A filtered column shows a small funnel marker, and a summary bar above the
  table shows how many filters are active, with a **Reset** that clears them.
- The same menu has **Hide column** (at least one column must stay visible).
- Filters apply only in the viewer's browser, only to the rows already
  loaded, and never change the underlying query, the saved insight or the
  dashboard. They are not saved and do not affect other viewers. They reset
  when the page is refreshed.
- Limit: filters work on the rows loaded in the browser. Cap the run endpoint
  at a documented maximum (suggest 10,000 rows) and show a clear notice when a
  result was truncated.
- Build it as a reusable table component so the chat's data table can use it
  too, and keep it keyboard accessible with labelled controls.

## Task 5: Combo (dual-axis) charts

**Desired behavior:** a single chart can show measures with different scales
or units, for example revenue as columns and margin percent as a line on a
second axis.
- Extend `ChartRenderer` (verify how it renders charts today and which
  library it uses) with a combo chart type driven by a **layout spec**, for
  example: which columns go on the x axis, a list of y axes (each with a
  position, left or right, a series type of column, bar, line or area, and
  its columns), and an optional column that splits the data into coloured
  series.
- Independent scales for the left and right axes, a legend, tooltips that show
  units, and correct handling of null values and time axes.
- **Automatic suggestion:** extend the chart recommender so that when a result
  has measures on clearly different scales, or the question asks for a combo
  or dual-axis chart, a combo layout is suggested. Define the rules in one
  place and keep them deterministic. Say in the plan how you would test them.
- **Manual editor:** in the widget editor, let the owner pick the series type
  and axis for each measure. The editor writes the same layout spec.
- The layout spec is stored with the widget settings (versioned with a
  `schema_version`), and the chat's chart switcher can use it as well.
- Fall back to the existing chart types when the spec is invalid.

## Task 6: Result cache, "data as of" and refresh

**Desired behavior:**
- Widget results can be served from a cache so dashboards open quickly.
- The dashboard header shows **Data as of <time>**, which is the time of the
  **oldest** result shown anywhere on the dashboard, and says when cached data
  is used.
- A **Refresh data** action re-runs every widget query (bypassing the cache)
  and updates the header time. Refreshing does not need any admin action.
- Admins see a small freshness marker on each widget (cached or live, and its
  age). Other users rely on the header.

**Requirements (security first):**
- The cache key includes the viewer and a fingerprint of their permissions.
  Cached rows are never served to a different user.
- Access is re-verified on every load before any cached result is returned. If
  the viewer lost access, they get the locked placeholder, not the cache.
- Cached rows are stored in Redis with a TTL and a size limit, after the same
  PII masking the app applies elsewhere. Nothing is written to the database,
  and results are never logged.
- Make the TTL, the size limit and an on and off switch configurable
  settings. Clear a source's cache entries when its schema is re-ingested.

## Task 7: Tests and documentation
- **Backend (pytest):** bulk add is atomic and skips duplicates; tab
  operations enforce permissions and keep at least one tab; deleting a tab
  moves or removes its widgets as chosen; text widgets reject raw HTML and
  unsafe links; the run endpoint truncates at the cap and reports it; cache
  keys differ per user, access is re-checked, and a revoked user never gets
  cached rows; refresh bypasses the cache; the layout spec validator accepts
  good specs and rejects bad ones.
- **Frontend (vitest and testing-library):** selection mode and bulk add;
  tab bar visibility, switching, URL deep link, reorder, delete confirmation;
  text widget rendering safety; instant filters (checklist counts, search,
  blank values, reset, hide column, the last visible column cannot be hidden,
  filters never change the query); combo chart rendering from a spec and the
  fallback; header "data as of" and refresh behavior.
- Add an ADR covering tabs, widget types, the combo layout spec and the cache
  design, and update `README.md` with the new features and settings.

## Out of scope for this phase (but do not block them)
- **Draft and publish versioning with history and revert.** Design the tab and
  widget tables so a later version snapshot can be added (stable ids and no
  assumptions that edits overwrite history).
- **Dashboard-wide filters** applied to all widgets, which need structured
  queries instead of raw SQL.
- AI-written summaries, "what changed since", scheduled notifications or
  email, sharing with named users, comments and sign-off workflows, and PDF
  export.

## Constraints
- Reuse existing components, `react-grid-layout` and the design tokens. Add no
  new dependency without stating its license. No AGPL.
- Keep existing behavior that is not listed here.
- If an assumed decision conflicts with what you find in the code, stop and
  tell me before changing it.

## Definition of done
- All seven tasks are complete and tests pass (`pytest` in
  `services/schema-ingestion/`, plus `tsc --noEmit` and the linter in
  `apps/web/`).
- A user can select several answers in a chat, add them to a new dashboard,
  split the dashboard into tabs, add a text widget and an overview summary,
  filter a table without changing the dashboard, show a revenue-and-margin
  combo chart, see "data as of" and refresh, and open a link that lands on a
  specific tab.
- A user without table permission never sees that table's rows, live or from
  cache.
- The PR description lists every decision made, any assumption that changed,
  and each `CLAUDE.md` invariant that was touched.
