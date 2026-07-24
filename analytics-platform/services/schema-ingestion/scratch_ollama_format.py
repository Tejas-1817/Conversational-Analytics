import requests
import json
from pydantic import BaseModel

class TestSchema(BaseModel):
    hello: str

base_url = "http://localhost:11434"
model_name = "qwen2.5:7b"

# Test 1: format = "json"
try:
    res = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model_name,
            "prompt": "Say hello in JSON",
            "stream": False,
            "format": "json"
        }
    )
    print("Test 1 (format='json'):", res.status_code)
except Exception as e:
    print("Test 1 error:", e)

# Test 2: format = JSON Schema dict
try:
    res = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model_name,
            "prompt": "Say hello in JSON",
            "stream": False,
            "format": TestSchema.model_json_schema()
        }
    )
    print("Test 2 (format=dict):", res.status_code)
    if res.status_code == 400:
        print(res.text)
except Exception as e:
    print("Test 2 error:", e)
