"""app/context_layer/governance.py
Injects non-negotiable security guardrails, RLS filters, and PII masking into context.
"""
from __future__ import annotations
import uuid
from typing import List, Dict, Any
import structlog
from sqlalchemy.orm import Session
from app.models import ColumnMeta, TableMeta

log = structlog.get_logger(__name__)


class GovernanceContext:
    """Builds security, RLS, and column masking rules for the prompt."""

    SENSITIVE_PATTERNS = ["password", "token", "secret", "ssn", "credit_card", "cvv", "salary", "hash"]

    @classmethod
    def build_governance_rules(
        cls,
        db: Session,
        tenant_id: uuid.UUID,
        user_role: str,
        relevant_tables: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Construct deterministic security and RLS rules."""
        
        # 1. Multi-tenant mandatory isolation filter
        rls_directive = f"STRICT TENANT ISOLATION: For any table containing a 'tenant_id' column, you MUST include 'WHERE tenant_id = '{str(tenant_id)}''."

        # 2. Column-Level Security (CLS) - identify sensitive columns
        masked_columns = []
        if user_role.lower() not in ("superadmin", "owner"):
            try:
                cols = (
                    db.query(ColumnMeta.column_name, TableMeta.table_name)
                    .join(TableMeta, ColumnMeta.table_id == TableMeta.id)
                    .filter(TableMeta.is_active == True)
                    .all()
                )
                for col_name, tbl_name in cols:
                    c_lower = col_name.lower()
                    if any(pat in c_lower for pat in cls.SENSITIVE_PATTERNS):
                        masked_columns.append(f"{tbl_name}.{col_name}")
            except Exception as exc:
                log.warning("governance_cls_detection_error", error=str(exc))
                try:
                    db.rollback()
                except Exception:
                    pass

        cls_directive = ""
        if masked_columns:
            sample_masked = ", ".join(masked_columns[:8])
            cls_directive = (
                f"RESTRICTED SENSITIVE COLUMNS: Never select plain values for: {sample_masked}. "
                "Only aggregate (e.g. AVG, COUNT) if permitted, or return UNANSWERABLE if sensitive data is explicitly requested."
            )

        # 3. Execution boundary (Limit cap)
        limit_directive = "RESULT CAP: Always apply a LIMIT clause (maximum 1,000 rows; use LIMIT 10-15 for ranking/trend charts) to prevent memory exhaustion."

        return {
            "rls_directive": rls_directive,
            "cls_directive": cls_directive,
            "limit_directive": limit_directive,
        }
