"""Application configuration. All settings come from environment variables (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Metadata repository (our own Postgres)
    metadata_db_url: str = "postgresql+psycopg://ingestion:ingestion@localhost:5432/metadata"

    # Redis / job queue
    redis_url: str = "redis://localhost:6379/0"
    job_timeout_seconds: int = 3600

    # API auth (skeleton-level: single static key; replace with SSO/OIDC before any real deployment)
    api_key: str = "change-me"

    # Credential encryption key (Fernet, urlsafe base64, 32 bytes).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # Profiling guardrails — enforced in code, not convention
    profile_sample_rows: int = 10_000       # max rows sampled per table for column stats
    profile_top_n_values: int = 20          # sample values stored per column
    statement_timeout_ms: int = 30_000      # per-query timeout on customer databases
    overlap_sample_values: int = 1_000      # distinct values sampled for value-overlap checks
    overlap_min_confidence: float = 0.90    # below this, candidate is not persisted

    default_tenant_id: str = "00000000-0000-0000-0000-000000000001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
