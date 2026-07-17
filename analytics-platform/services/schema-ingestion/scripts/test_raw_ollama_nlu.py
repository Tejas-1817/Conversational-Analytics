import sys
import os
import requests
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.schemas_engine import NLUIntent

def run_test():
    print("Testing RAW Ollama NLU Intent")
    
    schema = NLUIntent.model_json_schema()
    system_prompt = (
        "You are an expert, deterministic system that exclusively outputs valid JSON. "
        "Never output conversational text, markdown formatting blocks like ```json, or explanations. "
        "Output exactly and only a valid JSON object matching this JSON schema:\n"
        f"{json.dumps(schema, indent=2)}"
    )
    
    query = "Show total revenue by region"
    prompt = f"""
You are an expert Data Analyst and Natural Language Understanding engine.
Your task is to parse a user's analytical question into a structured intent representation.

USER QUESTION: {query}
"""
    full_prompt = f"{system_prompt}\n\nUSER PROMPT:\n{prompt}"
    
    payload = {
        "model": "qwen2.5:14b",
        "prompt": full_prompt,
        "stream": False,
        "format": "json"
    }

    start = time.time()
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=120.0
        )
        print(f"Time taken: {time.time() - start:.2f} seconds")
        print("STATUS:", response.status_code)
        print("RAW RESPONSE:", repr(response.text))
        
        raw_text = response.json().get("response", "").strip()
        print("CLEAN RESPONSE:", repr(raw_text))
        
        # Test markdown strip
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            if len(lines) > 1 and lines[0].startswith("```"):
                lines = lines[1:]
            if len(lines) > 0 and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
            
        print("AFTER STRIP:", repr(raw_text))
        
        parsed = NLUIntent.model_validate_json(raw_text)
        print("SUCCESSFULLY PARSED:", parsed)
        
    except Exception as e:
        print(f"Time taken: {time.time() - start:.2f} seconds")
        print("ERROR:", type(e).__name__, e)

if __name__ == "__main__":
    run_test()
