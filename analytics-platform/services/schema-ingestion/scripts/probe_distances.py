"""Probe real Chroma distance values to calibrate the RAG threshold."""
from app.embeddings.chroma_store import ChromaStore
from app.embeddings.registry import get_embedding_provider

TENANT_ID = "00000000-0000-0000-0000-000000000001"

store = ChromaStore(ephemeral=False)
coll = store._get_or_create_collection(TENANT_ID)

print("=== COLLECTION METADATA ===")
print(f"Name    : {coll.name}")
print(f"Metadata: {coll.metadata}")
print(f"Count   : {coll.count()}")
print()

peek = coll.peek(limit=20)
print("=== STORED DOCUMENTS ===")
for i, (doc_id, doc, meta) in enumerate(zip(peek["ids"], peek["documents"], peek["metadatas"])):
    print(f"[{i:02d}] type={meta.get('object_type'):<12}  text={doc[:90]}")
print()

provider = get_embedding_provider()

queries = [
    ("total revenue",             "SHOULD match: obvious"),
    ("sum of all sales",          "SHOULD match: paraphrase"),
    ("monthly revenue",           "SHOULD match: time dimension"),
    ("sales by region",           "SHOULD match: dimension"),
    ("user login authentication", "SHOULD NOT match: irrelevant"),
    ("database schema table",     "SHOULD NOT match: technical noise"),
]

print("=== DISTANCE PROBES ===")
for q_text, label in queries:
    vec = provider.embed([q_text])[0]
    results = coll.query(
        query_embeddings=[vec],
        n_results=min(5, coll.count()),
        where={"tenant_id": TENANT_ID},
        include=["documents", "metadatas", "distances"],
    )
    print(f'Query: "{q_text}"  ({label})')
    for j in range(len(results["ids"][0])):
        doc_id = results["ids"][0][j]
        doc    = results["documents"][0][j]
        dist   = results["distances"][0][j]
        meta   = results["metadatas"][0][j]
        print(f"  dist={dist:.4f}  type={meta.get('object_type'):<12}  doc=\"{doc[:70]}\"")
    print()
