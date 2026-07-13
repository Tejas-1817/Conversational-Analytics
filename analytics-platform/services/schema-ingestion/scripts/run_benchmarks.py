import os
import sys
import uuid
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY")

if not API_KEY:
    print("API_KEY environment variable required")
    sys.exit(1)

def run_benchmark(collection_id: str, threshold: float = 0.8):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    print(f"Triggering benchmark for collection {collection_id}...")
    # This might take a while, but for now our API triggers it synchronously.
    resp = requests.post(f"{API_URL}/eval/runs/{collection_id}", headers=headers)
    
    if resp.status_code != 200:
        print(f"Failed to trigger benchmark: {resp.status_code} - {resp.text}")
        sys.exit(1)
        
    run_data = resp.json()
    run_id = run_data["id"]
    
    print(f"Benchmark Run {run_id} completed.")
    
    # In a real async setup we would poll, but our current impl is sync so it's already done
    overall_score = float(run_data.get("overall_score") or 0.0)
    pass_rate = float(run_data.get("pass_rate") or 0.0)
    
    print(f"Overall Score: {overall_score * 100:.1f}%")
    print(f"Pass Rate: {pass_rate * 100:.1f}%")
    
    if overall_score < threshold:
        print(f"FAILURE: Overall score {overall_score} is below threshold {threshold}")
        sys.exit(1)
        
    print("Benchmark passed!")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_benchmarks.py <collection_id> [threshold]")
        sys.exit(1)
        
    c_id = sys.argv[1]
    thresh = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
    run_benchmark(c_id, thresh)
