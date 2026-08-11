"""
store_embeddings.py

Loads the embeddings.json produced by text_to_embeddings.py and stores
it in a persistent ChromaDB collection, ready to be queried by a
retrieval/RAG step.

Usage:
    python store_embeddings.py embeddings.json
    python store_embeddings.py embeddings.json --persist-dir ./chroma_data --collection schema_embeddings
    python store_embeddings.py embeddings.json --reset     # wipe the collection before loading
    python store_embeddings.py --query "who placed orders" --top-k 3   # query an existing collection
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings

DEFAULT_PERSIST_DIR = "./chroma_data"
DEFAULT_COLLECTION_NAME = "schema_embeddings"


def get_collection(persist_dir: str, collection_name: str):
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def load_records(input_path: Path) -> tuple[str, list[dict]]:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "records" not in data:
        raise ValueError(
            f"'{input_path}' doesn't look like an embeddings.json file from "
            "text_to_embeddings.py (missing 'records' key)."
        )
    return data.get("model", "unknown"), data["records"]


def upsert_records(collection, records: list[dict]) -> int:
    if not records:
        return 0

    ids = [r["id"] for r in records]
    embeddings = [r["embedding"] for r in records]
    documents = [r["text"] for r in records]
    # Chroma rejects empty metadata dicts, so always include at least the label.
    metadatas = [{"label": r.get("label", "")} for r in records]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    return len(ids)


def run_query(collection, query_embedding: list[float], top_k: int) -> list[dict]:
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
    )

    hits = []
    for i, doc_id in enumerate(results["ids"][0]):
        hits.append({
            "id": doc_id,
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return hits


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Store schema embeddings into ChromaDB")
    parser.add_argument("input", type=str, nargs="?", default=None, help="Path to embeddings.json (from text_to_embeddings.py)")
    parser.add_argument("--persist-dir", type=str, default=DEFAULT_PERSIST_DIR, help=f"ChromaDB storage directory (default: {DEFAULT_PERSIST_DIR})")
    parser.add_argument("--collection", type=str, default=DEFAULT_COLLECTION_NAME, help=f"Collection name (default: {DEFAULT_COLLECTION_NAME})")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the collection before loading")
    parser.add_argument("--query", type=str, default=None, help="Instead of loading, run a similarity query against an existing collection")
    parser.add_argument("--query-model", type=str, default=None, help="sentence-transformers model to embed --query with (defaults to the model recorded in embeddings.json, or all-MiniLM-L6-v2)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return for --query (default: 5)")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    client, collection = get_collection(args.persist_dir, args.collection)

    # --- Query mode ---
    if args.query:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("Error: sentence-transformers is not installed. Run: pip install sentence-transformers", file=sys.stderr)
            sys.exit(1)

        model_name = args.query_model or "all-MiniLM-L6-v2"
        print(f"Embedding query with '{model_name}'...", file=sys.stderr)
        model = SentenceTransformer(model_name)
        query_vector = model.encode([args.query], normalize_embeddings=True).tolist()[0]

        hits = run_query(collection, query_vector, args.top_k)
        if not hits:
            print("No results (collection is empty).", file=sys.stderr)
            return

        for h in hits:
            print(f"[{h['distance']:.4f}] {h['id']} — {h['metadata'].get('label', '')}")
            print(f"  {h['text'][:200]}{'...' if len(h['text']) > 200 else ''}")
        return

    # --- Load mode ---
    if not args.input:
        print("Error: an input embeddings.json is required unless --query is used.", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.reset:
        print(f"Resetting collection '{args.collection}'...", file=sys.stderr)
        try:
            client.delete_collection(args.collection)
        except Exception:
            pass  # didn't exist yet — fine
        client, collection = get_collection(args.persist_dir, args.collection)

    model_name, records = load_records(input_path)
    print(f"Loaded {len(records)} record(s) (embedded with '{model_name}') from {input_path}", file=sys.stderr)

    n = upsert_records(collection, records)

    print(f"Done. {n} record(s) upserted. Collection '{args.collection}' now has {collection.count()} total vector(s) at {args.persist_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()