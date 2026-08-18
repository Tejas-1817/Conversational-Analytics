"""FastAPI application entry point — Phase 6 hardened with security middleware."""
import structlog
from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import api_keys, auth, chat_sql, dashboards, deterministic_semantic, engine, eval, jobs, metadata, oidc, schema, semantic, sources, tenants, users
from app.config import get_settings
from app.db import get_engine, session_scope
from app.models import User
from app.security.auth import get_password_hash


# ---------------------------------------------------------------------------
# Structured logging processors
# ---------------------------------------------------------------------------

def redact_secrets(logger, log_method, event_dict):
    sensitive_keys = {"password", "token", "authorization", "secret", "api_key",
                      "encryption_key", "client_secret", "key_hash"}
    for k in sensitive_keys:
        if k in event_dict:
            event_dict[k] = "*** REDACTED ***"
    return event_dict


def add_correlation_id(logger, log_method, event_dict):
    if correlation_id.get():
        event_dict["correlation_id"] = correlation_id.get()
    return event_dict


structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    add_correlation_id,
    redact_secrets,
    structlog.processors.add_log_level,
    structlog.processors.JSONRenderer(),
])
log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects OWASP-recommended HTTP security headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        return response


# ---------------------------------------------------------------------------
# Request size limit middleware
# ---------------------------------------------------------------------------

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose body exceeds the configured limit."""

    def __init__(self, app, max_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Max: {self._max_bytes // (1024*1024)} MB"},
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate limiting (slowapi)
# ---------------------------------------------------------------------------

def _setup_rate_limiter(app: FastAPI) -> None:
    """Configure slowapi rate limiter. Gracefully skip if not installed."""
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        log.info("rate_limiter_enabled")
    except ImportError:
        log.warning("slowapi_not_installed", hint="pip install slowapi to enable rate limiting")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title="Conversational Analytics Platform — API",
    version="1.0.0",
    description=(
        "Enterprise-grade Conversational Analytics Platform. "
        "Phases 1-6: Schema Ingestion, Semantic Layer, Query Engine, "
        "SaaS Frontend, Charts & Dashboard Engine, "
        "Enterprise Multi-Tenancy & Production Security."
    ),
    # Disable /docs and /redoc in production by checking an env flag
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware order matters — add innermost first
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_size_bytes)

# CORS — restrict to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
    expose_headers=["X-Correlation-ID"],
)

_setup_rate_limiter(app)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     # Log the actual error for developers
#     log.error("unhandled_exception", error=str(exc), path=request.url.path, method=request.method)
#     # Return a generic 500 without leaking stack traces
#     return JSONResponse(
#         status_code=500,
#         content={"detail": "Internal Server Error"}
#     )


from app.api import (
    api_keys,
    auth,
    dashboards,
    domains_router,
    engine,
    jobs,
    metadata,
    semantic,
    sources,
    tenants,
    users,
)

app.include_router(auth.router)
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(metadata.router)
app.include_router(semantic.router)
app.include_router(engine.router)
app.include_router(dashboards.router)
app.include_router(users.router)

# Phase 6 — new routers
app.include_router(tenants.router)
app.include_router(api_keys.router)
app.include_router(domains_router.router)
app.include_router(oidc.router)
app.include_router(eval.router)
app.include_router(schema.router)
app.include_router(deterministic_semantic.router)
app.include_router(chat_sql.router)


# ---------------------------------------------------------------------------
# Startup: Bootstrap admin user
# ---------------------------------------------------------------------------

@app.on_event("startup")
def bootstrap_admin():
    settings = get_settings()
    if not settings.admin_bootstrap_email or not settings.admin_bootstrap_password:
        log.warning("skipping_admin_bootstrap_missing_credentials")
        return

    # Automatically create missing metadata tables and enums if database is empty
    try:
        from app.models import (
            Base, Tenant, User, RevokedToken, Conversation, ConversationMessage,
            ApiKey, OIDCProvider, DataSource, TableMeta, ColumnMeta, IndexMeta, AuditLog
        )
        engine = get_engine()
        enum_defs = {
            "approval_status": "('draft', 'reviewed', 'approved', 'rejected', 'needs_clarification')",
            "column_role": "('dimension', 'measure', 'key', 'attribute', 'unknown')",
            "additivity_type": "('additive', 'semi_additive', 'non_additive', 'not_applicable')",
            "rel_source": "('declared_fk', 'naming', 'value_overlap', 'llm')",
            "job_status": "('queued', 'running', 'succeeded', 'failed', 'succeeded_with_warnings')",
            "source_type": "('postgres', 'mysql', 'snowflake', 'bigquery')",
            "user_role": "('ADMIN', 'ANALYST', 'VIEWER')",
            "agg_type": "('SUM', 'AVG', 'COUNT', 'COUNT_DISTINCT', 'MIN', 'MAX', 'CUSTOM')",
            "join_type": "('INNER', 'LEFT', 'RIGHT', 'FULL')",
            "entity_type": "('METRIC', 'DIMENSION', 'GLOSSARY')",
            "time_grain": "('YEAR', 'QUARTER', 'MONTH', 'WEEK', 'DAY', 'HOUR', 'NONE')",
            "col_security_action": "('deny', 'mask', 'hash', 'partial_mask')",
            "generation_status": "('GENERATING', 'ACTIVE', 'REVIEW_REQUIRED', 'REJECTED', 'DRAFT', 'VALIDATED', 'ARCHIVED')",
            "generation_source": "('MANUAL', 'AI')"
        }
        with engine.begin() as conn:
            for enum_name, values in enum_defs.items():
                check_sql = text(f"SELECT 1 FROM pg_type WHERE typname = '{enum_name}'")
                res = conn.execute(check_sql).fetchone()
                if not res:
                    conn.execute(text(f"CREATE TYPE {enum_name} AS ENUM {values}"))

        infra_tables = [
            Tenant.__table__, User.__table__, RevokedToken.__table__,
            Conversation.__table__, ConversationMessage.__table__, ApiKey.__table__,
            OIDCProvider.__table__, DataSource.__table__, TableMeta.__table__,
            ColumnMeta.__table__, IndexMeta.__table__, AuditLog.__table__
        ]
        for tbl in infra_tables:
            try:
                Base.metadata.create_all(bind=engine, tables=[tbl])
            except Exception as e:
                log.warning("table_creation_warning", table=tbl.name, error=str(e))
    except Exception as exc:
        log.warning("database_table_creation_warning", error=str(exc))

    try:
        with session_scope() as session:
            admin = session.query(User).filter(User.email == settings.admin_bootstrap_email).first()
            if not admin:
                log.info("bootstrapping_first_admin", email=settings.admin_bootstrap_email)
                new_admin = User(
                    tenant_id=settings.default_tenant_id,
                    email=settings.admin_bootstrap_email,
                    password_hash=get_password_hash(settings.admin_bootstrap_password),
                    role="ADMIN",
                )
                session.add(new_admin)
                session.flush()

                # Audit the bootstrap creation
                from app.audit import AuditEvent, audit
                audit(
                    session,
                    tenant_id=new_admin.tenant_id,
                    entity_type="users",
                    entity_id=new_admin.id,
                    action=AuditEvent.USER_CREATED,
                    actor="system:bootstrap",
                    after={"email": settings.admin_bootstrap_email, "role": "ADMIN"},
                )
                session.commit()
            else:
                # Refresh password hash if invalid
                from app.security.auth import verify_password
                if not verify_password(settings.admin_bootstrap_password, admin.password_hash):
                    admin.password_hash = get_password_hash(settings.admin_bootstrap_password)
                    session.commit()
                    log.info("refreshed_admin_password_hash")
    except Exception as exc:
        log.warning("admin_bootstrap_skipping", error=str(exc))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
def health() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "metadata_db": "up"}
    except Exception as exc:
        log.error("health_check_failed", error=str(exc))
        return {"status": "degraded", "metadata_db": "down"}
