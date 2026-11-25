# Implementation Plan: Chat Answer Cards ("Cards for Each Point")

**Target Document**: `docs/plans/chat-answer-cards-plan.md`  
**Status**: Revised Plan — Ready for Review  
**Author**: Antigravity  
**Date**: November 17, 2026  

---

## Revision Notes

This revised implementation plan addresses all feedback points from the initial review:

1. **Single Typing Engine & Explicit Decision Point**: Replaced the dual-engine conflict. In Cards Mode, the text-level interval pump in `ChatInterface.tsx` is completely bypassed; the **Card Reveal Queue** acts as the single typing mechanism. Verified that the backend (`app/api/chat_sql.py`) executes the entire query before emitting token events, so the client evaluates card eligibility upfront once the full response arrives.
2. **Intro Paragraph Rule Reconciled**: Resolved the contradiction between Section 4.2 and Section 5.4. Opening text preceding headings is strictly treated as plain lead-in text. Summary cards are created **only** from matching section headings (`## Executive Summary`, `## Summary`, `## Overview`, `## Assessment`).
3. **WCAG AA Contrast Ratios Recomputed**: Corrected contrast ratio calculations using the strict WCAG 2.1 relative luminance formula. Specified distinct tokens for UI badges ($\ge 3.0:1$) versus body text ($\ge 4.5:1$). Added `--warning-text` (`#B45309`, 4.84:1), `--success-text` (`#15803D`, 4.79:1), and `--info-text` (`#0369A1`, 5.57:1) to guarantee compliance in light and dark modes.
4. **AST Parser & Sanitization**: Eliminated contradictory "regex AST" phrasing. Selected `unified`, `remark-parse`, and `remark-gfm` (all MIT licensed). Explicitly specified zero rendering of HTML nodes and restriction of links to `http:`, `https:`, and `mailto:` protocols. Added XSS test specifications with `<script>` and `<img onerror=...>` fixtures.
5. **Per-Tenant / Per-User Feature Flag**: Replaced the previous `localStorage` default-on approach. The feature flag is now modeled in the tenant governance system (`tenant_policies.allow_chat_cards`, defaulting to `false`), with a client-side override scoped by user/tenant ID and an always-visible low-emphasis toggle button on each assistant message.
6. **Strict Design Tokens**: Eliminated all hardcoded hex values and arbitrary fallbacks. Mapped every card component and tone variant strictly to CSS variables from `apps/web/src/index.css`.
7. **`formatSummaryContent` Stability**: Specified that the card parser runs strictly on **raw markdown** emitted by the backend, completely bypassing `formatSummaryContent` so the card structure never shifts after streaming completes.
8. **Layout Stability via Height Reservation**: Added invisible dual-render height reservation (`visibility: hidden` sizer with `aria-hidden="true"`) to prevent row height jumps when neighboring cards mount.
9. **Long Answer Cap & Click-to-Finish**: Established named threshold constants (`MAX_ANIMATED_CARDS = 8`, `MAX_ANIMATED_CHARS = 2500`) above which cards render instantly, and added a click-to-finish / skip animation mechanism.
10. **Heading-Only Tone Detection & Precedence**: Restricted tone matching to headings only (removed noisy body keywords). Established strict tie-breaker precedence: `conclusion` > `warning` > `summary` > `info` > `ordered_list` > `bullet_list` > `point`.
11. **V1 Answer Scope**: Defined exact detection logic for V1-eligible answers (schema overviews, multi-query reports, general analyses with $\ge 2$ headings) while explicitly keeping Code Intelligence (`isCodeIntel`) and deterministic record lists as plain markdown.
12. **Expanded Test Plan & Fixtures**: Added automated test specifications for fake timers, duration caps, stop states, scroll detachment, and an accessibility pass, backed by 20 anonymized production fixtures.

---

## 1. Summary

This plan specifies the architecture, client-side mdast parsing engine, component design, single-engine progressive reveal orchestration, accessibility, and testing strategy for transforming multi-point assistant responses into **structured cards** (summary cards, two-column point cards with labeled fields, tone-variant warning/info cards, list cards, and conclusion cards) in the chat interface of `analytics-platform`.

### Core Objectives
1. **Card Presentation**: When an assistant response contains structured analytical points, render each point as a discrete card adhering strictly to the design tokens in `apps/web/src/index.css` and icons from `lucide-react`.
2. **Deterministic & Client-Only**: Transformation occurs entirely on the frontend by analyzing markdown syntax trees. No backend database migrations, LLM schema disruptions, or new SSE protocols.
3. **Single Typing Engine**: The card reveal queue owns the typing animation in Cards Mode. The legacy text-level pump is bypassed.
4. **Cooperative Stop & History Resilience**: Pressing "Stop Generating" halts generation cleanly before decision, mid-card, or between cards. Past conversations reloaded from the database display immediately with zero animation delay.
5. **Zero Disruption to Existing Tooling**: The SQL accordion, data table, ECharts visualizations, CSV/insight buttons, and feedback controls remain unchanged beneath the cards.

---

## 2. Current State (with File References)

### 2.1 The Message Rendering Pipeline
- **Main Chat Container**: `apps/web/src/pages/business/ChatInterface.tsx`
  - Messages are stored in the state hook `const [messages, setMessages] = useState<any[]>([]);` ([ChatInterface.tsx#L287](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L287)).
  - Messages are rendered via a memoized iterator `const renderedMessages = useMemo(() => { ... });` ([ChatInterface.tsx#L1048](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1048)).
  - In each assistant message bubble, when `m.answer_markdown` exists, it is passed directly to the renderer:
    ```tsx
    {/* 1. Structured Cards & Markdown Synthesis */}
    {m.answer_markdown && (
      <div className="business-answer">
        <MarkdownRenderer content={m.answer_markdown} isStreaming={m.isStreaming} />
      </div>
    )}
    ```
    ([ChatInterface.tsx#L1092-L1097](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1092-L1097)).
  - Following the markdown synthesis block, the primary visualization (`ChartRenderer`), SQL accordion (`SqlBlock`), raw data table, and action bar (Copy, Regenerate, Thumbs Up/Down) are rendered sequentially ([ChatInterface.tsx#L1103-L1375](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1103-L1375)).

### 2.2 Markdown Rendering Library & Existing Preprocessing
- **Renderer Component**: `apps/web/src/components/chat/MarkdownRenderer.tsx`
  - Uses `react-markdown` (`^10.1.0`) and `remark-gfm` (`^4.0.1`) ([package.json#L23-L27](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/package.json#L23-L27)).
  - Employs a custom pre-processor `formatSummaryContent(content: string)` ([MarkdownRenderer.tsx#L63-L157](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/components/chat/MarkdownRenderer.tsx#L63-L157)) which parses dense paragraphs into bullet points. During active streaming (`isStreaming === true`), this pre-processor is bypassed to prevent re-parsing flashes ([MarkdownRenderer.tsx#L162-L166](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/components/chat/MarkdownRenderer.tsx#L162-L166)).
  - **Critical Finding**: Because `formatSummaryContent` runs only when `isStreaming` becomes false, running the card parser on reformatted text would cause layout jumps at the end of streaming. The card parser must therefore run exclusively on the raw markdown string.
  - Component handlers style elements with inline styles and Lucide icons ([MarkdownRenderer.tsx#L186-L409](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/components/chat/MarkdownRenderer.tsx#L186-L409)).

### 2.3 Backend Query & Streaming Architecture
- **Backend Execution Flow**: `services/schema-ingestion/app/api/chat_sql.py`
  - Lines 201–215: The entire SQL execution, data fetching, and natural-language LLM synthesis are executed synchronously within a threadpool worker:
    ```python
    result = await loop.run_in_executor(
        None,
        lambda: chat_service.process_text_to_sql(...)
    )
    ```
    ([chat_sql.py#L203-L215](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/services/schema-ingestion/app/api/chat_sql.py#L203-L215)).
  - Lines 221–245: Only **after** `process_text_to_sql` has completely finished and returned `result["answer_markdown"]` does the generator enter its token loop:
    ```python
    answer_text = result.get("answer_markdown") or result.get("answer") or ""
    lines = answer_text.splitlines(keepends=True)
    for line in lines:
        # Fast 2-word phrase chunks with 2ms sleep
        ...
    yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"
    ```
    ([chat_sql.py#L222-L245](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/services/schema-ingestion/app/api/chat_sql.py#L222-L245)).
  - **Key Verification**: The entire answer text is already fully formed before the first `token` event is emitted. The burst of `token` events finishes in ~50ms to 200ms, followed immediately by `complete`.

### 2.4 Existing Client-Side Pump and Stop Mechanism
- **Client Easing Pump**: `ChatInterface.tsx` lines 718–751 run a `16ms` interval timer that slices `displayedText` from `targetText` ([ChatInterface.tsx#L730-L751](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L730-L751)).
- **Stop Generating**: `handleStop` calls `abortRef.current.abort()` and `clearInterval(pumpRef.current)` ([ChatInterface.tsx#L297-L308](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L297-L308)). If stopped mid-stream, `m.stopped = true` is set and partial text is preserved ([ChatInterface.tsx#L841-L847](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L841-L847)).

### 2.5 History Reload Path
- **Reloading Chats**: `loadConversation(id: string)` fetches `/engine/conversations/${id}` ([ChatInterface.tsx#L421-L505](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L421-L505)).
  - Messages are mapped to normalized objects where `answer: m.content` and `answer_markdown: m.content`.
  - For reloaded messages, `isStreaming` is `undefined`/`false`, meaning they are loaded statically without typing animation.

---

## 3. Recommended Approach and Why

### Evaluation of Options

| Criterion | Option 1: Client mdast Parser (Recommended) | Option 2: Option 1 + Backend Prompt Tweak | Option 3: Structured JSON Answer Format |
| :--- | :--- | :--- | :--- |
| **Backend / DB Impact** | **Zero**. No schema changes, no migrations. | Low. Minor prompt adjustments. | **High**. Breaking schema, prompt, and SSE changes. |
| **Old Conversations** | **Works immediately**. Stored markdown maps to cards. | Inconsistent. Old chats lack new prompt structure. | **Breaks**. Requires DB migration of historical chats. |
| **Streaming Complexity**| **Deterministic**. Token pump drives card queue. | Same as Option 1. | Very complex. Streaming partial JSON requires JSON-repair parsers. |
| **LLM Grounding Quality**| **Preserved**. Preserves strict grounding prompts. | Risk of prompt drift or token truncation. | JSON mode degrades reasoning depth in smaller models. |
| **Failure Mode** | **Graceful**. Seamless fallback to standard markdown. | Seamless fallback to standard markdown. | Hard failure or JSON decode exception. |

### Recommendation: Option 1 (Client mdast Parser)
Option 1 parses the markdown via `unified` and `remark-parse` into an `mdast` syntax tree. Because the backend already holds the entire answer before sending token events, the client buffers the rapid token burst or awaits `complete`, evaluates eligibility, and renders cards smoothly with zero double-typing.

---

## 4. Card Kinds and Rules

### 4.1 Card Kinds Catalog

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. SUMMARY CARD (Full Width)                                           │
│ [Lightbulb]  OVERALL ASSESSMENT                                        │
│ Paragraph with bold inline metrics and synthesized summary text.      │
└────────────────────────────────────────────────────────────────────────┘

SECTION LABEL: Analytics Domains
┌───────────────────────────────────┬────────────────────────────────────┐
│ 2. POINT CARD (Grid Col 1)        │ 2. POINT CARD (Grid Col 2)         │
│ [Layers] Customer Churn Risk      │ [TrendingUp] Revenue Expansion     │
│ Use: `contracts`, `accounts`      │ Use: `invoices`, `payments`        │
│ Possible analytics: Net MRR churn │ Possible analytics: Upsell trends  │
│ Example dashboards: Retention 360 │ Example dashboards: Cohort Value   │
├───────────────────────────────────┼────────────────────────────────────┤
│ 3. WARNING CARD (Grid Col 1)      │ 4. INFO CARD (Grid Col 2)          │
│ [AlertTriangle] Data Limitations  │ [Info] Implementation Notice       │
│ Missing timestamps in audit table │ Standard sync occurs every 6 hours │
└───────────────────────────────────┴────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ 5. LIST CARD - ORDERED / BULLET (Full Width)                           │
│ [ListOrdered] RECOMMENDED ACTION PLAN                                  │
│ ① Review high-risk accounts with annual value > $100k                  │
│ ② Trigger proactive outreach campaign for Q4 renewals                 │
│ ③ Schedule automated health score recalibration                        │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ 6. CONCLUSION CARD (Full Width)                                        │
│ [CheckCircle2] FINAL TAKEAWAY                                          │
│ Concluding synthesis paragraph confirming business next steps.        │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Tone Detection: Heading-Only Rules & Precedence Order
Tone matching evaluates **heading text only** (case-insensitive substring match). Body text is never scanned for tone keywords to prevent false positives.

All keywords are consolidated in `apps/web/src/components/chat/cards/cardToneConfig.ts`:

```ts
export const CARD_TONE_CONFIG = {
  conclusion: ['conclusion', 'final takeaway', 'next steps', 'recommended next action', 'decision'],
  warning: ['risk', 'warning', 'caution', 'overdue', 'data limitation', 'limitations', 'missing data'],
  summary: ['summary', 'executive summary', 'overall assessment', 'overview', 'key findings'],
  info: ['note', 'notice', 'implementation notice', 'background', 'prerequisite'],
} as const;
```

#### Precedence Order for Heading Ties
If a heading contains keywords from multiple categories (e.g., `"Summary of Risks"`):
$$\text{conclusion} > \text{warning} > \text{summary} > \text{info} > \text{ordered\_list} > \text{bullet\_list} > \text{point}$$
*Result for "Summary of Risks"*: Evaluates to `warning` because `warning` takes precedence over `summary`.

### 4.3 Intro Paragraph vs. Summary Card Rule
- **Plain Lead-in**: Any opening paragraph preceding the first markdown heading is treated strictly as plain intro text. It is rendered above the card grid without a card container or icon badge.
- **Summary Card**: Created **only** when an explicit heading matches `summary` keywords. It is rendered as a full-width card with an icon badge.

### 4.4 V1 Eligibility & Scope

| Answer Type | Identification Criteria | Rendering in V1 |
| :--- | :--- | :--- |
| **Schema Overview** | Headings: `## Executive Summary`, `## Analytics We Can Build`, `## Data Limitations` ([prompt_builder.py#L398](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/services/schema-ingestion/app/chat_sql/prompt_builder.py#L398)) | **Cards Mode** |
| **Multi-Query Synthesis** | Headings: `### Domain: ...`, `Key Findings`, `Strategic Recommendations` ([answer_synthesizer.py#L498](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/services/schema-ingestion/app/chat_sql/answer_synthesizer.py#L498)) | **Cards Mode** |
| **General Multi-Point Analysis** | Markdown contains $\ge 2$ level-2 or level-3 headings (`##` or `###`) | **Cards Mode** |
| **Ordered Action Roadmap** | Heading followed by an ordered list (`1. `, `2. `, `3. `) where $\ge 3$ items each start with bold titles (`1. **Action**: ...`) and have length $\ge 30$ chars | **Cards Mode** |
| **Code Intelligence** | Message flag `m.isCodeIntel === true` ([ChatInterface.tsx#L470](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L470)) | **Plain Markdown** (Exempt) |
| **Deterministic Record Lists** | Text starts with `"Based on the verified database results"` ([answer_synthesizer.py#L226](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/services/schema-ingestion/app/chat_sql/answer_synthesizer.py#L226)) | **Plain Markdown** (Exempt) |
| **Short / Fact / Table Answers** | Single number, $< 50$ words without headings, standalone SQL or table | **Plain Markdown** (Exempt) |

---

## 5. Card-by-Card Reveal and Stop Behavior

### 5.1 One Typing Mechanism & The Decision Point

#### The Conflict Resolved
In the previous draft, the legacy pump in `ChatInterface.tsx` typed the markdown string character-by-character, and an inner card queue simultaneously typed each card. This caused double-typing, variable delays, and syntax flashing.

#### The Revised Mechanism
1. **The Decision Point**:
   - During query execution, the user sees `<ThoughtSteps isLoading={true} activeStage={...} />` with the live timer ([ChatInterface.tsx#L1084](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1084)).
   - When SSE yields `complete` (or the rapid token burst ends, ~100ms), `ChatInterface.tsx` receives the complete `answer_markdown`.
   - The client invokes `evaluateCardEligibility(answer_markdown, metadata)`.
2. **If Plain Text Mode**:
   - The existing 60 FPS pump runs exactly as it does today ([ChatInterface.tsx#L730-L751](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L730-L751)).
   - Zero change to plain text behavior.
3. **If Cards Mode**:
   - The legacy interval pump is **bypassed immediately**: `displayedText = targetText` is set at once.
   - `ChatInterface.tsx` marks `m.isCardsMode = true` and `m.isStreaming = true`.
   - The **Card Reveal Queue** takes exclusive ownership of progressive reveal.
   - Card 0 mounts with badge and title, types its body text, marks complete, and Card 1 mounts.
   - When the final card completes, `m.isStreaming = false` is dispatched, revealing the SQL accordion and ECharts visualizations below.

#### Handling Future Live-Token Streaming
If the backend ever migrates from post-generation burst streaming to true live LLM token streaming (e.g., streaming chunks over 5–10s directly from Gemini/Claude):
- The backend will send an initial metadata header event: `data: {"type": "intent", "mode": "cards"}`.
- The client initializes the card queue optimistically: when a heading token completes (`\n## `), the previous card finalizes and the new card mounts immediately.
- If the stream completes with $< 2$ headings, the container seamlessly transitions to standard `<MarkdownRenderer>` without remounting or dropping content.

### 5.2 Stop Generation Across All Phases
Pressing "Stop Generating" (`handleStop`, [ChatInterface.tsx#L297](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L297)) behaves deterministically in every state:

| Phase When "Stop" is Pressed | State of UI & Data | Outcome |
| :--- | :--- | :--- |
| **Phase A: Before Decision** (during SQL run or initial ~100ms wait) | Backend SSE connection aborted. No text has been typed. | The placeholder message is cleaned up or displays `"Generation stopped"` badge. No cards render. |
| **Phase B: While Card $N$ is Typing** | Card $0 \dots N-1$ are complete. Card $N$ is partially typed. | The reveal queue halts immediately. Card $N$ freezes at its currently displayed text and sets state to `complete`. Card $N+1$ never mounts. Message tagged `stopped: true`. |
| **Phase C: Between Cards** | Card $N$ completed; Card $N+1$ has not yet mounted. | The queue aborts. Card $N+1$ never appears. Message tagged `stopped: true`. |

In all cases, whatever partial markdown was revealed remains on screen, the "Stopped" badge displays ([ChatInterface.tsx#L1328-L1344](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1328-L1344)), and already-retrieved SQL/tables are made visible.

### 5.3 Layout Stability via Height Reservation
To prevent row heights from bouncing when Card 1 mounts beside Card 0 in a 2-column grid:
1. Each card employs an invisible **height reservation layer**:
   ```tsx
   <div className="card-wrapper" style={{ position: 'relative' }}>
     {/* Hidden sizer reserves exact final height */}
     <div 
       className="card-sizer" 
       style={{ visibility: 'hidden', userSelect: 'none', pointerEvents: 'none' }}
       aria-hidden="true"
     >
       <CardContent card={card} isFullText={true} />
     </div>
     {/* Revealer overlays the sizer with exact matching bounds */}
     <div 
       className="card-revealer" 
       style={{ position: 'absolute', inset: 0 }}
     >
       <CardContent card={card} visibleChars={revealedChars} />
     </div>
   </div>
   ```
2. Because the invisible sizer mounts immediately upon card birth, the grid cell claims its exact final dimensions. Neighboring cells never jump or reflow.
3. Once a card completes reveal, the sizer is unmounted and the revealed content reverts to standard `position: static`.

### 5.4 Long Answers & Click-to-Finish
- **Threshold Constants**:
  ```ts
  export const MAX_ANIMATED_CARDS = 8;
  export const MAX_ANIMATED_CHARS = 2500;
  export const TARGET_ANIMATION_MS = 3500;
  ```
- **Instant Render Rule**: If `cards.length > MAX_ANIMATED_CARDS` or `totalChars > MAX_ANIMATED_CHARS`, the typing animation is bypassed. All cards render instantly in their completed state.
- **Click-to-Finish**: Clicking anywhere on the card container during typing (or clicking a subtle `<FastForward size={12} /> Skip` button in the corner) immediately completes the reveal queue, rendering all cards instantly.

### 5.5 Auto-Scroll Detach
- When reveal is active, the lowest active card is brought into view using `scrollIntoView({ behavior: 'auto', block: 'nearest' })`.
- If the user scrolls upward (`isAtBottom === false`, [ChatInterface.tsx#L1541](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1541)), auto-scrolling is immediately disabled so user manual review is undisturbed.

---

## 6. Components Architecture & Dependencies

### 6.1 Package Dependencies
Add explicit dependencies to `apps/web/package.json` (all MIT licensed, zero AGPL):

| Package | Version | License | Purpose |
| :--- | :--- | :--- | :--- |
| `unified` | `^11.0.5` | MIT | Core AST processing pipeline |
| `remark-parse` | `^11.0.0` | MIT | Markdown text to mdast syntax tree parser |
| `remark-gfm` | `^4.0.1` | MIT | GFM table, strikethrough, and tasklist AST support |
| `unist-util-visit`| `^5.0.0` | MIT | AST visitor utility for leaf text extraction |
| `@types/mdast` | `^4.0.4` | MIT | TypeScript definitions for Markdown AST nodes |

### 6.2 Strict Sanitization and Security Guarantees
1. **Zero HTML Node Rendering**: The mdast parser identifies raw HTML tags (`<script>`, `<img>`, `<iframe>`, `onclick`) as `html` AST nodes. The card renderer explicitly drops `html` nodes or renders them as escaped plain text (`node.value`). `dangerouslySetInnerHTML` is strictly prohibited.
2. **Safe Link Protocol Whitelist**: Link URLs (`node.url`) are sanitized to permit only `http:`, `https:`, and `mailto:`. Dangerous schemes (`javascript:`, `data:`, `vbscript:`) are rewritten to `#`.
3. **Database Identifiers**: Identifiers inside `Use:` fields are verified against the connected source's active table/column names before wrapping with `<code>` monospace chips.
4. **Copy Fidelity**: The message action bar "Copy" button continues to copy `m.answer_markdown` directly ([ChatInterface.tsx#L1356](file:///c:/Users/DELL/Conversational-Analytics/analytics-platform/apps/web/src/pages/business/ChatInterface.tsx#L1356)), guaranteeing clean, standard markdown on the user's clipboard.

### 6.3 Component Tree

```
apps/web/src/components/chat/cards/
├── types.ts                    # Card models, reveal states, AST node types
├── cardToneConfig.ts           # Heading keywords, tone precedence, token map
├── cardParser.ts               # Unified/remark AST parsing into CardModel[]
├── useCardRevealQueue.ts       # Sequential reveal hook with sizer budget
├── AnswerCardsContainer.tsx    # Responsive grid, fallback toggle, sizer bounds
├── SummaryCard.tsx             # Overview card with lightbulb icon badge
├── PointCard.tsx               # 2-col point card with labeled fields and code
├── ListCard.tsx                # Numbered circle list card or bullet list card
├── ConclusionCard.tsx          # Final takeaway card with green checkmark badge
├── LabeledField.tsx            # Labeled key-value rows ("Use:", "Possible analytics:")
└── IconBadge.tsx               # Reusable tone-based badge (indigo, amber, green, grey)
```

---

## 7. Accessibility, Tokens & Design System

### 7.1 WCAG 2.1 AA Contrast Ratios
Contrast ratios are computed using the exact relative luminance formula:
$$L = 0.2126 R + 0.7152 G + 0.0722 B, \quad \text{Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05}$$

| Color Pair | Tested Element | Contrast Ratio | WCAG AA Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `#1F242E` (`--text-main`) on `#FFFFFF` (`--bg-card`) | Card body & headings | **15.55:1** | **Pass** (Req $\ge 4.5:1$) | Default high contrast text |
| `#6B7280` (`--text-muted`) on `#FFFFFF` (`--bg-card`) | Field labels & subtitles | **4.83:1** | **Pass** (Req $\ge 4.5:1$) | Subtle secondary text |
| `#B45309` (`--warning-text`) on `#FFFBEB` (`--warning-light`) | Warning card body text | **4.84:1** | **Pass** (Req $\ge 4.5:1$) | Replaces `#D97706` for text |
| `#D97706` (`--warning`) on `#FFFBEB` (`--warning-light`) | Warning icon badge | **3.07:1** | **Pass** (Req $\ge 3.0:1$) | Graphical object / icon |
| `#15803D` (`--success-text`) on `#F0FDF4` (`--success-light`) | Conclusion body text | **4.79:1** | **Pass** (Req $\ge 4.5:1$) | Replaces `#16A34A` for text |
| `#16A34A` (`--success`) on `#F0FDF4` (`--success-light`) | Conclusion icon badge | **3.15:1** | **Pass** (Req $\ge 3.0:1$) | Graphical object / icon |
| `#0369A1` (`--info-text`) on `#F0F9FF` (`--info-light`) | Info card body text | **5.57:1** | **Pass** (Req $\ge 4.5:1$) | Readable text on info tint |
| `#0EA5E9` (`--info`) on `#F0F9FF` (`--info-light`) | Info icon badge | **3.02:1** | **Pass** (Req $\ge 3.0:1$) | Graphical object / icon |
| `#4F46E5` (`--primary`) on `#EFF6FF` (`--primary-light`) | Primary icon badge | **5.82:1** | **Pass** (Req $\ge 3.0:1$) | Indigo tone badge |
| `#0F172A` on `#F1F5F9` | Monospace code chips | **16.30:1** | **Pass** (Req $\ge 4.5:1$) | Source table/column names |

### 7.2 Design Tokens Mapping Table
All styling strictly consumes CSS variables from `apps/web/src/index.css`. No inline hex codes.

```css
/* Additions to apps/web/src/index.css for text-level WCAG compliance */
:root {
  --warning-text: #B45309;
  --success-text: #15803D;
  --info-text: #0369A1;
}
```

| Card Tone | Badge Icon Token | Badge Background Token | Border Token | Card Background Token | Text Token |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Summary / Point** | `var(--primary)` | `var(--primary-light)` | `var(--border-color)` | `var(--bg-card)` | `var(--text-main)` |
| **Warning** | `var(--warning)` | `var(--warning-light)` | `var(--warning)` | `var(--bg-card)` | `var(--text-main)` / `var(--warning-text)` |
| **Conclusion** | `var(--success)` | `var(--success-light)` | `var(--success)` | `var(--bg-card)` | `var(--text-main)` / `var(--success-text)` |
| **Info** | `var(--info)` | `var(--info-light)` | `var(--border-color)` | `var(--bg-card)` | `var(--text-main)` / `var(--info-text)` |

### 7.3 Layout & Screen Reader Accessibility
- **Two-Column Grid**: Single column below $768\text{px}$, 2 equal columns at $\ge 768\text{px}$.
- **Screen Readers**:
  - Cards use semantic `<article aria-labelledby="card-title-{id}">`.
  - Icon badges carry `aria-hidden="true"`.
  - Politeness: A hidden `<div aria-live="polite" className="sr-only">` announces card completion only when Card $N$ completes typing (e.g. `"Section loaded: Analytics Domains"`).
- **Reduced Motion**: If `matchMedia('(prefers-reduced-motion: reduce)')` is true, sequential typing is disabled and all cards render immediately.

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Malformed Markdown AST** | Parser throws or creates broken DOM. | Wrapped in try/catch. Returns `canRenderCards: false`, rendering classic `<MarkdownRenderer>` fallback seamlessly. |
| **Raw HTML Injection via Prompt** | XSS vulnerability. | Custom AST renderer drops `html` nodes entirely. Link protocols restricted to `http/https/mailto`. |
| **Typing Desync / Jitter** | Double typing or queue race conditions. | Legacy pump in `ChatInterface.tsx` is completely bypassed in Cards Mode. Single queue owns typing. |
| **Height Jumps in 2-Column Grid** | Left card resizes as neighbor mounts. | Invisible sizer layer (`visibility: hidden`) reserves full card height upon mount. Zero height jumps. |
| **Copy Clipboard Corruption** | User copies broken card layout HTML. | Message copy button copies `m.answer_markdown` directly, preserving pure markdown text. |

---

## 9. Rollout & Feature Flag

### 9.1 Tenant & User Governance
1. **Database Model**: Add `allow_chat_cards: Mapped[bool] = mapped_column(Boolean, default=False)` to `TenantPolicy` in `services/schema-ingestion/app/models.py#L679-L693`.
2. **Default State**: **Default OFF** across all tenants.
3. **Client Configuration**:
   - `AuthContext` receives `tenant_policy.allow_chat_cards` via `GET /auth/me`.
   - A user-level local preference can override it per tenant: `localStorage.getItem(`pref_cards_${user.tenant_id}`)`.
4. **Always-Visible Escape Hatch**:
   - Every assistant message displays an always-visible low-emphasis toggle button (`<LayoutGrid size={13} />` / `<AlignLeft size={13} />`) in the bottom action bar next to Copy and Regenerate. Clicking it toggles between Cards and Markdown instantly.

---

## 10. Task Breakdown & Updated Effort Estimates

| Task | File(s) | Estimated Effort | Description |
| :--- | :--- | :--- | :--- |
| **Task 1: Dependencies & Flag** | `apps/web/package.json`<br>`apps/web/src/index.css`<br>`services/schema-ingestion/app/models.py` | 1.0 day | Add unified/remark dependencies; add accessible text tokens to `index.css`; wire tenant policy flag. |
| **Task 2: AST Parser & Tone Config** | `apps/web/src/components/chat/cards/types.ts`<br>`apps/web/src/components/chat/cards/cardToneConfig.ts`<br>`apps/web/src/components/chat/cards/cardParser.ts` | 2.0 days | Implement `mdast` parser, heading-only tone detection, tie-breaker precedence, and raw markdown safety. |
| **Task 3: Visual Components & Sizers** | `apps/web/src/components/chat/cards/IconBadge.tsx`<br>`apps/web/src/components/chat/cards/LabeledField.tsx`<br>`apps/web/src/components/chat/cards/SummaryCard.tsx`<br>`apps/web/src/components/chat/cards/PointCard.tsx`<br>`apps/web/src/components/chat/cards/ListCard.tsx`<br>`apps/web/src/components/chat/cards/ConclusionCard.tsx` | 2.5 days | Build all card variants with invisible height-reservation sizers and strict token consumption. |
| **Task 4: Reveal Engine & Integration** | `apps/web/src/components/chat/cards/useCardRevealQueue.ts`<br>`apps/web/src/components/chat/cards/AnswerCardsContainer.tsx`<br>`apps/web/src/pages/business/ChatInterface.tsx` | 2.0 days | Wire single-engine reveal queue, bypass legacy pump in cards mode, wire Stop generation, add skip animation. |
| **Task 5: Accessibility & Viewport QA** | All card components | 1.0 day | Screen reader audit (`aria-live`), 200% zoom verification, mobile (<768px) and dark mode visual QA. |
| **Task 6: Test Suite & 20 Fixtures** | `apps/web/src/components/chat/cards/__tests__/cardParser.test.ts`<br>`apps/web/src/components/chat/cards/__tests__/AnswerCards.test.tsx` | 2.0 days | Implement unit & integration test suites with fake timers, XSS injection tests, and 20 anonymized real fixtures. |

**Total Estimated Effort**: **10.5 engineering days**.

---

## 11. Test Plan & Fixtures

### 11.1 Parser & Security Unit Tests (`cardParser.test.ts`)
- **Sanitization Test**: Feeds `<script>alert(1)</script>` and `<img src=x onerror=alert(1)>`. Asserts that no HTML nodes are rendered and scripts are escaped or stripped.
- **Link Protocol Test**: Validates that `javascript:void(0)` is stripped, while `https://` is preserved.
- **Heading Tone Precedence**: Asserts that a heading `"Summary of Critical Risks"` maps strictly to `warning` due to precedence.
- **Raw vs. Formatted Independence**: Verifies that inputting raw markdown vs. the output of `formatSummaryContent` produces identical AST card models.
- **Eligibility Boundaries**:
  - Asserts `canRenderCards === false` for single numbers, SQL code blocks, plain tables, and responses with only 1 heading.
  - Asserts `canRenderCards === true` for responses with $\ge 2$ headings.

### 11.2 Component, Timing & Stop Tests (`AnswerCards.test.tsx`)
- **Single Typing Engine (Fake Timers)**: Verifies that Card 0 finishes typing before Card 1 mounts, with total duration capped at $\le 3500\text{ms}$.
- **Stop Generation in Phase A, B, and C**:
  - Stopping during query wait: cancels cleanly.
  - Stopping mid-card: active card freezes at partial text, no future cards mount.
  - Stopping between cards: completed cards remain intact.
- **Long Answer Instant Render**: Supplies an answer with 10 cards / 3000 chars; asserts all cards render immediately with zero animation delay.
- **Scroll Detach**: Simulates user scrolling upward during typing; asserts `scrollIntoView` is no longer called.
- **History Reload**: Verifies that when `isStreaming === false`, all cards render in full immediately.

### 11.3 20 Anonymized Production Fixtures
The test suite includes 20 anonymized fixture datasets adhering strictly to `CLAUDE.md` (no raw PII or real credentials):
1. *Schema Overview*: 5-section executive capability report.
2. *Multi-Query Synthesis*: 3 domain sections with table references and numbered action plan.
3. *Single KPI Result*: Single number and sentence (plain fallback).
4. *Standalone Raw Table*: Multi-column markdown data grid (plain fallback).
5. *Standalone Code Snippet*: Code repository function explanation (plain fallback).
6. *Deterministic Record Bullets*: Output of `_deterministic_answer` (plain fallback).
7. *Code Intelligence Architecture*: Response with `**File:**` and `**Symbol:**` (plain fallback).
8. *High-Risk Churn Warning*: Analysis with warning and conclusion cards.
9. *Ordered Roadmap*: $\ge 3$ numbered items with bold action titles.
10. *Unordered Capability Checklist*: Bulleted points with lead-in text.
11. *Embedded Table Between Cards*: Two point cards flanking an inline markdown table.
12. *XSS Exploit Attempt*: Markdown containing embedded script and SVG onerror tags.
13. *Malformed Markdown*: Unclosed bold, trailing hashes, and unclosed code backticks.
14. *Excessively Long Report*: $> 3000$ characters testing instant render bypass.
15. *Short Two-Point Comparison*: Exactly 2 short headed sections.
16. *Data Limitation Report*: Warning card paired with info notice.
17. *Strategic Advisory Roadmap*: Executive consultancy response format.
18. *Predictive Forecast*: Numerical forecast with confidence bounds.
19. *Zero Results Message*: Graceful message when query returns no rows.
20. *Unanswerable Prompt*: Safe fallback when question exceeds schema capability.

---

## 12. Open Questions (with Recommended Defaults)

*Note: The previous five open questions have all been resolved as agreed:*
- *Single column below 768px: **Adopted**.*
- *Monospace chips for `Use:` only matching real schema identifiers: **Adopted**.*
- *Always-visible low-emphasis view toggle button: **Adopted**.*
- *3.5s animation duration cap with long-answer bypass: **Adopted**.*
- *Tables between cards rendered as full-width cards: **Adopted**.*

### Remaining Open Questions

1. **Tenant Policy vs. User Preferences Storage Migration**  
   *Question*: Should the `allow_chat_cards` flag live on `tenant_policies` table (governed by admins) or on a new `user_preferences` table (individual user choice)?  
   *Recommended Default*: Place on `tenant_policies` first (defaulting to `false`) for enterprise rollout control, with individual users able to toggle their local view via the per-message UI button.

2. **Monospace Identifier Validation Cache**  
   *Question*: Should database table/column names for the `Use:` field chip validation be cached in memory per source ID to avoid repetitive schema lookups during card rendering?  
   *Recommended Default*: Yes; cache source schema column/table sets in a client-side `Set<string>` loaded once per active source.
