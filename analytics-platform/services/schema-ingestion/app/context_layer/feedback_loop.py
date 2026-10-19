"""app/context_layer/feedback_loop.py
Handles Context Development Lifecycle (CDLC) feedback ingestion and review.
"""
from __future__ import annotations
import uuid
from typing import Optional
from sqlalchemy.orm import Session
import structlog

from app.models import BusinessRule, SemanticMetric

log = structlog.get_logger(__name__)


class ContextLifecycleManager:
    """Manages versioning and updates to business context from user feedback."""

    @staticmethod
    def add_or_update_rule(
        db: Session,
        tenant_id: uuid.UUID,
        rule_title: str,
        rule_instruction: str,
        category: str = "filter_exclusion",
        keywords: Optional[str] = None,
        source_id: Optional[uuid.UUID] = None,
    ) -> BusinessRule:
        """Create or update an institutional rule with incremented version."""
        existing = (
            db.query(BusinessRule)
            .filter(
                BusinessRule.tenant_id == tenant_id,
                BusinessRule.rule_title == rule_title,
            )
            .first()
        )

        if existing:
            existing.rule_instruction = rule_instruction
            existing.category = category
            existing.keywords = keywords
            existing.version += 1
            rule = existing
        else:
            rule = BusinessRule(
                tenant_id=tenant_id,
                source_id=source_id,
                rule_title=rule_title,
                rule_instruction=rule_instruction,
                category=category,
                keywords=keywords,
                version=1,
            )
            db.add(rule)

        db.commit()
        db.refresh(rule)
        log.info("business_rule_updated", title=rule.rule_title, version=rule.version)
        return rule
