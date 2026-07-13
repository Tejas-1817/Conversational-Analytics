"""
Audit trail — every security-sensitive action lands here.

Phase 6 enhancements:
  - Event type constants for consistent querying
  - Captures ip_address, user_agent, request_id, correlation_id
  - Integration with asgi-correlation-id
  - Immutable by design (insert-only, no update)

Usage:
    from app.audit import audit, AuditEvent

    audit(session,
          tenant_id=user.tenant_id,
          entity_type="conversation",
          entity_id=conv.id,
          action=AuditEvent.QUERY_EXECUTED,
          actor=user.email,
          request=request)  # FastAPI Request (optional, for IP/UA)
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models import AuditLog

log = structlog.get_logger()


class AuditEvent:
    """Well-known audit event type constants."""
    # Authentication
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    FAILED_LOGIN = "FAILED_LOGIN"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    SSO_LOGIN = "SSO_LOGIN"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"

    # User management
    USER_CREATED = "USER_CREATED"
    USER_DISABLED = "USER_DISABLED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"

    # Data sources
    SOURCE_REGISTERED = "SOURCE_REGISTERED"
    SOURCE_DELETED = "SOURCE_DELETED"
    INGESTION_STARTED = "INGESTION_STARTED"

    # Semantic layer
    METRIC_CREATED = "METRIC_CREATED"
    METRIC_UPDATED = "METRIC_UPDATED"
    METRIC_ROLLED_BACK = "METRIC_ROLLED_BACK"
    DIMENSION_CREATED = "DIMENSION_CREATED"
    GLOSSARY_TERM_CREATED = "GLOSSARY_TERM_CREATED"

    # AI / Query engine
    QUERY_EXECUTED = "QUERY_EXECUTED"
    QUERY_BLOCKED = "QUERY_BLOCKED"

    # Dashboards & Insights
    INSIGHT_SAVED = "INSIGHT_SAVED"
    DASHBOARD_CREATED = "DASHBOARD_CREATED"
    DASHBOARD_UPDATED = "DASHBOARD_UPDATED"
    DASHBOARD_DELETED = "DASHBOARD_DELETED"

    # Exports
    DATA_EXPORTED = "DATA_EXPORTED"

    # Security
    RLS_FILTER_APPLIED = "RLS_FILTER_APPLIED"
    COLUMN_MASKED = "COLUMN_MASKED"
    SECRET_ACCESSED = "SECRET_ACCESSED"
    SECRET_ROTATED = "SECRET_ROTATED"


def _extract_request_context(request: Any | None) -> dict:
    """Extract IP, User-Agent, and request ID from a FastAPI Request object."""
    if request is None:
        return {}
    try:
        from asgi_correlation_id import correlation_id
        ip = None
        # Prefer X-Forwarded-For (behind proxy) over direct client address
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            ip = request.client.host

        return {
            "ip_address": ip,
            "user_agent": request.headers.get("user-agent"),
            "request_id": request.headers.get("x-request-id") or correlation_id.get(),
        }
    except Exception:
        return {}


def audit(
    session: Session,
    *,
    tenant_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: str,
    before: dict | None = None,
    after: dict | None = None,
    event_type: str | None = None,
    request: Any | None = None,
) -> None:
    """
    Record an immutable audit log entry.

    Args:
        session:      Active DB session. Caller is responsible for commit.
        tenant_id:    Tenant scope.
        entity_type:  The type of entity affected (e.g. "conversation", "data_sources").
        entity_id:    UUID of the affected entity.
        action:       Human-readable action verb (e.g. AuditEvent.LOGIN).
        actor:        Email or system identifier of the actor.
        before:       Optional snapshot of the entity before the change.
        after:        Optional snapshot of the entity after the change.
        event_type:   AuditEvent constant for structured filtering. Defaults to action.
        request:      FastAPI Request object for IP/UA/request_id extraction.
    """
    ctx = _extract_request_context(request)
    entry = AuditLog(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        before=before,
        after=after,
        event_type=event_type or action,
        ip_address=ctx.get("ip_address"),
        user_agent=ctx.get("user_agent"),
        request_id=ctx.get("request_id"),
    )
    session.add(entry)
    log.info(
        "audit_event",
        event_type=event_type or action,
        entity=entity_type,
        entity_id=str(entity_id),
        actor=actor,
        tenant_id=str(tenant_id) if tenant_id else None,
    )


# Backwards-compatible alias for old callers that used record()
def record(
    session: Session,
    *,
    tenant_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Backwards-compatible wrapper around audit()."""
    audit(
        session,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        before=before,
        after=after,
    )
