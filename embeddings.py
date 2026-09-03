"""
text_to_embeddings.py

Generates vector embeddings from a plain-text schema file (e.g. the
output of sql_schema_to_text.py) using sentence-transformers, which
runs locally — no API key or network calls at embedding time.

The input .txt is split into chunks on blank lines (each table's
description becomes one chunk, matching how sql_schema_to_text.py
separates tables with "\n\n"). Each chunk is embedded and the result
is written to a JSON file: a list of {id, text, embedding} records,
ready to be loaded into a vector database in the next step.

Usage:
    python text_to_embeddings.py schema.txt
    python text_to_embeddings.py schema.txt -o embeddings.json
    python text_to_embeddings.py schema.txt --model gemma3:4b
    python text_to_embeddings.py schema.txt --whole   # embed the whole file as one chunk
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None

DEFAULT_MODEL = "all-MiniLM-L6-v2"


def split_into_chunks(text: str) -> list[str]:
    """Splits on one-or-more blank lines. Falls back to the whole text
    as a single chunk if there's no blank-line separation at all."""
    raw_chunks = re.split(r"\n\s*\n", text.strip())
    chunks = [c.strip() for c in raw_chunks if c.strip()]
    return chunks if chunks else ([text.strip()] if text.strip() else [])


def load_model(model_name: str) -> "SentenceTransformer":
    if SentenceTransformer is None:
        raise ImportError(
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
        )
    print(f"Loading embedding model '{model_name}'...", file=sys.stderr)
    return SentenceTransformer(model_name)


def generate_embeddings(chunks: list[str], model) -> list[list[float]]:
    if not chunks:
        return []
    vectors = model.encode(chunks, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def build_records(chunks: list[str], vectors: list[list[float]]) -> list[dict]:
    records = []
    for i, (text, vector) in enumerate(zip(chunks, vectors)):
        # Use the first line as a rough label (e.g. "Table: users — ...")
        label = text.splitlines()[0][:80]
        records.append({
            "id": f"chunk_{i}",
            "label": label,
            "text": text,
            "embedding": vector,
        })
    return records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate vector embeddings from a plain-text schema file")
    parser.add_argument("input", type=str, help="Path to the input .txt file")
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Path to write the output .json file (default: same name as input, .json extension)",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"sentence-transformers model (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--whole", action="store_true",
        help="Embed the entire file as a single chunk instead of splitting on blank lines",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".json")

    text = input_path.read_text(encoding="utf-8")
    if not text.strip():
        print("Error: input file is empty.", file=sys.stderr)
        sys.exit(1)

    chunks = [text.strip()] if args.whole else split_into_chunks(text)
    if not chunks:
        print("Error: no content found to embed.", file=sys.stderr)
        sys.exit(1)

    print(f"Read {len(chunks)} chunk(s) from {input_path}", file=sys.stderr)

    try:
        model = load_model(args.model)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    vectors = generate_embeddings(chunks, model)
    records = build_records(chunks, vectors)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {"model": args.model, "dimension": len(vectors[0]) if vectors else 0, "records": records},
            f,
            indent=2,
        )

    print(f"Done. {len(records)} embedding(s) (dim={len(vectors[0]) if vectors else 0}) written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()