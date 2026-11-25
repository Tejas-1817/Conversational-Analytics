# 0007. Dashboards Phase 2: Tabs, Text Widgets, Instant Filters, Combo Dual-Axis Charts, and Viewer Cache

Date: 2026-11-23
Status: Accepted

## Context

Following Dashboards Phase 1 (visibility, reusable saved insights, and live permission-checked execution), Phase 2 expands the platform into a comprehensive, executive-ready analytics canvas inspired by WisdomAI capabilities, adhering strictly to the architecture invariants defined in `analytics-platform/CLAUDE.md`.

Specific customer capabilities required:
1. **Bulk-saving multiple answers from a chat**: Selecting one or more answers containing charts/tables in the conversation and adding them simultaneously to an existing or new dashboard in a single transaction.
2. **Dashboard tabs**: Segmenting dashboards into named tabs with URL deep-linking (`?tab=<id>`), auto-migrating legacy unassigned widgets to a "Main" tab, tab reordering, and widget move/clone operations across tabs.
3. **Text widgets and Overview summary**: Supporting narrative markdown notes alongside visualizations with strict sanitization (no raw HTML, link protocols restricted to `http`, `https`, `mailto`), plus an executive Overview section at the top of the dashboard.
4. **Instant table filters**: In-place filtering and column hiding on tabular results without mutating underlying queries or saved insights.
5. **Combo (dual-axis) charts**: Rendering measures on disparate scales (e.g. absolute revenue vs margin percentage) on separate left and right y-axes using a versioned layout specification.
6. **Result caching with viewer permission fingerprinting**: Serving widget query results from a high-performance Redis/in-memory cache to ensure sub-second dashboard load times while strictly preventing cross-user data exposure.

---

## Decisions

### 1. Multi-Answer Bulk Save (`POST /dashboards/bulk-save`)
- Chat interface provides an "In this chat" drawer listing all model answers that generated tabular or visual results.
- Bulk dialog permits selecting target dashboard or creating a new one in place.
- Backend saves insights and widgets atomically in a single database transaction.
- Duplicate detection matches both query signature and source message ID against existing widgets on the target dashboard, skipping duplicates and reporting them cleanly.
- Grid coordinates allocate widgets in two-column 6x4 blocks (`lg` breakpoint).

### 2. Tab Architecture & Scoping (`dashboard_tabs`)
- A dedicated `dashboard_tabs` table (`id`, `dashboard_id`, `name`, `position`, `created_at`, `updated_at`) with foreign key cascade to `dashboards`.
- Nullable `tab_id` on `dashboard_widgets`.
- **Zero disruption for existing dashboards**: Single-tab or legacy dashboards hide the tab bar entirely until two or more tabs exist.
- **Auto-migration**: The first time an editor adds a tab, existing widgets on the dashboard (`tab_id IS NULL`) are automatically migrated to a newly created "Main" tab (position 0), and the requested tab is created at position 1.
- **URL synchronization**: Active tab is reflected in the URL parameter (`?tab=<id>`).
- **Tab deletion safety**: Deleting a tab with widgets prompts the editor to either move widgets to another tab (`move_to_tab_id`) or delete them. Dashboards must retain at least one tab.

### 3. Text Widgets & Safe Markdown Rendering
- `widget_type` column added to `dashboard_widgets` (default `'insight'`; `'text'` does not require `insight_id`).
- Safe Markdown rendering enforced on both backend and frontend:
  - Raw HTML tags (`<script>`, `<iframe>`, `<div>`, `<img onerror=...>`, etc.) are rejected with HTTP 422 on the backend and escaped on the frontend.
  - Link protocols are strictly restricted to `http:`, `https:`, and `mailto:` via `safeUrlTransform`.
- An executive **Overview Summary** is added to `dashboards` (Markdown, capped at 10,000 characters). Collapse state is persisted locally in `localStorage` per viewer.

### 4. Instant Table Filters (`InstantFilterTable`)
- Client-side in-memory filtering applied over loaded dataset rows:
  - Multi-select value checklist with frequency counts and search.
  - `(Blank)` handling for empty/null values.
  - Column hiding with minimum 1 visible column protection.
  - Active filter summary bar with one-click reset.
- Execution cap enforced at 10,000 rows with a visible status notice when truncation occurs.
- Filters never mutate saved insight definitions, SQL queries, or dashboard metadata.

### 5. Combo (Dual-Axis) Charts & Versioned Layout Spec
- ECharts option generator configured with independent left and right numeric value y-axes.
- Layout spec schema version 1:
  ```json
  {
    "schema_version": 1,
    "x_axis": "quarter",
    "y_axes": [
      {
        "position": "left",
        "series_type": "bar",
        "columns": ["revenue"],
        "unit": "$"
      },
      {
        "position": "right",
        "series_type": "line",
        "columns": ["margin_pct"],
        "unit": "%"
      }
    ]
  }
  ```
- Deterministic auto-recommendation in `ChartRecommender` when metrics have disparate numerical scales ($\ge 10\times$ ratio or percentage vs absolute).
- Manual combo editor in widget settings allows owners to configure custom dual-axis mappings.

### 6. Result Caching & Permission Fingerprinting
- Cached in Redis (with local LRU memory fallback).
- Cache key incorporates tenant ID, viewer user ID, SHA-256 permission fingerprint (role, accessible source, permitted table IDs), insight ID, and query SQL:
  `dashcache:{tenant}:{user}:{perm_hash}:{insight}:{sql_hash}`
- **Security-first**: Every query load re-verifies viewer table permissions before returning cached data. If table or source access is revoked, a locked placeholder is returned immediately.
- Freshness header indicates **Data as of <time>** computed from the oldest result among displayed widgets.
- **Refresh data** action sends `force_refresh=true` to re-execute customer queries directly and update cache entries.
- Admins see a small freshness badge (`⚡ Cached` vs `🟢 Live`) on each widget card.

---

## Consequences

- Dashboards render significantly faster when reading cached metrics while preventing all cross-user data leakage.
- Clean separation between analytical SQL execution and frontend data exploration (instant filters).
- Full backwards compatibility with Phase 1 dashboards and customer databases.
- Read-only database guarantees and PII masking invariants remain strictly enforced.
