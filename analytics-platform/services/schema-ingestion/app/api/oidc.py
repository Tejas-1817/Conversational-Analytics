"""
OIDC / SSO Authentication API.

Supports pluggable identity providers:
  - Microsoft Entra ID (Azure AD)
  - Google Workspace
  - Okta
  - Auth0
  - Keycloak
  - Any standard OIDC-compliant IdP

Flow:
  1. Frontend calls GET /auth/oidc/login  → redirected to IdP
  2. IdP authenticates user, redirects to GET /auth/oidc/callback
  3. Backend exchanges code for tokens, extracts claims
  4. Backend finds or creates User scoped to the correct Tenant
  5. Backend issues platform JWT pair (access + refresh)
  6. Frontend receives tokens and logs in normally

Requires:
  - OIDC_ENABLED=true
  - OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ISSUER_URL
  - authlib package: pip install authlib httpx

When OIDC_ENABLED=false, these endpoints return 503.
"""
from __future__ import annotations

import secrets
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import AuditEvent, audit
from app.config import get_settings
from app.db import get_session
from app.models import User
from app.security.auth import create_access_token, create_refresh_token, get_password_hash

log = structlog.get_logger()
router = APIRouter(prefix="/auth/oidc", tags=["auth-oidc"])

# In-memory state store for CSRF protection (production: use Redis)
_state_store: dict[str, str] = {}


def _require_oidc_enabled():
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=503,
            detail="OIDC/SSO is not enabled. Set OIDC_ENABLED=true in .env to activate.",
        )
    return settings


def _get_oidc_client(settings):
    """Build an authlib OAuth2 client for the configured IdP."""
    try:
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        return AsyncOAuth2Client(
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            scope=" ".join(["openid", "email", "profile"]),
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="authlib is not installed. Run: pip install authlib httpx",
        )


@router.get("/login")
async def oidc_login(request: Request):
    """
    Initiate OIDC login flow.
    Redirects the user to the configured identity provider.
    """
    settings = _require_oidc_enabled()

    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    _state_store[state] = "pending"

    # Build authorization URL
    issuer = settings.oidc_issuer_url.rstrip("/")
    auth_endpoint = f"{issuer}/oauth2/authorize"

    # Handle well-known provider URL patterns
    if "login.microsoftonline.com" in issuer:
        auth_endpoint = f"{issuer}/oauth2/v2.0/authorize"
    elif "accounts.google.com" in issuer:
        auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    elif "okta.com" in issuer:
        auth_endpoint = f"{issuer}/v1/authorize"

    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    redirect_url = f"{auth_endpoint}?{query_string}"

    log.info("oidc_login_initiated", provider=settings.oidc_provider_name)
    return RedirectResponse(url=redirect_url)


class OIDCCallbackResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False


@router.get("/callback", response_model=OIDCCallbackResponse)
async def oidc_callback(
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """
    Handle the OIDC callback from the identity provider.
    Exchanges the authorization code for tokens, extracts user claims,
    and issues platform JWTs.
    """
    settings = _require_oidc_enabled()

    # Validate CSRF state
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    del _state_store[state]

    # Exchange code for tokens
    try:
        import httpx
        issuer = settings.oidc_issuer_url.rstrip("/")

        token_endpoint = f"{issuer}/oauth2/token"
        if "login.microsoftonline.com" in issuer:
            token_endpoint = f"{issuer}/oauth2/v2.0/token"
        elif "accounts.google.com" in issuer:
            token_endpoint = "https://oauth2.googleapis.com/token"
        elif "okta.com" in issuer:
            token_endpoint = f"{issuer}/v1/token"

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.oidc_redirect_uri,
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret,
                },
                timeout=10,
            )
            if token_response.status_code != 200:
                log.error("oidc_token_exchange_failed", status=token_response.status_code)
                raise HTTPException(status_code=401, detail="Failed to exchange authorization code")

            token_data = token_response.json()
            id_token = token_data.get("id_token")

            if not id_token:
                raise HTTPException(status_code=401, detail="No id_token in OIDC response")

            # Decode claims from ID token (without full verification for simplicity)
            # Production: use authlib or PyJWT with JWKS verification
            import base64
            import json
            parts = id_token.split(".")
            if len(parts) < 2:
                raise HTTPException(status_code=401, detail="Malformed ID token")

            padding = 4 - len(parts[1]) % 4
            claims_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
            claims = json.loads(claims_bytes)

    except HTTPException:
        raise
    except Exception as e:
        log.error("oidc_callback_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"OIDC error: {e}")

    email = claims.get("email") or claims.get("preferred_username")
    if not email:
        raise HTTPException(status_code=400, detail="No email claim in OIDC token")

    # Find or create user — scoped to the default tenant (can be extended for multi-tenant SSO)
    from app.config import get_settings
    default_tenant_id = uuid.UUID(get_settings().default_tenant_id)

    user = db.query(User).filter(User.email == email).first()
    is_new = False

    if not user:
        # Auto-provision user in the default tenant
        user = User(
            tenant_id=default_tenant_id,
            email=email,
            password_hash=get_password_hash(secrets.token_hex(32)),  # random unusable password
            role="VIEWER",
        )
        db.add(user)
        db.flush()
        is_new = True
        log.info("oidc_user_provisioned", email=email)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    # Issue platform JWTs
    access_token = create_access_token(subject=user.id, role=user.role, tenant_id=user.tenant_id)
    refresh_jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(subject=user.id, jti=refresh_jti)

    audit(
        db,
        tenant_id=user.tenant_id,
        entity_type="users",
        entity_id=user.id,
        action=AuditEvent.SSO_LOGIN,
        actor=user.email,
        after={"provider": settings.oidc_provider_name, "is_new_user": is_new},
        request=request,
        event_type=AuditEvent.SSO_LOGIN,
    )
    db.commit()

    log.info("oidc_login_success", email=email, provider=settings.oidc_provider_name)
    return OIDCCallbackResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        is_new_user=is_new,
    )
