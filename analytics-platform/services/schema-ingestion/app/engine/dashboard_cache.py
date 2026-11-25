"""Dashboard Result Cache (Phase 2).

Provides per-viewer, permission-fingerprinted result caching for dashboard widgets.
Cached in Redis with short TTL and fallback to local memory cache if Redis is down.
Cached rows are never shared across users and never persisted to the database.
"""
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User

logger = logging.getLogger(__name__)


class DashboardResultCache:
    _instance = None
    _memory_cache: dict[str, tuple[float, str]] = {}  # key -> (expires_at, json_data)

    def __init__(self):
        self.settings = get_settings()
        self._redis_client = None
        self._init_redis()

    def _init_redis(self):
        try:
            import redis
            self._redis_client = redis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
                decode_responses=True,
            )
            # Ping to verify connectivity
            self._redis_client.ping()
        except Exception as exc:
            logger.debug("Redis cache not available, using in-memory cache: %s", exc)
            self._redis_client = None

    @classmethod
    def get_instance(cls) -> "DashboardResultCache":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def compute_permission_hash(user: User, source_id: uuid.UUID | None, db: Session) -> str:
        """
        Compute a SHA-256 fingerprint representing the viewer's exact data access permissions.
        If user permissions change, the hash changes, preventing stale cache access.
        """
        permitted_tables: list[str] = []
        if source_id and user.role != "ADMIN":
            from app.api.deps import get_user_permitted_table_ids
            from app.models import TableMeta
            from sqlalchemy import select

            t_ids = get_user_permitted_table_ids(db, user, source_id)
            if t_ids:
                names = db.scalars(
                    select(TableMeta.table_name).where(TableMeta.id.in_(t_ids))
                ).all()
                permitted_tables = sorted([n.lower() for n in names])

        raw_str = f"{user.tenant_id}:{user.id}:{user.role}:{source_id}:{','.join(permitted_tables)}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    def make_cache_key(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        permission_hash: str,
        insight_id: uuid.UUID,
        query_sql: str,
    ) -> str:
        q_hash = hashlib.sha256(query_sql.strip().encode("utf-8")).hexdigest()[:16]
        return f"dash_cache:{tenant_id}:{user_id}:{permission_hash}:{insight_id}:{q_hash}"

    def get(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        permission_hash: str,
        insight_id: uuid.UUID,
        query_sql: str,
    ) -> dict[str, Any] | None:
        if not self.settings.dashboard_cache_enabled:
            return None

        key = self.make_cache_key(tenant_id, user_id, permission_hash, insight_id, query_sql)

        # Try Redis first
        if self._redis_client:
            try:
                raw = self._redis_client.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.debug("Redis cache read error: %s", e)

        # Fallback to in-memory cache
        now = time.time()
        if key in self._memory_cache:
            expires_at, raw = self._memory_cache[key]
            if now < expires_at:
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            else:
                del self._memory_cache[key]

        return None

    def set(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        permission_hash: str,
        insight_id: uuid.UUID,
        query_sql: str,
        payload: dict[str, Any],
    ) -> bool:
        if not self.settings.dashboard_cache_enabled:
            return False

        key = self.make_cache_key(tenant_id, user_id, permission_hash, insight_id, query_sql)
        ttl = self.settings.dashboard_cache_ttl_seconds

        # Add cache metadata
        cached_payload = dict(payload)
        cached_payload["cached"] = True
        cached_payload["cached_at"] = datetime.now(timezone.utc).isoformat()

        try:
            raw = json.dumps(cached_payload, default=str)
        except Exception:
            return False

        # Enforce size limit
        if len(raw.encode("utf-8")) > self.settings.dashboard_cache_max_bytes:
            logger.debug("Result size exceeds cache max bytes, skipping caching")
            return False

        # Set in Redis
        stored = False
        if self._redis_client:
            try:
                self._redis_client.setex(key, ttl, raw)
                stored = True
            except Exception as e:
                logger.debug("Redis cache write error: %s", e)

        # Always store in memory cache as well / fallback
        self._memory_cache[key] = (time.time() + ttl, raw)
        return stored or True

    def clear_for_source(self, source_id: uuid.UUID) -> None:
        """Clear cache entries when a source schema is re-ingested or updated."""
        s_id_str = str(source_id)
        if self._redis_client:
            try:
                keys = self._redis_client.keys("dash_cache:*")
                for k in keys:
                    self._redis_client.delete(k)
            except Exception as e:
                logger.debug("Redis cache clear error: %s", e)
        self._memory_cache.clear()

    def clear_all(self) -> None:
        """Clear all dashboard cache entries."""
        if self._redis_client:
            try:
                keys = self._redis_client.keys("dash_cache:*")
                if keys:
                    self._redis_client.delete(*keys)
            except Exception as e:
                logger.debug("Redis cache clear error: %s", e)
        self._memory_cache.clear()
