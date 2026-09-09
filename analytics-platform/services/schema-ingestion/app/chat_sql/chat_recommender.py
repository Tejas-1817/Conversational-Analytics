"""Deterministic follow-up recommendations for analytics chat."""

from __future__ import annotations

from typing import Literal, Sequence


Intent = Literal["data", "strategy", "hybrid"]


class ChatRecommender:
    """Generate grounded follow-up questions without another LLM call."""

    @staticmethod
    def _deduplicate(
        questions: Sequence[str],
        current_question: str,
        limit: int,
    ) -> list[str]:
        current = current_question.strip().casefold()
        seen: set[str] = set()
        result: list[str] = []

        for question in questions:
            clean = " ".join(question.split()).strip()
            key = clean.casefold()

            if not clean or key == current or key in seen:
                continue

            seen.add(key)
            result.append(clean)

            if len(result) >= limit:
                break

        return result

    @classmethod
    def recommend(
        cls,
        *,
        intent: Intent,
        question: str,
        columns: Sequence[str],
        schema_inventory: str,
        limit: int = 4,
    ) -> list[str]:
        searchable = (
            " ".join(columns) + " " + schema_inventory
        ).casefold()

        candidates: list[str] = []

        if "product" in searchable and "revenue" in searchable:
            candidates.append(
                "Which products generate the highest and lowest revenue?"
            )

        if "product" in searchable and "margin" in searchable:
            candidates.append(
                "Which products have high revenue but low profit margin?"
            )

        if "customer" in searchable and "segment" in searchable:
            candidates.append(
                "How does performance differ across customer segments?"
            )

        if any(
            term in searchable
            for term in ("date", "month", "year", "created_at")
        ):
            candidates.append(
                "How has this metric changed month by month?"
            )

        if "inventory" in searchable:
            candidates.append(
                "Which products have low stock or unusually high inventory?"
            )

        if "return" in searchable and "product" in searchable:
            candidates.append(
                "Which products have the highest return rates?"
            )

        if intent in {"strategy", "hybrid"}:
            candidates.extend(
                [
                    "Which measurable KPI should we analyze first?",
                    "What additional data is required to validate these recommendations?",
                ]
            )
        else:
            candidates.extend(
                [
                    "Can you break this result down by category?",
                    "Can you compare this with the previous period?",
                ]
            )

        return cls._deduplicate(
            candidates,
            current_question=question,
            limit=max(1, min(limit, 6)),
        )