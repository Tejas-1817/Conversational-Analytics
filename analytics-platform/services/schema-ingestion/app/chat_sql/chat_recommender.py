"""Deterministic follow-up recommendations for analytics chat."""

from __future__ import annotations

import json
import re
from typing import Any,Literal, Sequence
import structlog

log = structlog.get_logger(__name__)

Intent = Literal["data", "strategy", "hybrid"]


class ChatRecommender:
    """Generate grounded follow-up questions without another LLM call."""

    @staticmethod
    def _parse_schema(schema_inventory: str) -> dict[str, list[str]]:
        """Parses schema inventory string into {table_name: [columns]}."""
        catalog: dict[str, list[str]] = {}
        for line in (schema_inventory or "").splitlines():
            line = line.strip()
            if not line.startswith("-") or ":" not in line:
                continue
            table_part, cols_part = line[1:].split(":", 1)
            tbl = table_part.strip().split(".")[-1]  # Extract table name without schema prefix
            cols = [c.strip() for c in cols_part.split(",") if c.strip()]
            if tbl and cols:
                catalog[tbl] = cols
        return catalog

    @staticmethod
    def _deduplicate(
        questions: Sequence[str],
        current_question: str,
        limit: int,
    ) -> list[str]:
        current = current_question.strip().casefold()
        seen: set[str] = set()
        result: list[str] = []
        for q in questions:
            clean = " ".join(q.split()).strip()
            clean = re.sub(r"^[-*\d.)\s]+", "", clean).strip()  # Strip list prefixes
            key = clean.casefold()
            if not clean or key == current or key in seen:
                continue
            # Ensure it ends with a question mark
            if not clean.endswith("?"):
                clean += "?"
            seen.add(key)
            result.append(clean)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _deterministic_schema_fallback(
        cls,
        *,
        catalog: dict[str, list[str]],
        columns: Sequence[str],
        question: str,
        limit: int = 4,
    ) -> list[str]:
        """Dynamically builds follow-ups using real physical columns and tables."""
        candidates: list[str] = []
        # Find primary table or queried columns
        queried_cols = set(columns)
        all_tables = list(catalog.keys())
        # Identify numeric metrics, dimensions, and date columns in the active schema
        metric_cols: list[str] = []
        dim_cols: list[str] = []
        date_cols: list[str] = []
        for tbl, cols in catalog.items():
            for c in cols:
                cl = c.lower()
                if any(k in cl for k in ("date", "time", "created_at", "month", "year")):
                    date_cols.append(c)
                elif any(k in cl for k in ("amount", "score", "total", "balance", "arr", "mrr", "cost", "price", "count", "days")):
                    metric_cols.append(c)
                elif any(k in cl for k in ("name", "type", "status", "tier", "stage", "department", "region", "priority")):
                    dim_cols.append(c)
        # 1. Dimension breakdown (using REAL dimension columns in the DB)
        if dim_cols and metric_cols:
            dim = dim_cols[0].replace("_", " ")
            metric = metric_cols[0].replace("_", " ")
            candidates.append(f"How does {metric} break down by {dim}?")
        # 2. Related table exploration
        if len(all_tables) > 1:
            for tbl in all_tables[:2]:
                tbl_clean = tbl.replace("_", " ")
                candidates.append(f"Can you show related details from {tbl_clean}?")
        # 3. Time trend (only if a real date column exists in the database)
        if date_cols and metric_cols:
            metric = metric_cols[0].replace("_", " ")
            candidates.append(f"How has {metric} trended over time?")
        # 4. Status / Priority breakdown
        status_col = next((c for c in dim_cols if "status" in c.lower() or "priority" in c.lower()), None)
        if status_col:
            candidates.append(f"What is the distribution across {status_col.replace('_', ' ')}?")
        return candidates

    @classmethod
    def recommend(
        cls,
        *,
        intent: Intent,
        question: str,
        columns: Sequence[str] = (),
        schema_inventory: str = "",
        limit: int = 4,
        sql: str = "",
        domain_context: str = "",
        **kwargs: Any,
    ) -> list[str]:
        """Recommends follow-up questions tailored to any connected database."""
        catalog = cls._parse_schema(schema_inventory)
        # 1. Attempt LLM-grounded recommendation
        try:
            from app.chat_sql.llm_provider import LLMProvider
            prompt = f"""You are a data analyst. Generate exactly 3-4 natural, highly relevant follow-up questions that a business user would ask next.
CRITICAL RULES:
1. Every question MUST be strictly answerable using ONLY tables and columns listed in DATABASE SCHEMA.
2. NEVER mention tables, entities, or columns that do not exist in the schema below (e.g. do not ask about 'products' or 'categories' if they do not exist).
3. Ground the questions in the user's specific question and the query results.
4. Output JSON only: {{"follow_ups": ["question 1", "question 2", "question 3"]}}
DATABASE SCHEMA:
{schema_inventory[:4000]}
USER QUESTION:
{question}
EXECUTED SQL OR RESULT COLUMNS:
{sql or ', '.join(columns)}
"""
            raw_output = LLMProvider().generate_text(prompt=prompt, max_tokens=150)
            match = re.search(r"\{.*\}", raw_output, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                llm_candidates = data.get("follow_ups", [])
                if isinstance(llm_candidates, list) and len(llm_candidates) > 0:
                    cleaned = cls._deduplicate(llm_candidates, current_question=question, limit=limit)
                    if cleaned:
                        return cleaned
        except Exception as exc:
            log.warning("llm_follow_up_recommendation_fallback", error=str(exc))
        # 2. Fallback to schema-grounded deterministic engine
        candidates = cls._deterministic_schema_fallback(
            catalog=catalog,
            columns=columns,
            question=question,
            limit=limit,
        )
        return cls._deduplicate(
            candidates,
            current_question=question,
            limit=max(1, min(limit, 6)),
        )