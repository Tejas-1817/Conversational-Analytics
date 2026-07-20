import sys
import time
import requests
import json
import uuid

API_BASE = "http://localhost:8000"

def get_admin_token():
    res = requests.post(f"{API_BASE}/auth/login", data={
        "username": "admin@example.com",
        "password": "ChangeMe!SecurePassword123",
        "grant_type": "password"
    })
    if res.status_code != 200:
        print("Login failed:", res.text)
    res.raise_for_status()
    return res.json()["access_token"]

def main():
    print("Authenticating...")
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("Creating conversation...")
    res = requests.post(f"{API_BASE}/engine/conversations", headers=headers)
    res.raise_for_status()
    conv_id = res.json()["id"]
    print(f"Conversation ID: {conv_id}")

    print("Sending query...")
    start_time = time.time()
    res = requests.post(f"{API_BASE}/engine/conversations/{conv_id}/query", headers=headers, json={"message": "What is our total revenue?"})
    req_latency = time.time() - start_time
    
    assert req_latency < 5.0, f"Expected fast response, got {req_latency:.2f}s"
    print(f"Immediate POST /query took {req_latency:.2f}s")
    
    res.raise_for_status()
    msg = res.json()
    msg_id = msg["id"]
    status = msg.get("status")
    print(f"Message ID: {msg_id}")
    print(f"Initial Status: {status}")
    
    assert status == "processing", f"Expected 'processing', got '{status}'"

    print("\nPolling for completion...")
    attempts = 0
    while attempts < 100: # 10 minutes max
        time.sleep(3)
        attempts += 1
        res = requests.get(f"{API_BASE}/engine/conversations/{conv_id}/messages/{msg_id}", headers=headers)
        res.raise_for_status()
        msg_poll = res.json()
        current_status = msg_poll.get("status")
        
        print(f"Attempt {attempts}: Status = {current_status}")
        if current_status == "complete":
            print("\n[OK] Processing Complete!")
            print("Generated SQL:", msg_poll.get("generated_sql"))
            print("Explanation:", msg_poll.get("content"))
            return
        elif current_status == "error":
            print("\n[FAIL] Processing failed!")
            print("Error:", msg_poll.get("error"))
            sys.exit(1)
            
    print("Timed out waiting for processing")
    sys.exit(1)

if __name__ == "__main__":
    main()
