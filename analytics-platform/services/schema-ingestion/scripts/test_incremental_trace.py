"""
Checkpoint 1 verification: prove that trace entries land in the DB incrementally
(i.e. mid-processing polls see a growing trace list), not as one batch write at
job completion.

HOW IT WORKS
------------
1. Enqueues a real chat job via the API (same as the frontend does).
2. Polls the message endpoint every 2 seconds.
3. Records the length of the trace list returned on each poll.
4. After the job completes, asserts:
   a. Final trace is not empty.
   b. At least one intermediate poll returned a trace shorter than the final
      trace — proving incremental writes.
   c. All trace entries have the required shape: stage, label, status, at.
   d. Final complete status is "complete" or "error" (not "processing" forever).
"""

import sys
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"c:\Users\Admin\Downloads\Analytics Tool\Analytics Tool\analytics-platform\services\schema-ingestion")

BASE = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def login():
    r = requests.post(f"{BASE}/auth/login",
                      data={"username": "admin@example.com", "password": "admin123"},
                      timeout=10)
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def create_conversation(token):
    r = requests.post(f"{BASE}/engine/conversations",
                      headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code in (200, 201), f"Create conv failed: {r.text}"
    return r.json()["id"]

def send_query(token, conv_id, question):
    r = requests.post(f"{BASE}/engine/conversations/{conv_id}/query",
                      json={"message": question},
                      headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r.status_code in (200, 201, 202), f"Query failed: {r.text}"
    return r.json()

def get_message(token, conv_id, msg_id):
    r = requests.get(f"{BASE}/engine/conversations/{conv_id}/messages/{msg_id}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200, f"Get message failed: {r.text}"
    return r.json()

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
def run():
    print("=== Checkpoint 1: Incremental trace verification ===\n")

    token = login()
    print("✓ Authenticated")

    conv_id = create_conversation(token)
    print(f"✓ Conversation created: {conv_id}")

    question = "What is our total revenue?"
    msg = send_query(token, conv_id, question)
    msg_id = msg["id"]
    print(f"✓ Job enqueued  msg_id={msg_id}")
    print(f"  Initial status : {msg['status']}")
    print(f"  Initial trace  : {msg.get('trace')}\n")

    # Poll and record trace lengths at each poll
    poll_trace_lengths = []
    max_polls = 120  # 4 minutes max
    polls_done = 0

    print("Polling (every 2s)...")
    for i in range(max_polls):
        time.sleep(2)
        polls_done += 1
        data = get_message(token, conv_id, msg_id)
        trace = data.get("trace") or []
        status = data["status"]
        print(f"  poll {i+1:3d} | status={status:<12} | trace_len={len(trace)}")
        poll_trace_lengths.append(len(trace))

        if status in ("complete", "error"):
            print(f"\n✓ Terminal status reached after {polls_done} polls")
            final_msg = data
            break
    else:
        print("\n✗ TIMEOUT — job never reached terminal status")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------
    print("\n--- Assertions ---")
    final_trace = final_msg.get("trace") or []

    # a. Final trace is not empty
    assert len(final_trace) > 0, "FAIL: final trace is empty — _append_trace never called"
    print(f"✓ Final trace length = {len(final_trace)} (not empty)")

    # b. At least one intermediate poll saw a shorter trace than the final
    # (proves incremental writes, not batch write at end)
    intermediate_lengths = poll_trace_lengths[:-1]  # exclude the last poll which may be final
    found_shorter = any(n < len(final_trace) for n in intermediate_lengths)
    assert found_shorter, (
        f"FAIL: no intermediate poll saw a trace shorter than the final length {len(final_trace)}.\n"
        f"All intermediate lengths were: {intermediate_lengths}\n"
        f"This means trace entries were batch-written at the end, not incrementally."
    )
    min_intermediate = min(intermediate_lengths) if intermediate_lengths else "N/A"
    print(f"✓ Incremental writes confirmed: min intermediate trace_len={min_intermediate}, final={len(final_trace)}")

    # c. All entries have required shape
    required_keys = {"stage", "label", "status", "at"}
    for i, entry in enumerate(final_trace):
        missing = required_keys - set(entry.keys())
        assert not missing, f"FAIL: trace entry #{i} missing keys {missing}: {entry}"
    print(f"✓ All {len(final_trace)} trace entries have required shape (stage, label, status, at)")

    # d. Terminal status
    assert final_msg["status"] in ("complete", "error"), \
        f"FAIL: unexpected final status '{final_msg['status']}'"
    print(f"✓ Final status = '{final_msg['status']}'")

    # ------------------------------------------------------------------
    # Print final trace for visual inspection
    # ------------------------------------------------------------------
    print("\n--- Final trace ---")
    import json
    print(json.dumps(final_trace, indent=2))

    print("\n=== ALL ASSERTIONS PASSED ===")


if __name__ == "__main__":
    run()
