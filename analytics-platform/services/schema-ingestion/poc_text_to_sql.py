import json
import re
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set
from pydantic import BaseModel, Field

import os


# =====================================================================
# 1. CONFIG & OLLAMA SETTINGS
# =====================================================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b").strip()


# =====================================================================
# 2. HARDCODED SCHEMA DEFINITION (DDL & Metadata)
# =====================================================================
SAMPLE_SCHEMA_DDL = """
CREATE TABLE users (
    user_id INT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    email VARCHAR(255) NOT NULL,
    status VARCHAR(50) CHECK (status IN ('active', 'suspended', 'deleted')),
    country VARCHAR(2) NOT NULL
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    order_date TIMESTAMP NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) CHECK (status IN ('completed', 'pending', 'cancelled', 'refunded'))
);

CREATE TABLE order_items (
    item_id INT PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_name VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL
);

CREATE TABLE payments (
    payment_id INT PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    payment_date TIMESTAMP NOT NULL,
    payment_method VARCHAR(50) CHECK (payment_method IN ('credit_card', 'paypal', 'stripe', 'bank_transfer')),
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) CHECK (status IN ('success', 'failed', 'pending'))
);
"""

SCHEMA_METADATA = {
    "tables": {
        "users": ["user_id", "created_at", "email", "status", "country"],
        "orders": ["order_id", "user_id", "order_date", "total_amount", "status"],
        "order_items": ["item_id", "order_id", "product_name", "quantity", "unit_price"],
        "payments": ["payment_id", "order_id", "payment_date", "payment_method", "amount", "status"]
    }
}


# =====================================================================
# 3. STRUCTURED OUTPUT RESPONSE MODEL
# =====================================================================
class TextToSQLResponse(BaseModel):
    reasoning: str = Field(description="Step-by-step logic on how tables and joins were chosen.")
    is_answerable: bool = Field(description="False if the question asks for data outside the schema.")
    tables_referenced: List[str] = Field(default_factory=list, description="List of tables used.")
    sql_query: Optional[str] = Field(default=None, description="Clean SQL query without markdown blocks.")
    unanswerable_reason: Optional[str] = Field(default=None, description="Explanation if unanswerable.")
    start_time: Optional[str] = Field(default=None, description="Query execution start timestamp.")
    end_time: Optional[str] = Field(default=None, description="Query execution end timestamp.")
    execution_duration: Optional[str] = Field(default=None, description="Formatted execution duration.")


# =====================================================================
# 4. TEXT-TO-SQL ENGINE FOR OLLAMA
# =====================================================================
def save_query_metrics(start_dt: datetime, end_dt: datetime, question: str):
    """Persist query execution timestamps to file so REST API reflects real CLI runs."""
    try:
        metrics_file = Path(__file__).resolve().parent / "poc_text_to_sql_metrics.json"
        duration_ms = round((end_dt - start_dt).total_seconds() * 1000, 2)
        data = {
            "last_start_time": start_dt.isoformat(),
            "last_end_time": end_dt.isoformat(),
            "execution_time_ms": duration_ms,
            "last_question": question
        }
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_active_schema() -> tuple[str, dict]:
    """Get active dynamic schema DDL and metadata, falling back to static schema if DB is offline."""
    try:
        from app.services.dynamic_schema_service import schema_service
        sdata = schema_service.get_schema()
        ddl = sdata.get("ddl")
        metadata = sdata.get("schema_metadata", {})
        if ddl and metadata.get("tables"):
            return ddl, metadata
    except Exception:
        pass
    return SAMPLE_SCHEMA_DDL, SCHEMA_METADATA


class OllamaTextToSQLEngine:
    def __init__(self, base_url: str, model_name: str, ddl: Optional[str] = None, metadata: Optional[dict] = None):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self._custom_ddl = ddl
        self._custom_metadata = metadata

    def _get_schema_context(self) -> tuple[str, dict]:
        if self._custom_ddl and self._custom_metadata:
            return self._custom_ddl, self._custom_metadata
        return get_active_schema()

    def _build_prompt(self, question: str) -> str:
        active_ddl, _ = self._get_schema_context()
        json_schema = json.dumps(TextToSQLResponse.model_json_schema(), indent=2)
        return f"""You are a strict, expert Text-to-SQL engine targeting PostgreSQL.
Translate the user question into a valid SQL query using ONLY the provided DDL schema.

### DATABASE SCHEMA (DDL):
{active_ddl}

### CRITICAL RULES:
1. NO HALLUCINATIONS: Do NOT reference any table or column not present in the DDL above.
2. UNANSWERABLE: If the question requires data outside this DDL, set `is_answerable` to false.
3. READ-ONLY: Only generate SELECT queries.
4. Output MUST be raw JSON matching this JSON Schema:
{json_schema}

User Question: {question}
JSON Output:"""

    def validate_schema(self, response: TextToSQLResponse) -> tuple[bool, str]:
        if not response.is_answerable or not response.sql_query:
            return True, "Marked unanswerable."

        _, active_metadata = self._get_schema_context()
        valid_tables: Set[str] = set(active_metadata.get("tables", {}).keys())
        for table in response.tables_referenced:
            if table.lower() not in valid_tables:
                return False, f"Hallucination Detected: Table '{table}' does not exist in schema."

        sql_lower = response.sql_query.lower()
        if any(kw in sql_lower for kw in ["insert ", "update ", "delete ", "drop "]):
            return False, "Security Violation: Non-SELECT query detected."

        return True, "Valid"

    def generate_sql(self, question: str) -> TextToSQLResponse:
        start_dt = datetime.now()
        start_utc = datetime.now(timezone.utc)
        prompt = self._build_prompt(question)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0}
        }

        res = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=600.0)
        res.raise_for_status()

        end_dt = datetime.now()
        end_utc = datetime.now(timezone.utc)
        duration_sec = (end_dt - start_dt).total_seconds()
        
        save_query_metrics(start_utc, end_utc, question)

        raw_text = res.json().get("response", "").strip()

        # Clean markdown code fences if present
        if "```" in raw_text:
            lines = raw_text.splitlines()
            # Filter out lines starting with ```
            lines = [line for line in lines if not line.strip().startswith("```")]
            raw_text = "\n".join(lines).strip()

        parsed_json = json.loads(raw_text)
        result = TextToSQLResponse(**parsed_json)

        # Attach execution timing
        result.start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        result.end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        result.execution_duration = f"{duration_sec:.2f}s ({duration_sec * 1000:.0f}ms)"

        # Apply schema guardrail
        valid, msg = self.validate_schema(result)
        if not valid:
            result.is_answerable = False
            result.sql_query = None
            result.unanswerable_reason = f"Guardrail Failure: {msg}"

        return result


# =====================================================================
# 5. RUN POC TEST
# =====================================================================
if __name__ == "__main__":
    engine = OllamaTextToSQLEngine(OLLAMA_BASE_URL, OLLAMA_MODEL)
    print("=" * 70)
    print(f"  Interactive Text-to-SQL PoC (Model: {OLLAMA_MODEL})")
    print("  Type your question below (or type 'exit' or 'quit' to stop).")
    print("=" * 70)
    print()

    while True:
        try:
            user_question = input("Ask a Question > ").strip()
            if not user_question:
                continue
            if user_question.lower() in ["exit", "quit", "q"]:
                print("Exiting Text-to-SQL PoC. Goodbye!")
                break

            print("\nGenerating SQL query, please wait...")
            res = engine.generate_sql(user_question)
            print("\n" + "-" * 70)
            print(f"Query Start   : {res.start_time}")
            print(f"Query End     : {res.end_time}")
            print(f"Execution Time: {res.execution_duration}")
            print(f"Reasoning     : {res.reasoning}")
            print(f"Is Answerable : {res.is_answerable}")
            if res.is_answerable:
                print(f"Tables Used   : {res.tables_referenced}")
                print(f"SQL Query     :\n{res.sql_query}")
            else:
                print(f"Refusal Reason: {res.unanswerable_reason}")
            print("-" * 70 + "\n")
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\n[ERROR]: {e}\n")
