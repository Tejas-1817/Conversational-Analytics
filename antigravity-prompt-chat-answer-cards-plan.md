# Prompt for Antigravity: Plan "cards for each point" in chat answers

Paste everything below into Antigravity as the task prompt. Attach the
reference screenshots to the same message. This replaces the earlier,
larger redesign prompt: the scope is now only the cards.

---

## Your role and the deliverable

You are planning, not building. **Do not modify any source files in this
task.** Explore the repository, then write one implementation plan at
`docs/plans/chat-answer-cards-plan.md`. I will review it and answer your
open questions before anything is implemented.

## Goal (the only change wanted)

When an assistant answer contains several points, show **each point as its
own card** instead of one long block of text, in the style of the
screenshots. Nothing else about the chat changes, except that the cards appear one
after another as the answer types out (described below).

Copy the card structure only. The screenshots come from another product,
so do not copy its logo, name, wording, icons or exact styling. Use this
app's design tokens (CSS variables in `apps/web/src/index.css`) and its
existing icon library (`lucide-react`).

## What the cards look like (from the screenshots)

- **Summary card:** a small icon badge (a lightbulb in a pale rounded
  square), a bold title such as "Overall assessment", and one paragraph
  with bold inline emphasis.
- **Section label** (for example "Analytics domains") above a
  **two-column grid of cards** with equal heights in each row.
- **Point card:** icon badge, bold title, then labeled paragraphs such as
  "Use:" (source table names shown as inline monospace code), "Possible
  analytics: ..." and "Example dashboards: ...".
- **Tone variants:** a warning card has an orange triangle badge (used for
  risk topics), and a neutral info card has a grey "i" badge and only a
  paragraph.
- **List cards:** a full-width card with a **numbered list** (numbers in
  small circles), and a card with a **bullet list**.
- **Conclusion card:** a green check badge and a short paragraph.

## Out of scope (do not plan any of this)

The "Thought for N seconds" area and step rows with narration, the
collapsible "Composed response" row, the report title and its icon
buttons, follow-up suggestion chips, the message action bar and timestamp,
chart-card controls (type switcher, edit, kebab menu), any change to the
input box or its selectors, the scroll-to-latest button, any new streaming
events, new LLM calls, database migrations, and a structured JSON answer
format. If you think one of these is needed to make the cards work, say so
in the open questions instead of adding it to the plan.

## Context

This is the `analytics-platform` repo: a FastAPI backend in
`services/schema-ingestion/` and a React 19 + TypeScript + Vite frontend in
`apps/web/`. Read `analytics-platform/CLAUDE.md` first and respect it (tests
with every behavior change, no AGPL dependencies, no logging of raw answers
or PII).

Things I believe about the current chat. **Verify each one in the code
before relying on it:**
- The chat page is `apps/web/src/pages/business/ChatInterface.tsx`, with
  helpers in `apps/web/src/components/chat/` (including a markdown
  renderer). The answer arrives as text, probably markdown.
- Text is typed out on screen by a client-side animation, and a
  stop-generation feature exists (the partial text is kept when the user
  stops).
- The SQL accordion, data table, chart and feedback controls sit under the
  answer text and must stay exactly as they are.
- Old conversations are reloaded from the database and must also show cards
  where their text has the right shape.

## What to investigate

1. **Current rendering path.** List the files and functions that turn the
   answer text into elements (message list, markdown renderer, any custom
   components), with line references, and the markdown library in use.
2. **What the answers look like today.** Read the answer synthesizer and
   prompt builder (`app/chat_sql/answer_synthesizer.py`,
   `app/chat_sql/prompt_builder.py`) and describe the typical text shape:
   headings, bold labels, lists, tables, code spans. Use real examples from
   tests or fixtures if any exist.
3. **How cards can be derived with the least change.** Evaluate at least
   these options and recommend one with evidence:
   - **Option 1 (my lean): client only.** Parse the existing markdown (by
     reusing the renderer's own parse tree if it has one) into cards:
     a heading plus its following content becomes a card, a paragraph that
     starts with a bold or "Label:" prefix becomes a labeled field, a list
     becomes a list card. No backend change, no migration, and old messages
     work automatically.
   - **Option 2: Option 1 plus a small prompt tweak** in the answer
     synthesizer that asks the model to use one heading per point and
     "Label:" lines, so the parsing is more reliable. No new schema.
   - **Option 3 (for comparison only): a structured JSON answer.** This is
     out of scope; explain in two or three lines why it is not needed here.

## The plan must cover

- **When to use cards and when not to.** Define clear rules (for example,
  at least two headed sections or a list of three or more items) so that a
  one-sentence answer, a single number, a code block or a plain table stays
  as normal text. Include a one-click or automatic fallback to the current
  rendering whenever the parser is unsure.
- **Card kinds and tone.** Deterministic rules for choosing the icon and
  tone (summary, point, list, warning, info, conclusion), for example by
  heading keywords such as risk, overdue, conclusion or assessment. No LLM
  call. Keep the keyword list in one configurable place.
- **Card-by-card reveal and stop behavior.** The cards must appear one
  at a time, in reading order: first a card appears (its icon badge and
  title), then its text types out progressively inside it, then the next
  card appears and its text types out, and so on until the last card.
  Never start typing into card N+1 before card N has finished. Plan:
  - how the reveal is driven: a queue over the parsed card list that
    reveals the parsed text (not a re-parse of a growing string), so that
    unfinished bold or code markers never show up as raw characters while
    typing; list cards reveal their items one after another;
  - how this works with the current typing animation, with an answer that
    is already complete when the card list is built, and with an answer
    that is still arriving (a new card opens as soon as its heading line is
    complete);
  - the grid: cards in a two-column row appear one at a time in reading
    order, so say how to avoid layout jumps while a card's text grows and
    row heights change;
  - what appears before the first card (intro text) and after the last card
    (SQL accordion, data table, chart, feedback): by default these appear
    once the last card has finished;
  - pacing: a bounded total animation time (for example a few seconds for a
    typical answer, faster for long ones) so long answers do not take long
    to read;
  - scrolling: keep the newest content in view while it grows, stop
    following if the user scrolls up, and keep the scroll behavior that
    already exists;
  - what the user sees when they press Stop partway: the card being typed
    keeps the text shown so far, no later card appears, and the message is
    marked as stopped as it is today;
  - `prefers-reduced-motion` (show everything at once), and no
    announcement of every character to screen readers (announce completed
    cards or the finished answer).
- **Component design.** A small component set (a card container, a labeled
  field, a list card, an icon badge) and the parser module, with props and
  file locations. Say what is reused and what must be refactored in the
  large `ChatInterface.tsx`.
- **Security and correctness.** Keep the existing markdown sanitization (no
  raw HTML injection), keep table and column names as inline code, and make
  sure "copy answer" and any export still use the original markdown text.
- **Layout and accessibility.** Two columns on wide screens that collapse
  to one on narrow screens, dark mode through the existing CSS variables,
  semantic structure (each card is a labeled region with its title as the
  accessible name), decorative icons hidden from screen readers, and
  keyboard and zoom behavior unchanged.
- **Performance.** Behavior with very long answers and with many cards, and
  how often the parser runs (once per change in the received text, not on
  every animation frame).
- **Tests.** Parser unit tests with fixtures (include an answer shaped like
  the screenshots, a short answer, an answer with a table, an answer with a
  code block, malformed markdown, and a partially streamed answer),
  component tests for each card kind, reveal-order tests (one card at a
  time, text types inside the current card, Stop partway keeps the partial
  text and shows no later card, reduced motion shows everything at once), a
  fallback test, and a history-reload test (old messages show their cards
  immediately, without the typing animation).
- **Rollout.** A feature flag (per user or per tenant) with an instant way
  back to the current rendering, and an ordered, sized task list.

## Constraints

- Do not change the backend response shape, the stored messages, or the
  SSE events.
- No new dependency unless you justify it and state its license. No AGPL.
- Existing behavior stays: stop generation, SQL and data accordions,
  charts, feedback, copy, and access control.

## Output format

Write `docs/plans/chat-answer-cards-plan.md` with these headings, in this
order: Summary, Current state (with file references), Recommended approach
and why, Card kinds and rules, Card-by-card reveal and stop behavior, Components,
Accessibility and layout, Risks and mitigations, Rollout, Task breakdown,
Test plan, Open questions.

End with **no more than five open questions** for me, each with your
recommended default.

## Definition of done for this task

- The plan file exists and follows the structure above.
- Every claim about current behavior cites a file and line you read.
- Every card type in the screenshots is covered by a rule in the plan.
- The card-by-card reveal (order, pacing, scrolling, Stop, history) is
  specified.
- No source file outside `docs/plans/` was changed.
