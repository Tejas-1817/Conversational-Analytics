# Prompt for Antigravity: Add a "Stop generating" option to the chat

Paste everything below into Antigravity as the task prompt.

---

## Context

This is the `analytics-platform` repo (FastAPI backend at
`services/schema-ingestion/`, React frontend at `apps/web/`). Users ask
analytical questions in the chat page (`apps/web/src/pages/business/ChatInterface.tsx`)
and the answer comes back from the backend.

Read `analytics-platform/CLAUDE.md` first. Do not weaken any invariant in
it (tenant isolation, audit logging, read-only customer data, and so on).
Every behavior change must ship with tests.

**Feature:** like ChatGPT and Claude, after a user submits a question they
must be able to stop the answer while it is still being produced. This is
a **Stop**, not a resumable pause: the partial answer stays on screen and
the generation ends. The existing Regenerate button already covers
retrying.

### How the chat works today (verify each point in the code before changing anything)

1. `sendMessage` in `ChatInterface.tsx` sends SQL questions to
   `POST /api/v1/chat/sql/stream` with `fetch` and reads the response as
   Server-Sent Events (`sql`, `token`, `complete`, `error` events; the
   server also sends `status` events that the client currently ignores).
   Questions for a selected git repository go to
   `POST /code-repos/{id}/query` through `fetchApi` and are not streamed.
2. **The streaming is simulated.** In `app/api/chat_sql.py`,
   `generate_sql_from_question_stream` runs the whole pipeline
   (`chat_service.process_text_to_sql`, which includes all LLM calls, SQL
   execution and answer synthesis) inside `loop.run_in_executor(...)`.
   Only after it finishes does the endpoint split the finished answer into
   `token` events. So nearly all of the waiting happens **before the first
   token**, and that is where Stop matters most.
3. The client types the text out with its own 16 ms `setInterval` "pump"
   that lives as a local variable inside a `Promise` in `sendMessage`. The
   pump only resolves when `isStreamFinished` becomes true.
4. Aborting the HTTP request does not stop the worker thread. The LLM
   calls (up to about six per question, which matters for Gemini quota)
   and SQL execution continue, and the assistant message is still saved.
5. The textarea has `disabled={loading}`, Enter is guarded by `!loading`,
   and the send button has `disabled={loading || !input.trim()}`.
6. `fetchApi` in `apps/web/src/services/api.ts` spreads its options into
   `fetch`, so passing `signal` through it works.

Work through the tasks in order. Each has current behavior, desired
behavior and requirements.

---

## Task 1: Frontend abort plumbing and pump cleanup

**Current behavior:** There is no way to cancel an in-flight request. The
pump interval id is not reachable from outside its `Promise`, so it cannot
be cleared.

**Desired behavior:** The request can be aborted and the typing animation
stops immediately with no leaked timers.

**Requirements:**
- Add `abortRef = useRef<AbortController | null>(null)` and
  `pumpRef = useRef<number | null>(null)` (use the correct timer type for
  this project's TypeScript config).
- In `sendMessage`, create a new `AbortController` for each submission,
  store it in `abortRef`, and pass `signal` to the `/api/v1/chat/sql/stream`
  `fetch` and to the `fetchApi` call for `/code-repos/{id}/query`.
- Move the pump's interval id into `pumpRef` so it can be cleared from
  outside.
- Add `handleStop`: abort the controller, clear `pumpRef`, and set
  `isStreamFinished = true` so `pumpPromise` resolves instead of hanging.
  Make `handleStop` safe to call when nothing is running, and make it a
  no-op once the stream has finished (avoid a race at completion).
- In the `catch` block of `sendMessage`, check `err.name === 'AbortError'`
  **before** the existing error handling so the user never sees a
  "Failed to process query" bubble after clicking Stop. In that branch:
  - If any text had been typed, keep it as the assistant message with
    `isStreaming: false` and `stopped: true`. If `finalData` has already
    arrived, also attach its SQL, rows, columns and chart fields.
  - If nothing had been typed, remove the empty placeholder assistant
    message.
- In `finally`, always `setLoading(false)` and set `abortRef.current = null`.
- Apply the same abort handling to `handleRegenerateResponse`. If a
  regenerate request is aborted, do not call `loadConversation` afterwards.
- Check whether the legacy `pollMessageStatus` polling path is still used
  by any live code path. If it is, make Stop clear its interval too. If it
  is dead code, leave it alone and say so in the PR description.

---

## Task 2: Stop button and keyboard shortcut

**Current behavior:** While loading, the send button is just disabled.

**Desired behavior:** While a response is loading, the send button becomes
a Stop button.

**Requirements:**
- While `loading` is true, render a Stop button in place of the Send
  button: `type="button"`, `onClick={handleStop}`, the lucide `Square`
  icon (add it to the existing `lucide-react` import), and
  `aria-label="Stop generating"`. Keep the existing round 32px styling and
  CSS variables; do not hard-code new colors.
- Pressing **Esc** while loading calls `handleStop`. Register the listener
  only while loading and remove it on cleanup.
- Keep the Send button behavior unchanged when not loading, including the
  `Enter` to send, `Shift+Enter` for a new line behavior.
- After Stop, re-enable the textarea and move focus back into it.
- Show a small, unobtrusive "Stopped" label on assistant messages whose
  `stopped` flag is true. Do not change how finished messages look.
- Optional but welcome: surface the `status` SSE events
  (`planning`, `executing`) in the existing `ThoughtSteps` loader so users
  can see what is happening before the first token.

---

## Task 3: Do not orphan conversations when a first question is stopped

**Current behavior:** The client only learns `conversation_id` from the
final `complete` event. If a user stops their first question in a new
conversation, the server may already have created a conversation that the
client never saw, so the next question starts a second one.

**Desired behavior:** The client always knows the conversation id, even
after a stop.

**Requirements:**
- In `generate_sql_from_question_stream`, send the conversation id in an
  early event (for example `{"type": "meta", "conversation_id": ...}`)
  as soon as it is known. If the conversation is only created inside
  `process_text_to_sql`, create or resolve it before the heavy work
  starts, without changing behavior for callers that do not use streaming.
- In `ChatInterface.tsx`, handle the `meta` event by setting `convId` and
  `localStorage.active_conversation_id`.
- Also call `loadConversationsList()` in the stop path, as the success
  path already does.

---

## Task 4: Backend cooperative cancellation

**Current behavior:** When the client disconnects, the pipeline keeps
running in its worker thread.

**Desired behavior:** A disconnect or Stop halts further pipeline work at
the next safe point, and a cancelled question does not save an assistant
message.

**Requirements:**
- In `app/chat_sql/`, define a small `GenerationCancelled` exception (a
  plain `Exception` subclass is fine).
- Add an optional `cancel_event: threading.Event | None = None` parameter
  to `ChatService.process_text_to_sql`. It must default to `None` so every
  other caller (for example the non-streaming `/sql` endpoint and
  `app/tasks/chat_tasks.py`) behaves exactly as before.
- In `process_text_to_sql`, check `cancel_event.is_set()` at these points
  and raise `GenerationCancelled` if it is set: before each
  `generate_sql`, `refine_sql` and `review_sql` call, before executing
  SQL, before answer synthesis (`AnswerSynthesizer`), and **before
  persisting the assistant message**. An LLM call already in flight is
  allowed to finish. Do not try to kill threads.
- In `event_generator` in `app/api/chat_sql.py`:
  - Create a `threading.Event`, pass it into `process_text_to_sql`.
  - Wrap the `await loop.run_in_executor(...)` so that on
    `asyncio.CancelledError` the event is set before re-raising. Note that
    the existing `except Exception` does not catch `CancelledError`, so it
    needs its own clause. As far as we know, Starlette cancels the
    streaming generator when the client disconnects; **verify this with a
    test or a log line**, including behind the dev proxy, and do not assume
    it.
  - Catch `GenerationCancelled` and end the stream quietly (no `error`
    event, no stack trace in the logs; a single info-level log line is
    enough).
- Persistence rule: if cancellation happens before the assistant message
  is saved, save nothing for the assistant, but keep the user's question
  message if it was already stored. Document in the PR description the one
  known mismatch: if the user stops during the typing animation, the full
  answer was already saved, so a reload shows more text than they saw.
- Keep tenant and access checks (`verify_user_has_source_access`,
  `verify_user_has_domain_access`) exactly as they are.

---

## Task 5: Tests

**Frontend (vitest and testing-library, already installed):**
- While a request is pending, the Stop button is shown and Send is not.
- Clicking Stop calls `abort` on the controller, shows no error bubble,
  re-enables and focuses the textarea, and clears the pump (use fake
  timers and assert no further state updates).
- Pressing Esc while loading stops; pressing Esc when idle does nothing.
- A stop before any token removes the empty assistant placeholder.
- A stop after some tokens keeps the partial text and marks it `stopped`.
- A stop after `finalData` has arrived keeps the SQL and data fields.
- The `meta` event sets the conversation id.

**Backend (pytest):**
- With `cancel_event` set, `process_text_to_sql` raises
  `GenerationCancelled` at the next checkpoint and makes no further LLM
  or executor calls (use fakes or mocks for the LLM provider and executor).
- No assistant message is persisted for a cancelled run.
- Existing callers that do not pass `cancel_event` behave unchanged.
- The stream endpoint ends without an `error` event when cancelled.

---

## Definition of done

- All tasks complete, with the tests above passing (`pytest` in
  `services/schema-ingestion/`, plus `tsc --noEmit` and the project's
  linter in `apps/web/`).
- Manually verified in the browser: Stop during the thinking phase (before
  any text), Stop during the typing phase, Esc to stop, stopping the first
  question of a new conversation (no orphaned conversation), and a normal
  uncancelled question still works end to end.
- Backend logs confirm that after Stop no further LLM calls are made for
  that request.
- No change to the response shape of the non-streaming endpoints.
- The PR description lists: the persistence mismatch noted in Task 4,
  whether `pollMessageStatus` is still used, and any invariant from
  `CLAUDE.md` that the change touches.
- Out of scope for this task (mention as a follow-up only): streaming the
  real LLM tokens for the answer text instead of the simulated stream.
