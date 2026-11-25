# Prompt: Dashboards Page Redesign — Clean Canvas-First Layout

Work on the `Customer360` branch in the `analytics-platform` repo.
Read `analytics-platform/CLAUDE.md` first and respect every invariant in it.

---

## Goal

Redesign the Dashboards page so the **widget canvas occupies maximum space**.
Remove the in-page sidebar that currently takes up 270 px on the left (dashboard
list + create form). Replace it with a compact top bar that has only two
controls: a **dashboard selector dropdown** and a **"+ New Dashboard" button**.
The main application sidebar (`Layout.tsx`) stays exactly as it is today.

Widgets on the dashboard must be **freely resizable** and **drag-and-drop
movable** at all times for editors — no separate "Edit Layout" toggle required.

---

## Current State (what to change)

| Element | Today | After |
|---|---|---|
| **In-page sidebar** (270 px, left) | Contains "New Dashboard" form (name, description, visibility, Create button) and a scrollable list of dashboards | **Removed entirely** |
| **Dashboard selector** | Click a row in the sidebar list to switch dashboards | **Compact dropdown** in the top-right area of the canvas header |
| **New dashboard** | Inline form in the sidebar | **Small "New Dashboard" button** next to the dropdown; opens a modal dialog |
| **Canvas width** | `flex: 1` minus 270 px sidebar | `flex: 1` — full remaining width after the app sidebar |
| **Widget resizing** | Only when "Edit Layout" button is toggled on | **Always enabled** for editors (owners + admins); viewers still cannot resize or move |
| **Widget dragging** | Only when "Edit Layout" button is toggled on | **Always enabled** for editors |
| **"Edit Layout" / "Done" button** | Toggles `isEditMode` to enable drag/resize | **Removed** (or repurposed as a lock/unlock toggle if you prefer, but default is unlocked for editors) |
| **Dashboard header bar** | Full-width bar with title, badges, 6+ action buttons | Simplified: title + badges on the left, dashboard dropdown + New Dashboard button + settings gear + refresh on the right |

---

## Decisions (confirm with me before changing any of these)

| # | Decision | Assumed default |
|---|---|---|
| 1 | In-page sidebar removal | Remove entirely. The app sidebar (`Layout.tsx`) already has the "Dashboards" link. |
| 2 | Dashboard switching | A `<select>` or custom dropdown showing all dashboards by name, in the header bar. |
| 3 | New Dashboard creation | A small `"New Dashboard"` button that opens a **modal** with name, description and visibility fields. |
| 4 | Widget interactivity default | `isDraggable` and `isResizable` are always `true` for editors; always `false` for viewers. No toggle button needed. |
| 5 | Unsaved layout auto-save | Keep the current Save/Discard banner. When a user drags or resizes, the yellow banner appears and they explicitly save. |
| 6 | Existing features preserved | Tabs bar, Overview section, Add Insight drawer, Add Text widget, Settings modal, Delete modal, fullscreen overlay — all stay. |

---

## Task 1 — Remove the in-page sidebar

### What to remove
- The entire `<div style={{ width: '270px', ... }}>` block (lines ~1775–1897 in
  `Dashboards.tsx`), which contains:
  - The "Dashboards" `<h2>` heading.
  - The "New Dashboard" card form (`<form onSubmit={handleCreateDashboard}>`).
  - The "Available Dashboards" list (`dashboards.map(...)`).
- The outer flex container's `gap: '1.5rem'` between sidebar and canvas.

### What to keep
- All state variables (`newDashName`, `newDashDesc`, `newDashVisibility`,
  `isCreatingDash`, `handleCreateDashboard`, `dashboards`, `loadData`,
  `activeDashboardId`, `setActiveDashboardId`) — they will be used by the new
  dropdown and modal.
- The `Layout.tsx` sidebar (the application-level sidebar with Dashboards,
  Domains, etc.) is **not touched**.

### Result
The page root `return` is now a single `<div>` that is the canvas area, using
the full width provided by the layout.

---

## Task 2 — Add dashboard selector dropdown and "New Dashboard" button to the header

### Dashboard selector dropdown
- Place it in the **top-right** area of the existing dashboard header bar
  (the bar that currently shows the dashboard title, visibility badge, and
  action buttons).
- It should be a compact dropdown (`<select>` or a custom popover) showing all
  dashboard names. The currently active dashboard is pre-selected.
- Selecting a different dashboard calls `setActiveDashboardId(id)` and updates
  `searchParams` just like the sidebar click handler did.
- Style: small, unobtrusive, matching the design system. Something like:
  ```
  [ ▾ My Sales Dashboard ]   [＋ New Dashboard]   [⚙]  [↻]
  ```

### "New Dashboard" button
- A small **secondary** button (or ghost button with a `+` icon) placed right
  after the dropdown.
- Clicking it opens a **modal dialog** (not an inline form) with:
  - Dashboard Name input (required)
  - Description input (optional)
  - Visibility radio: Private / Published
  - Cancel and Create buttons
- On successful creation, close the modal, reload data, and auto-select the
  new dashboard — the same logic as today's `handleCreateDashboard`.

### Header layout
Reorganize the header bar to look clean:

```
┌────────────────────────────────────────────────────────────────────────┐
│  📊 Dashboard Title    [Private]   Data as of 3:49 PM                 │
│  Optional description text                                            │
│                                                       ┌─────────────┐ │
│    [Add Insight] [Add Text] [Add Tab]  [⚙] [↻]       │ ▾ Dashboard │ │
│                                                       └─────────────┘ │
│                                              [＋ New Dashboard]        │
└────────────────────────────────────────────────────────────────────────┘
```

Or a more compact single-row variant:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Dashboard Title [Private] [Data as of …]     [ ▾ Switch ] [＋New] [⚙] [↻] │
└──────────────────────────────────────────────────────────────────────────────┘
```

Use whichever fits cleanly. The key constraint is: **dropdown + New button on the right side of the header**.

---

## Task 3 — Make widgets always interactive (drag + resize) for editors

### Changes to `ResponsiveGridLayout`
- Currently gated by `isEditMode && canEditActiveDashboard`.
- Change to just `canEditActiveDashboard`:
  ```tsx
  isDraggable={canEditActiveDashboard}
  isResizable={canEditActiveDashboard}
  ```
- Remove the `isEditMode` state variable and the "Edit Layout" / "Done"
  toggle button from the header.
- Keep the `onLayoutChange` handler and the Save/Discard banner — they remain
  exactly as today, appearing whenever the layout differs from the saved state.

### Widget card resize handles
- Ensure each widget card shows a subtle **resize handle** in the
  bottom-right corner (react-grid-layout provides this by default when
  `isResizable` is true). Style it to be unobtrusive: a small diagonal grip
  icon, faded until hovered.
- Drag handles: the widget title bar should be the drag handle. Add
  `className="drag-handle"` to the title bar `<div>` and configure
  `draggableHandle=".drag-handle"` on `ResponsiveGridLayout` so that
  dragging happens only from the title bar (not from chart content, which
  needs its own interactions like tooltips and clicks).

### Viewer experience
- Viewers see the same widgets but cannot drag or resize.
- No "Edit Layout" button is shown to them (already the case today).

---

## Task 4 — Polish and cleanup

### Remove dead code
- Remove the `isEditMode` state, the toggle button JSX, and any conditional
  rendering that depended on `isEditMode` (the `isEditMode` prop on
  `DashboardWidgetCard` can be set to `true` for editors, `false` for
  viewers, or removed entirely if the card doesn't need it).

### Empty state
- When no dashboards exist and the page loads, show a centered empty state:
  - Icon + "No dashboards yet"
  - "Create your first dashboard" button (opens the same New Dashboard
    modal)
- When dashboards exist but none is selected (edge case), auto-select the
  first one (already implemented).

### Responsive behavior
- On small screens (< 768 px), the dashboard dropdown should stack above the
  action buttons or become full-width.
- The grid already has responsive breakpoints (`sm`, `xs`, `xxs`) — no
  changes needed there.

---

## Task 5 — Tests

### Frontend (Vitest + Testing Library)
Update or add tests in `Dashboards.test.tsx`:
- The in-page sidebar is no longer rendered.
- The dashboard selector dropdown renders with all dashboard names.
- Selecting a dropdown option switches the active dashboard.
- The "New Dashboard" button opens a modal.
- Submitting the modal creates a dashboard and closes the modal.
- Widgets are draggable/resizable by default for editor users (verify
  `isDraggable` and `isResizable` props on the grid).

### Backend
No backend changes required for this redesign. All API endpoints remain the
same.

### Build
- `tsc -b && vite build` must pass with zero errors.
- `oxlint` on modified files must have zero errors (warnings are ok).

---

## Out of scope
- No changes to `Layout.tsx` or the application sidebar.
- No changes to the backend API.
- No changes to widget rendering (`DashboardWidgetCard`, `ChartRenderer`,
  `InstantFilterTable`).
- No changes to tabs, overview summary, or any modal other than adding the
  New Dashboard modal.

---

## Definition of done
1. The in-page sidebar is gone; the canvas uses the full available width.
2. A compact dashboard dropdown in the header lets users switch dashboards.
3. A "New Dashboard" button opens a creation modal.
4. Widgets are always draggable and resizable for editors without needing to
   toggle edit mode.
5. Existing features (tabs, overview, add insight, settings, delete, refresh,
   fullscreen, bulk save) all work exactly as before.
6. `npm run build` passes. Tests pass.
7. The page looks clean, professional, and uncluttered.
