import requests
import json

system_prompt = "You are an expert, deterministic system that exclusively outputs valid JSON. Output exactly and only a valid JSON object matching this schema: {\"type\": \"object\", \"properties\": {\"route\": {\"type\": \"string\"}, \"confidence\": {\"type\": \"number\"}, \"reason\": {\"type\": \"string\"}}}"

full_prompt = f"{system_prompt}\n\nUSER PROMPT:\nquery: hello"

payload = {
    "model": "qwen2.5:14b",
    "prompt": full_prompt,
    "stream": False,
    "format": "json"
}

try:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json=payload,
        timeout=120.0
    )
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
except Exception as e:
    print("ERROR:", e)
