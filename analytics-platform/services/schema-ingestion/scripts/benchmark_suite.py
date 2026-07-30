import argparse
import csv
import json
import os
import sys
import time
import uuid
import psutil
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import event, create_engine
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import get_engine, session_scope
from app.models import Base, Tenant, DataSource, TableMeta, ColumnMeta, SemanticModel, MetadataVersion
from app.ingestion.introspector import run_introspection
from app.semantic.generation_service import SemanticGenerationService
from app.embeddings.job import embed_approved_objects
from app.engine.query_intelligence_service import QueryIntelligenceService
from app.schemas_semantic_ai import AITableEnrichmentSchema, AITableDimensionsSchema, AITableMeasuresSchema, AITableMetadataSchema
from app.embeddings.chroma_store import ChromaStore

# --- Telemetry ---

_query_count = 0
_db_engine = get_engine()

@event.listens_for(_db_engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    global _query_count
    _query_count += 1

class TelemetryContext:
    def __init__(self, name: str, results: list):
        self.name = name
        self.results = results
        self.start_time = 0
        self.start_query_count = 0
        
    def __enter__(self):
        global _query_count
        self.start_query_count = _query_count
        tracemalloc.start()
        psutil.cpu_percent(interval=None) # Prime CPU
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _query_count
        latency_ms = (time.perf_counter() - self.start_time) * 1000
        cpu_pct = psutil.cpu_percent(interval=None)
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        queries = _query_count - self.start_query_count
        peak_mem_mb = peak_mem / (1024 * 1024)
        
        print(f"[{self.name}] Latency: {latency_ms:.2f}ms | CPU: {cpu_pct:.1f}% | Mem: {peak_mem_mb:.2f}MB | Queries: {queries}")
        
        self.results.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_name": self.name,
            "latency_ms": round(latency_ms, 2),
            "cpu_percent": round(cpu_pct, 1),
            "peak_memory_mb": round(peak_mem_mb, 2),
            "sql_queries": queries,
            "error": str(exc_val) if exc_val else ""
        })

# --- Mocks for Testing ---

def _mock_llm_generate_structured(*args, **kwargs):
    schema = kwargs.get("schema")
    if schema == AITableEnrichmentSchema:
        return AITableEnrichmentSchema(
            business_description="Mock description",
            dimensions=[],
            measures=[],
            kpis=[],
            glossary_terms=[],
            confidence_score=0.9
        )
    elif schema == AITableDimensionsSchema:
        return AITableDimensionsSchema(business_description="Mock description", dimensions=[])
    elif schema == AITableMeasuresSchema:
        return AITableMeasuresSchema(measures=[], kpis=[])
    elif schema == AITableMetadataSchema:
        return AITableMetadataSchema(glossary_terms=[], relationships=[], confidence_score=0.9)
    return None

def _mock_llm_generate(*args, **kwargs):
    return '{"sql": "SELECT 1;", "explanation": "Mocked SQL", "confidence": 0.9, "referenced_objects": []}'


# --- Benchmarks ---

def setup_test_data(db: Session):
    existing_tenant = db.query(Tenant).filter_by(slug="benchmark-tenant").first()
    if existing_tenant:
        db.delete(existing_tenant)
        db.commit()

    tenant = Tenant(name="Benchmark Tenant", slug="benchmark-tenant")
    db.add(tenant)
    db.flush()
    
    source = DataSource(
        tenant_id=tenant.id,
        name="Benchmark DB",
        type="postgres",
        host="localhost",
        port=5432,
        database_name="bench_db",
        username="bench",
        credentials_encrypted=b"mock",
        created_by="system",
        updated_by="system",
        options={}
    )
    db.add(source)
    db.flush()
    
    meta = MetadataVersion(source_id=source.id, version_number=1, sync_status="succeeded")
    db.add(meta)
    db.flush()
    
    model = SemanticModel(
        tenant_id=tenant.id, 
        source_id=source.id, 
        metadata_version_id=meta.id, 
        semantic_version=1, 
        generated_by_model="benchmark-mock",
        generation_status="ACTIVE"
    )
    db.add(model)
    db.flush()
    
    tables = []
    for i in range(10): # 10 tables
        t = TableMeta(source_id=source.id, schema_name="public", table_name=f"test_table_{i}", status="approved", is_active=True)
        db.add(t)
        db.flush()
        tables.append(t)
        for j in range(20): # 20 columns each
            c = ColumnMeta(table_id=t.id, column_name=f"col_{j}", data_type="varchar", status="approved", is_active=True)
            db.add(c)
    
    db.commit()
    return tenant.id, source, model.id, tables


def run_benchmarks(output_csv: str):
    results = []
    
    print("Setting up test data...")
    with session_scope() as db:
        tenant_id, source, model_id, tables = setup_test_data(db)
        db.commit() # Release lock on test data
        
        # 1. Ingestion Pipeline
        print("Starting 1. Ingestion Pipeline...")
        try:
            with TelemetryContext("ingestion_pipeline", results):
                # Pass our own metadata engine to introspection just for speed testing
                run_introspection(db, source, _db_engine)
            db.commit() # Release lock from introspection before threads run
        except Exception as e:
            print(f"Skipping native introspection benchmark: {e}")
            db.rollback()

        print("Starting 2. Concurrent Ingestion (Simulate 5 workers)...")
        with TelemetryContext("concurrent_ingestion_5_workers", results):
            def _dummy_worker():
                try:
                    with session_scope() as db_worker:
                        run_introspection(db_worker, source, _db_engine)
                except Exception: 
                    pass

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(_dummy_worker) for _ in range(5)]
                for f in futures:
                    f.result()

        # 3. Semantic Generation (Mocked LLM)
        print("Starting 3. Semantic Generation Pipeline...")
        with patch("app.llm.orchestrator.ai_orchestrator.generate_structured", side_effect=_mock_llm_generate_structured):
            with TelemetryContext("semantic_generation_pipeline", results):
                with session_scope() as s2:
                    SemanticGenerationService.generate_for_tables(s2, tables, tenant_id, model_id, max_workers=3)
        
        # 4. Embeddings
        print("Starting 4. Embeddings Generation...")
        with TelemetryContext("embedding_generation", results):
            with session_scope() as s3:
                embed_approved_objects(tenant_id, s3, store=ChromaStore(ephemeral=True))
                
        # 5. Query Intelligence
        print("Starting 5. Query Intelligence Pipeline...")
        qis = QueryIntelligenceService()
        with TelemetryContext("query_intelligence_pipeline", results):
            with TelemetryContext("query_intelligence_latency", results):
                try:
                    QueryIntelligenceService.answer_question(
                        db, tenant_id, model_id, 
                        question="Show me revenue by product", 
                        user_email="bench@test.com"
                    )
                except Exception as e:
                    pass # it might fail because no dimensions were actually created by mock
                    
        # Cleanup
        t = db.query(Tenant).get(tenant_id)
        if t:
            db.delete(t)
        db.commit()
    
    # Write to CSV
    file_exists = os.path.isfile(output_csv)
    with open(output_csv, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", "test_name", "latency_ms", "cpu_percent", "peak_memory_mb", "sql_queries", "error"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)
    
    print(f"\nResults saved to {output_csv}")
    return results


def compare_reports(current_csv: str, previous_csv: str):
    def load_data(file):
        data = {}
        with open(file, 'r') as f:
            for row in csv.DictReader(f):
                data[row["test_name"]] = row
        return data

    if not os.path.exists(previous_csv):
        print(f"Previous CSV {previous_csv} not found for comparison.")
        return

    curr = load_data(current_csv)
    prev = load_data(previous_csv)
    
    print("\n--- Performance Regression Report ---")
    for test_name, c_row in curr.items():
        if test_name not in prev:
            continue
        p_row = prev[test_name]
        
        c_lat = float(c_row["latency_ms"])
        p_lat = float(p_row["latency_ms"])
        lat_diff = ((c_lat - p_lat) / p_lat * 100) if p_lat else 0
        
        c_mem = float(c_row["peak_memory_mb"])
        p_mem = float(p_row["peak_memory_mb"])
        mem_diff = ((c_mem - p_mem) / p_mem * 100) if p_mem else 0
        
        icon = "🚨" if lat_diff > 10 else ("✅" if lat_diff < -10 else "➖")
        print(f"[{test_name}] {icon}")
        print(f"  Latency: {p_lat}ms -> {c_lat}ms ({lat_diff:+.1f}%)")
        print(f"  Memory:  {p_mem}MB -> {c_mem}MB ({mem_diff:+.1f}%)")


def generate_html_report(csv_path: str, html_path: str):
    if not os.path.exists(csv_path):
        return
        
    data = []
    with open(csv_path, 'r') as f:
        data = list(csv.DictReader(f))
        
    # Group by test_name
    grouped = {}
    for row in data:
        t = row["test_name"]
        if t not in grouped:
            grouped[t] = {"labels": [], "latency": [], "memory": [], "cpu": []}
        # Simplify timestamp for label
        dt = row["timestamp"][:16].replace("T", " ")
        grouped[t]["labels"].append(dt)
        grouped[t]["latency"].append(row["latency_ms"])
        grouped[t]["memory"].append(row["peak_memory_mb"])
        grouped[t]["cpu"].append(row["cpu_percent"])

    html = """<!DOCTYPE html>
<html>
<head>
    <title>Performance Benchmark Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f8f9fa; }
        .chart-container { width: 800px; height: 400px; background: white; padding: 20px; margin-bottom: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        h2 { color: #555; border-bottom: 1px solid #ddd; padding-bottom: 10px; }
    </style>
</head>
<body>
    <h1>Performance Benchmark Trends</h1>
"""
    
    for idx, (test_name, series) in enumerate(grouped.items()):
        html += f"""
    <h2>{test_name}</h2>
    <div class="chart-container">
        <canvas id="chart_{idx}"></canvas>
    </div>
    <script>
    new Chart(document.getElementById('chart_{idx}'), {{
        type: 'line',
        data: {{
            labels: {json.dumps(series["labels"])},
            datasets: [
                {{ label: 'Latency (ms)', data: {json.dumps(series["latency"])}, borderColor: 'rgb(255, 99, 132)', yAxisID: 'y' }},
                {{ label: 'Memory (MB)', data: {json.dumps(series["memory"])}, borderColor: 'rgb(54, 162, 235)', yAxisID: 'y1' }}
            ]
        }},
        options: {{
            responsive: true,
            scales: {{
                y: {{ type: 'linear', display: true, position: 'left', title: {{ display: true, text: 'Latency (ms)' }} }},
                y1: {{ type: 'linear', display: true, position: 'right', title: {{ display: true, text: 'Memory (MB)' }}, grid: {{ drawOnChartArea: false }} }},
            }}
        }}
    }});
    </script>
"""
    html += "</body></html>"
    
    with open(html_path, 'w') as f:
        f.write(html)
    print(f"\nHTML Report generated at {html_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance & Scalability Test Suite")
    parser.add_argument("--out", default="benchmarks_history.csv", help="Output CSV file")
    parser.add_argument("--compare-with", default=None, help="Compare with a previous CSV run")
    parser.add_argument("--html", default="benchmark_report.html", help="Generate HTML report")
    
    args = parser.parse_args()
    
    print("Running Performance Suite...")
    run_benchmarks(args.out)
    
    if args.compare_with:
        compare_reports(args.out, args.compare_with)
        
    if args.html:
        generate_html_report(args.out, args.html)
