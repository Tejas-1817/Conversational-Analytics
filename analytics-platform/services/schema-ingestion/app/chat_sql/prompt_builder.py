"""Prompt Builder.

Constructs strict system instructions and appends active DDL, database name,
and natural language question for Text-to-SQL generation.
"""


class PromptBuilder:
    """Constructs Text-to-SQL prompts with strict anti-hallucination guardrails."""

    @staticmethod
    def format_compact_schema(catalog: dict) -> str:
        lines = []
        for t_name, t_info in catalog.items():
            cols = t_info.get("columns", {})
            if isinstance(cols, dict):
                col_str = ", ".join([f"{c} {meta.get('data_type', '')}".strip() for c, meta in cols.items()])
            elif isinstance(cols, list):
                col_str = ", ".join(cols)
            else:
                col_str = ""
            lines.append(f"TABLE {t_name} ({col_str})")
        return "\n".join(lines)

    @classmethod
    def build_prompt(cls, question: str, ddl: str, database_name: str, catalog: dict = None) -> str:
        schema_text = cls.format_compact_schema(catalog) if catalog else ddl
        return f"""You are an expert PostgreSQL SQL generator.
Database Name: {database_name}

### CONNECTED POSTGRESQL DATABASE SCHEMA:
{schema_text}

### CRITICAL RULES:
1. Generate PostgreSQL valid SQL ONLY.
2. Use ONLY the tables and columns present in the supplied schema.
3. NEVER hallucinate tables, columns, or relationships.
4. Only generate read-only SELECT queries.
5. Return raw SQL ONLY. Do NOT wrap in markdown, code fences, or explanations.
6. If the question cannot be answered using the provided schema, output EXACTLY:
   "UNANSWERABLE: Required tables or columns do not exist in the connected database schema."

### USER QUESTION:
{question}

### GENERATED SQL:
"""
