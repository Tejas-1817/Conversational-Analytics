"""
Generate PostgreSQL queries from natural-language questions using a local
Ollama instance and the exported database schema DDL.

Usage:
    from ollama import generate_sql

    sql = generate_sql("How many active customers do we have?")
    print(sql)

    # Or run as a script (prompts for the question at runtime):
    python ollama.py

Configuration (.env / environment variables):
    OLLAMA_BASE_URL  - Ollama server URL (default: http://localhost:11434)
    OLLAMA_MODEL     - Model name (default: gemma3:4b)
    SCHEMA_FILE      - Path to schema DDL file (default: database_schema.sql)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
SCHEMA_FILE = os.getenv("SCHEMA_FILE", "database_schema.sql")


def load_schema(schema_path: str | Path | None = None) -> str:
    """Load the database schema DDL from disk."""
    path = Path(schema_path or SCHEMA_FILE)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    if not path.exists():
        raise FileNotFoundError(
            f"Schema file not found: {path}. "
            "Run export_postgres_schema.py first to generate it."
        )
    return path.read_text(encoding="utf-8")


def build_prompt(question: str, schema_ddl: str) -> str:
    """Build the text-to-SQL prompt sent to Ollama."""
    return f"""You are an expert PostgreSQL query generator.

Your task is to convert a natural-language question into a single, valid,
read-only PostgreSQL SELECT query using ONLY the tables and columns defined
in the schema below.

## Rules
1. Output ONLY the SQL query — no explanations, no markdown fences, no comments.
2. Use PostgreSQL syntax only (e.g. ILIKE, LIMIT, DATE_TRUNC, jsonb operators).
3. Prefer JOINs over subqueries when relationships are clear from the schema.
4. Never invent tables or columns that are not in the schema.
5. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or any
   statement that modifies data or schema.
6. If the question cannot be answered from the schema, respond with exactly:
   -- UNSUPPORTED: <short reason>
7. Qualify column names with table aliases when joining multiple tables.
8. Use sensible LIMIT (e.g. 100) for open-ended list questions unless the
   user asks for a full count/aggregate.

## Database schema (PostgreSQL DDL)
{schema_ddl}

## User question
{question}

## SQL query
"""


def _extract_sql(raw: str) -> str:
    """Strip markdown fences / chatter and return the SQL text."""
    text = raw.strip()

    fenced = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # If the model still adds a lead-in, take from the first SQL keyword.
    match = re.search(
        r"(?is)\b(WITH|SELECT|EXPLAIN|--\s*UNSUPPORTED)\b[\s\S]*",
        text,
    )
    if match:
        return match.group(0).strip().rstrip("`").strip()

    return text


def generate_sql(
    question: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    schema_path: str | Path | None = None,
    temperature: float = 0.1,
    timeout: int = 120,
) -> str:
    """
    Ask the local Ollama model to generate a PostgreSQL query for `question`
    using the contents of the database schema file.

    Args:
        question: Natural-language question about the data.
        model: Ollama model name. Defaults to OLLAMA_MODEL / gemma3:4b.
        base_url: Ollama server URL. Defaults to OLLAMA_BASE_URL.
        schema_path: Path to the schema DDL file.
        temperature: Sampling temperature (lower = more deterministic).
        timeout: HTTP timeout in seconds.

    Returns:
        Generated SQL query string (or an -- UNSUPPORTED comment).
    """
    if not question or not question.strip():
        raise ValueError("question must be a non-empty string")

    model = model or OLLAMA_MODEL
    base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
    schema_ddl = load_schema(schema_path)
    prompt = build_prompt(question.strip(), schema_ddl)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            # Encourage concise SQL-only answers.
            "num_predict": 1024,
        },
    }

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed to reach Ollama at {base_url} using model '{model}': {exc}"
        ) from exc

    data = response.json()
    raw = data.get("response", "")
    if not raw:
        raise RuntimeError(f"Ollama returned an empty response: {json.dumps(data)}")

    return _extract_sql(raw)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a PostgreSQL query from a natural-language question via Ollama."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Natural-language question (optional; prompted at runtime if omitted)",
    )
    parser.add_argument("--model", default=None, help=f"Ollama model (default: {OLLAMA_MODEL})")
    parser.add_argument("--base-url", default=None, help=f"Ollama base URL (default: {OLLAMA_BASE_URL})")
    parser.add_argument("--schema", default=None, help=f"Schema DDL file (default: {SCHEMA_FILE})")
    args = parser.parse_args()

    question = (args.question or "").strip()
    if not question:
        try:
            question = input("Enter your question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            sys.exit(1)

    if not question:
        print("Error: question cannot be empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Using model '{args.model or OLLAMA_MODEL}' at {args.base_url or OLLAMA_BASE_URL} ...")
    print("Generating SQL...\n")

    try:
        sql = generate_sql(
            question,
            model=args.model,
            base_url=args.base_url,
            schema_path=args.schema,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(sql)


if __name__ == "__main__":
    main()
