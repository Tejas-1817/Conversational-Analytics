"""
sql_schema_to_text.py

Converts a .sql schema file (CREATE TABLE statements) into a plain-text,
human-readable description using a local Ollama LLM.

Usage:
    python sql_schema_to_text.py schema.sql
    python sql_schema_to_text.py schema.sql -o schema.txt
    python sql_schema_to_text.py schema.sql --model gemma3:4b --url http://localhost:11434/api/generate
    python sql_schema_to_text.py schema.sql --whole   # send the whole file in one prompt instead of per-table

By default, the script splits the .sql file into one CREATE TABLE
statement per chunk and asks the LLM to describe each table
separately — this keeps prompts small and avoids truncation on large
schemas. Use --whole for short schemas where a single prompt is fine.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_TIMEOUT = 300

TABLE_PROMPT_TEMPLATE = """You are a database documentation assistant.
Convert the following SQL CREATE TABLE statement into a clear, plain-English
description. Describe the table's purpose (infer it from the name/columns if
not obvious), list each column with its type and any constraints (primary
key, foreign key, not null, default), in plain sentences — not SQL syntax.
Keep it concise. Do not include markdown code fences in your response.

SQL:
{sql}

Plain-text description:
"""

WHOLE_FILE_PROMPT_TEMPLATE = """You are a database documentation assistant.
Convert the following full SQL schema into a clear, plain-English
description of the database: describe each table's purpose, its columns
with types and constraints, and any relationships between tables (foreign
keys). Organize the output table by table. Do not include markdown code
fences in your response.

SQL SCHEMA:
{sql}

Plain-text description:
"""


def split_into_table_statements(sql_text: str) -> list[str]:
    """Splits a .sql file into one chunk per CREATE TABLE statement.

    Falls back to returning the whole file as a single chunk if no
    CREATE TABLE statements are found (e.g. the file only has ALTER/
    COMMENT statements, or uses a dialect this regex doesn't match).
    """
    # Find each "CREATE TABLE ... ;" block, including any preceding
    # comment lines directly above it (common in schema dumps).
    pattern = re.compile(
        r"(?:^--[^\n]*\n)*^\s*CREATE\s+TABLE\b.*?;",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    matches = [m.group(0).strip() for m in pattern.finditer(sql_text)]

    if matches:
        return matches

    stripped = sql_text.strip()
    return [stripped] if stripped else []


def call_ollama(prompt: str, model: str, url: str, timeout: int = 120) -> str:
    try:
        response = requests.post(
            url,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.RequestException as e:
        raise RuntimeError(
            f"Failed to reach Ollama at {url}. Is `ollama serve` running and "
            f"has `ollama pull {model}` been run? Original error: {e}"
        ) from e


def convert_schema_to_text(
    sql_text: str,
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
    whole_file: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    if whole_file:
        prompt = WHOLE_FILE_PROMPT_TEMPLATE.format(sql=sql_text)
        return call_ollama(prompt, model, url, timeout=timeout)

    chunks = split_into_table_statements(sql_text)
    if not chunks:
        return ""

    descriptions = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"  Converting table {i}/{len(chunks)}...", file=sys.stderr)
        prompt = TABLE_PROMPT_TEMPLATE.format(sql=chunk)
        description = call_ollama(prompt, model, url, timeout=timeout)
        descriptions.append(description)

    return "\n\n".join(descriptions)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a .sql schema file to plain text using Ollama")
    parser.add_argument("input", type=str, help="Path to the input .sql file")
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Path to write the output .txt file (default: same name as input, .txt extension)",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Ollama model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--url", type=str, default=DEFAULT_OLLAMA_URL, help=f"Ollama API URL (default: {DEFAULT_OLLAMA_URL})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Ollama request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument(
        "--whole", action="store_true",
        help="Send the entire file as one prompt instead of splitting per-table",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".txt")

    sql_text = input_path.read_text(encoding="utf-8")
    if not sql_text.strip():
        print("Error: input file is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading schema from {input_path}...", file=sys.stderr)
    try:
        plain_text = convert_schema_to_text(
            sql_text,
            model=args.model,
            url=args.url,
            whole_file=args.whole,
            timeout=args.timeout,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not plain_text.strip():
        print("Error: no CREATE TABLE statements found and the file could not be converted.", file=sys.stderr)
        sys.exit(1)

    output_path.write_text(plain_text, encoding="utf-8")
    print(f"Done. Plain-text schema written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()