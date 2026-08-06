import requests
import json
import os
from dotenv import load_dotenv

import sys
sys.path.insert(0, r"c:\Users\Admin\Downloads\Analytics Tool\Analytics Tool\analytics-platform\services\schema-ingestion")

from app.schemas_semantic_ai import AITableEnrichmentSchema

load_dotenv()
model_name = os.getenv("OLLAMA_MODEL", "gemma3:4b")
base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

print(f"Testing model: {model_name}")

payload = {
    "model": model_name,
    "prompt": "Test prompt",
    "stream": False,
    "format": AITableEnrichmentSchema.model_json_schema(),
    "options": {"temperature": 0.2}
}

try:
    res = requests.post(
        f"{base_url}/api/generate",
        json=payload
    )
    print(f"Status Code: {res.status_code}")
    if res.status_code != 200:
        print(f"Response Body: {res.text}")
    else:
        print("Success!")
except Exception as e:
    print(f"Error: {e}")
