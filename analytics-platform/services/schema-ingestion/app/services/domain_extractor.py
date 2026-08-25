"""LLM business term extraction service for Domain Knowledge Base.

Extracts domain-specific terms, definitions, logic, and synonyms from raw document text.
"""
from __future__ import annotations

import json
import structlog
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.chat_sql.llm_provider import LLMProvider

log = structlog.get_logger(__name__)


class ExtractedTerm(BaseModel):
    term: str = Field(description="The domain business term or acronym.")
    definition: str = Field(description="Clear business definition or calculation rule.")
    synonyms: List[str] = Field(default_factory=list, description="Alternative names or synonyms.")
    category: str = Field(default="business_term", description="Category e.g. metric, dimension, rule, acronym.")


def extract_domain_terms(text_sample: str, domain_name: str) -> List[ExtractedTerm]:
    """Use LLM capabilities to identify domain-specific business terms from raw text."""
    if not text_sample or not text_sample.strip():
        return []

    prompt = f"""You are an expert NLP data analyst building a Domain Business Glossary for the business domain '{domain_name}'.

Analyze the raw document text below and identify all domain-specific business terms, metrics, KPIs, business rules, acronyms, and formulas.

RAW DOCUMENT TEXT:
{text_sample[:8000]}

Return a strict JSON array of objects with keys:
- "term": Name of the business term or acronym
- "definition": Precise business definition or calculation logic
- "synonyms": List of alternative names/synonyms (e.g. ["revenue", "turnover"])
- "category": One of "metric", "dimension", "business_rule", "acronym", "general"

Return ONLY valid JSON array. No markdown, no explanations outside JSON."""

    try:
        # provider = LLMProvider().generate_sql(prompt)
        # response = provider.generate_chat_completion(
        #     messages=[{"role": "user", "content": prompt}],
        #     temperature=0.1
        # )
        content = LLMProvider().generate_sql(prompt).strip()
        
        # Strip markdown code blocks if wrapped
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data = json.loads(content)
        terms = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "term" in item and "definition" in item:
                    terms.append(ExtractedTerm(
                        term=str(item.get("term", "")).strip(),
                        definition=str(item.get("definition", "")).strip(),
                        synonyms=[str(s).strip() for s in item.get("synonyms", []) if s],
                        category=str(item.get("category", "general")).strip()
                    ))
        return terms
    except Exception as exc:
        log.warning("domain_term_extraction_failed", domain=domain_name, error=str(exc))
        return []
