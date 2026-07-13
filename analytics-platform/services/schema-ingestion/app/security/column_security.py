"""
Column-Level Security (CLS) Engine.

Post-processes query result rows to apply:
  - deny:         Remove the column entirely from results
  - mask:         Replace the value with mask characters (e.g. "****")
  - hash:         SHA-256 hash the value (for linking without revealing data)
  - partial_mask: Show only last N characters (e.g. "****1234" for card numbers)

The CLS engine runs AFTER SQL execution and BEFORE results are returned to
the frontend, so sensitive data is never transmitted over the wire.

Usage:
    from app.security.column_security import ColumnSecurityEngine

    processed = ColumnSecurityEngine.apply(
        session, tenant_id, user_role, table_name, columns, rows
    )
    # processed is (columns_out, rows_out) with security applied
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models import ColumnSecurityPolicy

log = structlog.get_logger()


class ColumnSecurityEngine:
    """
    Evaluates column security policies and transforms result sets accordingly.
    """

    @classmethod
    def apply(
        cls,
        session: Session,
        tenant_id: uuid.UUID,
        user_role: str,
        table_name: str,
        columns: list[str],
        rows: list[dict],
        source_id: uuid.UUID | None = None,
    ) -> tuple[list[str], list[dict]]:
        """
        Apply column-level security to a result set.

        Returns:
            (columns, rows) with security policies applied.
            Denied columns are removed from both columns list and row dicts.
        """
        # Admins always see everything
        if user_role == "ADMIN":
            return columns, rows

        policies = cls._load_policies(session, tenant_id, user_role, table_name, source_id)
        if not policies:
            return columns, rows

        # Build policy map: column_name -> ColumnSecurityPolicy
        policy_map: dict[str, ColumnSecurityPolicy] = {p.column_name.lower(): p for p in policies}

        denied_columns: set[str] = set()
        for col in columns:
            policy = policy_map.get(col.lower())
            if policy and policy.action == "deny":
                denied_columns.add(col)
                log.info("cls_column_denied", column=col, role=user_role)

        # Filter columns list
        columns_out = [c for c in columns if c not in denied_columns]

        # Apply per-row transformations
        rows_out: list[dict] = []
        for row in rows:
            new_row: dict[str, Any] = {}
            for col, val in row.items():
                if col in denied_columns:
                    continue  # skip denied columns
                policy = policy_map.get(col.lower())
                if policy:
                    new_row[col] = cls._transform(val, policy)
                else:
                    new_row[col] = val
            rows_out.append(new_row)

        return columns_out, rows_out

    @classmethod
    def _load_policies(
        cls,
        session: Session,
        tenant_id: uuid.UUID,
        user_role: str,
        table_name: str,
        source_id: uuid.UUID | None,
    ) -> list[ColumnSecurityPolicy]:
        """Load active CLS policies matching the current context."""
        query = session.query(ColumnSecurityPolicy).filter(
            ColumnSecurityPolicy.tenant_id == tenant_id,
            ColumnSecurityPolicy.is_active == True,  # noqa: E712
            ColumnSecurityPolicy.table_name == table_name,
        )
        if source_id:
            query = query.filter(
                (ColumnSecurityPolicy.source_id == source_id)
                | (ColumnSecurityPolicy.source_id == None)  # noqa: E711
            )

        all_policies = query.all()
        # Only return policies that apply to this role
        return [p for p in all_policies if user_role in (p.applies_to_roles or [])]

    @staticmethod
    def _transform(value: Any, policy: ColumnSecurityPolicy) -> Any:
        """Apply the policy's transformation action to a single value."""
        if value is None:
            return None

        action = policy.action
        str_val = str(value)

        if action == "mask":
            mask_char = policy.mask_char or "*"
            return mask_char * len(str_val)

        elif action == "hash":
            return hashlib.sha256(str_val.encode("utf-8")).hexdigest()

        elif action == "partial_mask":
            visible = policy.visible_chars or 4
            mask_char = policy.mask_char or "*"
            if len(str_val) <= visible:
                return mask_char * len(str_val)
            masked_part = mask_char * (len(str_val) - visible)
            return masked_part + str_val[-visible:]

        # "deny" is handled at the column level — this should never be reached
        return value
