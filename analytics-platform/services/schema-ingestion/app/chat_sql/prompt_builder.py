"""Prompt Builder.

Constructs strict system instructions and appends loaded static schema text
and natural language question for Text-to-SQL generation matching main.py.
"""


class PromptBuilder:
    """Constructs Text-to-SQL system prompts with strict anti-hallucination guardrails matching main.py."""

    @classmethod
    def build_prompt(cls, question: str, schema_text: str, database_name: str = "analytics_db") -> str:
        """Constructs system prompt directly from static schema text matching main.py."""
        return f"""You are an expert PostgreSQL SQL Generator.

Below is the database schema.

==================================================
{schema_text}
==================================================

Instructions:
1. Generate ONLY a valid PostgreSQL SQL query.
2. Never explain the SQL.
3. Never use markdown.
4. Never wrap SQL inside ```sql.
5. Never hallucinate tables.
6. Never hallucinate columns.
7. Use ONLY tables and columns present in the schema.
8. Use proper JOINs whenever required.
9. If multiple SQL queries are possible, generate the simplest one.
10. If the question cannot be answered using the schema, reply exactly:

I cannot generate a SQL query because the required tables or columns do not exist in the provided schema.

USER QUESTION:
{question}

GENERATED SQL:
"""

