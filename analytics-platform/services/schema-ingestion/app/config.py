"""Application configuration. All settings come from environment variables (.env)."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Metadata repository (our own Postgres)
    metadata_db_url: str = "postgresql+psycopg://ingestion:ingestion@localhost:5432/metadata"

    # Bootstrapping credentials
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    # Redis / job queue
    redis_url: str = "redis://localhost:6379/0"
    job_timeout_seconds: int = 3600

    # JWT Auth settings
    jwt_secret: str = "super-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 1440  # 24 hours

    # LLM Settings
    llm_provider: str = "mock"  # options: "gemini", "mock", "none", "huggingface"
    gemini_api_key: str = ""
    
    # Hugging Face Settings
    huggingface_api_key: str = ""
    hf_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    hf_max_tokens: int = 2048
    hf_timeout: int = 30
    hf_temperature: float = 0.0
    hf_top_p: float = 0.95
    hf_retry_count: int = 3

    # Phase 2 — Embedding pipeline
    embedding_model: str = "all-MiniLM-L6-v2"   # sentence-transformers model name
    chroma_persist_dir: str = "./chroma_store"   # local Chroma storage path
    embedding_provider: str = "sentence_transformers"  # options: sentence_transformers | mock

    # Phase 3 — RAG retrieval
    # Cosine distance threshold: hits with distance > threshold are discarded.
    # Empirically calibrated: true positives top out at ~0.54, nearest noise starts at ~0.70.
    rag_distance_threshold: float = 0.60
    rag_top_k: int = 10             # number of Chroma candidates to fetch per query
    rag_enabled: bool = True        # set False in CI / offline environments


    # Credential encryption key (Fernet, urlsafe base64, 32 bytes).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # Profiling guardrails
    profile_sample_rows: int = 10_000
    profile_top_n_values: int = 20
    statement_timeout_ms: int = 30_000
    overlap_sample_values: int = 1_000
    overlap_min_confidence: float = 0.90

    default_tenant_id: str = "00000000-0000-0000-0000-000000000001"

    # =========================================================================
    # Phase 6 — Security & Multi-Tenancy
    # =========================================================================

    # CORS: comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Secret backend: "env" (default, uses ENCRYPTION_KEY from env) or "vault"
    secret_backend: Literal["env", "vault"] = "env"

    # HashiCorp Vault (only used when secret_backend="vault")
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "dev-token"
    vault_mount: str = "secret"

    # OIDC / SSO (set OIDC_ENABLED=true to activate)
    oidc_enabled: bool = False
    oidc_provider_name: str = "generic"     # azure | google | okta | auth0 | keycloak
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_issuer_url: str = ""
    oidc_redirect_uri: str = "http://localhost:8000/auth/oidc/callback"

    # Rate limiting defaults (can be overridden per tenant in tenant_policies)
    rate_limit_chat: str = "100/minute"
    rate_limit_login: str = "10/minute"
    rate_limit_refresh: str = "30/minute"

    # Request size limit (bytes)
    max_request_size_bytes: int = 10 * 1024 * 1024  # 10MB

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
