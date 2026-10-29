"""app/context_layer/rules_engine.py
Retrieves relevant institutional knowledge, operational exclusions, and entity maps.
"""
from __future__ import annotations
import uuid
import re
from typing import Any, Dict, List
import structlog
from sqlalchemy.orm import Session

from app.models import BusinessRule

log = structlog.get_logger(__name__)


class RulesEngine:
    """Matches user questions against institutional business rules and concept ontologies."""

    @staticmethod
    def resolve_rules(
        db: Session,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID | None,
        question: str,
        relevant_tables: List[str] | None = None,
        limit: int = 4,
    ) -> List[Dict[str, str]]:
        """Retrieve the top matching institutional rules for this question and its tables."""
        q_lower = (question or "").lower()
        tables_set = set(t.lower() for t in (relevant_tables or []))
        matched_rules: List[Dict[str, str]] = []

        try:
            rules = (
                db.query(BusinessRule)
                .filter(
                    BusinessRule.tenant_id == tenant_id,
                    BusinessRule.is_active == True,
                )
                .all()
            )

            scored = []
            for r in rules:
                score = 0
                # Check keyword match
                if r.keywords:
                    kws = [k.strip().lower() for k in r.keywords.split(",") if k.strip()]
                    for kw in kws:
                        if kw in q_lower:
                            score += 5

                # Check table match
                if r.applies_to_tables:
                    rule_tables = set(t.lower() for t in r.applies_to_tables)
                    if tables_set.intersection(rule_tables):
                        score += 8

                # Title match
                if r.rule_title.lower() in q_lower:
                    score += 6

                if score > 0 or r.category == "fiscal_calendar":
                    scored.append((score, r))

            scored.sort(key=lambda x: x[0], reverse=True)
            for _, r in scored[:limit]:
                matched_rules.append({
                    "title": r.rule_title,
                    "instruction": r.rule_instruction,
                    "category": r.category,
                })

        except Exception as exc:
            log.warning("rules_engine_resolution_error", error=str(exc))
            try:
                db.rollback()
            except Exception:
                pass

        return matched_rules
