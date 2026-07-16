import json
import os
import uuid

import redis
from sqlalchemy.orm import Session

from app.models import AIContext, SemanticKPI, SuggestedQuestion


class SemanticCache:
    """Redis-backed cache for compiled Semantic Models.
    
    Instead of repeatedly querying PostgreSQL for the complete AI Context,
    this class compiles the semantic model into a dense string representation
    and caches it in Redis for sub-second Prompt Builder utilization.
    """
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.from_url(redis_url)

    def _cache_key(self, semantic_model_id: uuid.UUID) -> str:
        return f"semantic_model_context:{semantic_model_id}"

    def get_context(self, db: Session, semantic_model_id: uuid.UUID) -> str:
        key = self._cache_key(semantic_model_id)
        try:
            cached = self.redis.get(key)
            if cached:
                return cached.decode("utf-8")
        except redis.RedisError:
            pass # Fallback to DB if redis is down

        # Build context if missing
        context_payload = self._build_context(db, semantic_model_id)

        try:
            self.redis.set(key, context_payload, ex=86400) # Cache for 1 day
        except redis.RedisError:
            pass

        return context_payload

    def _build_context(self, db: Session, semantic_model_id: uuid.UUID) -> str:
        ai_context = db.query(AIContext).filter_by(semantic_model_id=semantic_model_id).first()
        if not ai_context:
            return "{}"

        kpis = db.query(SemanticKPI).filter_by(semantic_model_id=semantic_model_id).all()
        questions = db.query(SuggestedQuestion).filter_by(semantic_model_id=semantic_model_id).all()

        payload = {
            "purpose": ai_context.purpose,
            "default_filters": ai_context.default_filters,
            "time_intelligence": ai_context.time_intelligence,
            "chart_preferences": ai_context.chart_preferences,
            "kpis": [{"name": k.name, "description": k.description, "formula": k.formula} for k in kpis],
            "suggested_questions": [{"question": q.question, "entity": q.entity_name} for q in questions]
        }
        return json.dumps(payload, indent=2)

semantic_cache = SemanticCache()
