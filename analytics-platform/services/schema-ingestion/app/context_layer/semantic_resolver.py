"""app/context_layer/semantic_resolver.py
Resolves approved semantic metrics and glossary terms for the Context Layer.
"""
from __future__ import annotations
import uuid
import re
from typing import Any, Dict, List
import structlog
from sqlalchemy.orm import Session

from app.models import SemanticMetric, BusinessGlossary, SemanticSynonym, TableMeta

log = structlog.get_logger(__name__)


class SemanticResolver:
    """Matches user questions against approved semantic metrics and glossary terms."""

    @staticmethod
    def resolve_metrics(
        db: Session,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        question: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find approved metrics that are relevant to the user question."""
        q_lower = (question or "").lower()
        resolved: List[Dict[str, Any]] = []

        try:
            # 1. Fetch all approved metrics for this tenant
            metrics = (
                db.query(SemanticMetric)
                .filter(
                    SemanticMetric.tenant_id == tenant_id,
                    SemanticMetric.status == "approved",
                    SemanticMetric.review_status == "ACTIVE",
                )
                .all()
            )

            # 2. Score relevance based on keyword and synonym matching
            scored_metrics = []
            for m in metrics:
                score = 0
                name_clean = (m.name or "").replace("_", " ").lower()
                biz_name = (m.business_name or "").lower()

                # Exact or phrase match
                if name_clean and name_clean in q_lower:
                    score += 10
                if biz_name and biz_name in q_lower:
                    score += 12

                # Word overlap match
                name_tokens = set(re.findall(r"\w+", name_clean))
                q_tokens = set(re.findall(r"\w+", q_lower))
                overlap = name_tokens.intersection(q_tokens)
                score += len(overlap) * 2

                if score > 0:
                    scored_metrics.append((score, m))

            # 3. Sort by relevance and take the top matches (Intentional Context: Less is More)
            scored_metrics.sort(key=lambda x: x[0], reverse=True)
            top_metrics = [m for _, m in scored_metrics[:limit]]

            for m in top_metrics:
                # Resolve source table name if linked
                table_name = "unknown"
                if m.source_table_id:
                    tbl = db.query(TableMeta).filter(TableMeta.id == m.source_table_id).first()
                    if tbl:
                        table_name = tbl.table_name

                resolved.append({
                    "name": m.name,
                    "business_name": m.business_name or m.name,
                    "description": m.description or "",
                    "aggregation": m.aggregation_type,
                    "expression": m.expression,
                    "table_name": table_name,
                })

        except Exception as exc:
            log.warning("semantic_metric_resolution_error", error=str(exc))

        return resolved

    @staticmethod
    def resolve_glossary(
        db: Session,
        tenant_id: uuid.UUID,
        question: str,
        limit: int = 4,
    ) -> List[Dict[str, str]]:
        """Find business glossary terms that match terms in the question."""
        q_lower = (question or "").lower()
        resolved: List[Dict[str, str]] = []

        try:
            terms = (
                db.query(BusinessGlossary)
                .filter(
                    BusinessGlossary.tenant_id == tenant_id,
                    BusinessGlossary.status == "approved",
                )
                .all()
            )

            for t in terms:
                term_clean = (t.term or "").lower()
                # Check for word boundary match (e.g. \bARR\b or \bchurn\b)
                if re.search(rf"\b{re.escape(term_clean)}\b", q_lower):
                    resolved.append({
                        "term": t.term,
                        "definition": t.business_definition,
                    })
                    if len(resolved) >= limit:
                        break

        except Exception as exc:
            log.warning("glossary_resolution_error", error=str(exc))

        return resolved
