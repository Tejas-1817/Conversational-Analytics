from __future__ import annotations

import json
import re

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def rewrite(question: str, conversation_context: str = "") -> list[str]:
    """Return 1 to N search strings. Failure returns the original question."""
    settings = get_settings()
    question = (question or "").strip()
    if not question:
        return []
    if not settings.rag_query_rewrite_enabled:
        return [question]
    try:
        from app.chat_sql.llm_provider import LLMProvider

        prompt = f"""Rewrite the user question into search queries.
Return JSON only: {{"search_queries": ["..."]}}
Use at most {settings.rag_max_query_variants} queries.
Resolve pronouns from the conversation. Do not add facts.

CONVERSATION:
{(conversation_context or "None")[:2000]}

QUESTION:
{question}
"""
        raw = LLMProvider().generate_text(prompt, max_tokens=300)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        queries = [str(item).strip() for item in payload.get("search_queries", []) if str(item).strip()]
        queries = queries[: settings.rag_max_query_variants]
        if question not in queries:
            queries.insert(0, question)
        return queries or [question]
    except Exception as exc:
        log.warning("rag_v2_rewrite_failed", error=type(exc).__name__)
        return [question]