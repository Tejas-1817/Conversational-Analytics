"""app/context_layer/engine.py
Central orchestrator for assembling intentional, verified Context Layer payloads.
"""
from __future__ import annotations
import uuid
from typing import Any, Dict, List
import structlog
from sqlalchemy.orm import Session

from app.context_layer.semantic_resolver import SemanticResolver
from app.context_layer.rules_engine import RulesEngine
from app.context_layer.governance import GovernanceContext

log = structlog.get_logger(__name__)


class ContextLayerEngine:
    """Assembles Data, Business, and Governance context at runtime."""

    @classmethod
    def assemble_context(
        cls,
        db: Session,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        question: str,
        user_role: str = "analyst",
        relevant_tables: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Builds a compact, intentional context package for the prompt."""
        
        # 1. Resolve Data Context (Semantic metrics & glossary)
        metrics = SemanticResolver.resolve_metrics(db, tenant_id, source_id, question, limit=3)
        glossary = SemanticResolver.resolve_glossary(db, tenant_id, question, limit=3)

        # 2. Resolve Business Context (Institutional rules)
        rules = RulesEngine.resolve_rules(db, tenant_id, source_id, question, relevant_tables, limit=3)

        # 3. Resolve Governance Context (RLS, CLS, limits)
        governance = GovernanceContext.build_governance_rules(db, tenant_id, user_role, relevant_tables)

        # 4. Format into clean text sections for the LLM prompt
        sections: List[str] = []

        if metrics:
            metric_lines = ["VERIFIED BUSINESS FORMULAS (MUST ADOPT EXACT CALCULATION):"]
            for m in metrics:
                metric_lines.append(
                    f"- Metric: \"{m['business_name']}\" ({m['name']})\n"
                    f"  Calculation: {m['aggregation']}({m['expression']})\n"
                    f"  Table: {m['table_name']}"
                )
            sections.append("\n".join(metric_lines))

        if glossary:
            gloss_lines = ["BUSINESS DEFINITIONS & ACRONYMS:"]
            for g in glossary:
                gloss_lines.append(f"- {g['term']}: {g['definition']}")
            sections.append("\n".join(gloss_lines))

        if rules:
            rule_lines = ["INSTITUTIONAL BUSINESS RULES:"]
            for r in rules:
                rule_lines.append(f"- {r['title']}: {r['instruction']}")
            sections.append("\n".join(rule_lines))

        # Always append Governance Directives
        gov_lines = ["GOVERNANCE & SECURITY RULES:"]
        gov_lines.append(f"- {governance['rls_directive']}")
        if governance['cls_directive']:
            gov_lines.append(f"- {governance['cls_directive']}")
        gov_lines.append(f"- {governance['limit_directive']}")
        sections.append("\n".join(gov_lines))

        # Combine and cap at 3,500 chars (Token-safe & Intentional)
        context_text = "\n\n".join(sections)[:3_500]

        return {
            "formatted_text": context_text,
            "metric_count": len(metrics),
            "rule_count": len(rules),
            "glossary_count": len(glossary),
        }
