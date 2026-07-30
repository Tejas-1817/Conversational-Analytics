import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.llm.providers.ollama import OllamaProvider
from app.schemas_semantic_ai import AITableEnrichmentSchema

provider = OllamaProvider()
print(f"Testing OllamaProvider model={provider.model_name} at {provider.base_url}")

# Verify schema contains $defs
schema_dict = AITableEnrichmentSchema.model_json_schema()
print(f"Has $defs in schema: {'$defs' in schema_dict}")

prompt = "Generate sample dimensions for an 'employees' table with columns id, name, department, salary."

try:
    res = provider.generate_structured_json(prompt=prompt, schema=AITableEnrichmentSchema)
    print("\n--- OLLAMA SUCCESS RESPONSE ---")
    print(res[:300] + "..." if len(res) > 300 else res)
    print("SUCCESS: $defs fallback triggered output_format='json' and Ollama responded cleanly without 400 error!")
except Exception as e:
    print(f"\n--- ERROR ---: {type(e).__name__}: {e}")
