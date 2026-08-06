import structlog

log = structlog.get_logger(__name__)


class PromptBuilder:
    """Constructs Text-to-SQL system prompts with generic database-agnostic semantic mapping rules."""

    @classmethod
    def build_prompt(cls, question: str, schema_text: str, database_name: str = "analytics_db", schema_version: int = 1) -> str:
        """Constructs database-agnostic Text-to-SQL prompt with generic semantic schema mapping directives."""
        prompt_str = f"""You are an expert PostgreSQL query generator.

Below is the database schema.

==================================================
Database Name: {database_name}

{schema_text}
==================================================

GENERIC SCHEMA MAPPING DIRECTIVES:
1. SEMANTIC MATCHING:
   - Interpret natural-language business terms using semantic meaning rather than literal string matching.
   - Before generating SQL, identify the most semantically appropriate table and column in the provided schema.
   - Never invent tables or columns that do not exist. Only map user terminology to EXISTING schema objects.

2. COLUMN MATCHING RULES (DATABASE-AGNOSTIC):
   - If the user refers to price, cost, sale price, retail price, unit price, value, amount, or charge, locate the most appropriate numeric column representing monetary value.
   - If the user refers to date, month, year, created, registered, ordered, shipped, delivered, or updated, locate the most appropriate DATE or TIMESTAMP column.
   - If the user refers to customer type, membership, segment, tier, or class, locate the most appropriate categorical customer column.
   - If the user refers to rating, review score, stars, or feedback, locate the appropriate review or rating column.

3. TABLE DISAMBIGUATION RULES:
   - If multiple tables appear similar, inspect foreign-key relationships and column relevance.
   - Select the primary table that best satisfies the business question. Avoid joining semantically unrelated tables.

4. SQL GROUNDING & Anti-Hallucination Rules:
   - Output ONLY a single, valid PostgreSQL SELECT query — no markdown fences, no explanations, no comments.
   - Generated SQL MUST always reference physical schema table and column names only. Never generate non-existent column aliases.
   - Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or data-modifying queries.
   - If the question cannot be answered using the provided schema, reply EXACTLY:

I cannot generate a SQL query because the required tables or columns do not exist in the provided schema.

USER QUESTION:
{question}

GENERATED SQL:
"""
        prompt_length = len(prompt_str)
        estimated_tokens = prompt_length // 4
        log.info(
            "prompt_built_telemetry",
            database_name=database_name,
            schema_version=schema_version,
            prompt_length=prompt_length,
            estimated_tokens=estimated_tokens,
            question_length=len(question)
        )
        return prompt_str

