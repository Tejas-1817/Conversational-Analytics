import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

print(f"Testing model: {model_name}")

payload = {
    "model": model_name,
    "prompt": "Say hello in JSON",
    "stream": False,
    "format": "json",
    "options": {"temperature": 0.0}
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
