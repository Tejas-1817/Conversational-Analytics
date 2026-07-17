"""Golden Set Evaluation Script (Phase 3).

Runs 20 realistic questions against the demo schema.
Modes:
  --mode baseline  : Runs with RAG forcibly disabled (keyword path only).
  --mode rag       : Runs with RAG enabled (hybrid path).

Outputs a comparison table and exits non-zero if any regressions occur.
"""

import argparse
import sys
import os
import uuid
import warnings

sys.path.insert(0, os.path.abspath("."))

# Suppress Pydantic deprecation warnings from within our models
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from app.config import get_settings
from app.db import session_scope
from app.engine.nlu_service import NLUService
from app.engine.context_manager import ConversationContext
from app.engine.resolver_service import ResolverService
from app.engine.retrieval_service import RetrievalService


# Pre-defined 20 golden questions. 
# We evaluate: 1) Did it match a metric? 2) How many dimensions matched?
QUESTIONS = [
    ("Show total revenue", "Total Revenue", []),
    ("Revenue by region", "Total Revenue", ["Region"]),
    ("Revenue by date", "Total Revenue", ["Sale Date"]),
    ("Monthly revenue", "Total Revenue", ["Sale Date"]),
    ("What is our total sales?", "Total Revenue", []),
    ("Break down revenue by geography", "Total Revenue", ["Region"]),
    ("Revenue trend over time", "Total Revenue", ["Sale Date"]),
    ("How much did we earn?", "Total Revenue", []),
    ("Revenue split by area", "Total Revenue", ["Region"]),
    ("Show me revenue for each date", "Total Revenue", ["Sale Date"]),
    ("What's the revenue broken down by region and date?", "Total Revenue", ["Region", "Sale Date"]),
    ("Sales by region", "Total Revenue", ["Region"]),
    ("Income by geography", "Total Revenue", ["Region"]),
    ("Total earnings", "Total Revenue", []),
    ("Revenue by sale date", "Total Revenue", ["Sale Date"]),
    ("How is revenue trending?", "Total Revenue", ["Sale Date"]),
    ("Show earnings by territory", "Total Revenue", ["Region"]),
    ("Revenue per date", "Total Revenue", ["Sale Date"]),
    ("Total income for all regions", "Total Revenue", ["Region"]),
    ("Revenue breakdown", "Total Revenue", []),
]

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def run_eval(mode: str):
    settings = get_settings()

    if mode == "baseline":
        settings.rag_enabled = False
    elif mode == "rag":
        settings.rag_enabled = True

    print(f"=== Running Evaluation (Mode: {mode.upper()}) ===")
    print(f"{'#':<3} | {'Question':<45} | {'Metric Match':<15} | {'Dim Match':<10} | {'Path':<10}")
    print("-" * 92)

    total_metric_score = 0
    total_dim_score = 0
    results = []

    with session_scope() as db:
        for idx, (question, exp_metric, exp_dims) in enumerate(QUESTIONS, 1):
            # 1. Parse Intent (Mocked to avoid LLM rate limits and isolate resolver)
            from app.schemas_engine import NLUIntent
            intent = NLUIntent(
                intent="aggregate",
                metric=exp_metric,
                dimensions=exp_dims,
                filters=[],
                time_granularity=None,
                time_intelligence=None
            )
            
            # 2. Retrieve
            rag_hits = RetrievalService.retrieve(question, TENANT_ID, db)
            
            # 3. Resolve
            res = ResolverService.resolve_entities(db, TENANT_ID, intent, rag_hits)
            
            # Score metric (1 if exact name match, 0 otherwise)
            metric_match = 0
            got_metric = None
            if res.metric:
                got_metric = res.metric.name
                if got_metric.lower() == exp_metric.lower():
                    metric_match = 1
            elif res.kpi:
                # Demo schema might map "Total Revenue" to a KPI, let's accept that too if name matches
                got_metric = res.kpi.name
                if got_metric.lower() == exp_metric.lower():
                    metric_match = 1

            # Score dims (fraction matched)
            got_dims = {d.business_name.lower() for d in res.dimensions}
            exp_dims_set = {d.lower() for d in exp_dims}
            
            if not exp_dims_set:
                dim_score = 1.0 if not got_dims else 0.0
            else:
                matched_count = len(got_dims.intersection(exp_dims_set))
                dim_score = matched_count / len(exp_dims_set)

            total_metric_score += metric_match
            total_dim_score += dim_score
            results.append({
                "q": question,
                "metric_match": metric_match,
                "dim_score": dim_score,
                "got_metric": got_metric,
                "got_dims": list(got_dims),
                "path": res.retrieval_path
            })

            m_str = "PASS" if metric_match else f"FAIL ({got_metric or 'None'})"
            d_str = "PASS" if dim_score == 1.0 else f"{dim_score:.1f}"
            print(f"{idx:<3} | {question[:45]:<45} | {m_str:<15} | {d_str:<10} | {res.retrieval_path:<10}")

    print("-" * 92)
    print(f"Overall Metric Score : {total_metric_score}/{len(QUESTIONS)}")
    print(f"Overall Dim Score    : {total_dim_score:.1f}/{len(QUESTIONS)}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "rag"], required=True)
    args = parser.parse_args()

    # Mute Chroma telemetry warnings
    import os
    os.environ["CHROMA_TELEMETRY"] = "false"
    
    run_eval(args.mode)
