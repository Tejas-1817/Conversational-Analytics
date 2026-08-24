import structlog

log = structlog.get_logger(__name__)


class PromptBuilder:
    """Constructs Text-to-SQL system prompts with generic database-agnostic semantic mapping rules."""

    @classmethod
    def build_prompt(
        cls,
        question: str,
        schema_text: str,
        database_name: str = "analytics_db",
        schema_version: int = 1,
        domain_context: str | None = None,
    ) -> str:
        """Constructs database-agnostic Text-to-SQL prompt with generic semantic schema mapping directives."""
        domain_block = ""
        if domain_context and domain_context.strip():
            domain_block = f"""\n==================================================
SELECTED BUSINESS DOMAIN CONTEXT & KNOWLEDGE BASE:
{domain_context.strip()}
==================================================\n"""

        prompt_str = f"""You are an expert PostgreSQL query generator.

Below is the database schema.

==================================================
Database Name: {database_name}

{schema_text}
==================================================
{domain_block}
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

5. ALIASING CONVENTION (CRITICAL FOR CHART LABELS):
   - Every aggregate expression (SUM, COUNT, AVG, MIN, MAX) and every computed expression MUST be given a clear, descriptive snake_case alias via AS (e.g. SUM(amount) AS total_revenue, not SUM(amount)).
   - Never leave an aggregate or computed column unaliased.

6. RANKING / TOP-N PATTERN:
   - If the question asks for a "top N", "highest", "lowest", "best", or "worst" result, the query MUST include both an ORDER BY on the relevant metric and a LIMIT clause matching the requested count (or a reasonable default of 10 if unspecified).

7. PREFER HUMAN-READABLE COLUMNS OVER RAW IDS:
   - When both a surrogate id column (e.g. ending in _id) and a human-readable name/label column exist for the same entity, prefer selecting the human-readable column for display purposes.
   - Only include the id column if the question explicitly asks for it.

8. PERCENTAGE / SHARE NAMING CONVENTION:
   - When a query computes a proportion or share, alias it using a name containing "percentage", "share", "pct", or "rate" (e.g. AS revenue_share_pct) so it is recognized as a percentage value by the visualization engine.

--- FEW-SHOT EXAMPLES ---

Q: What is the total revenue?
SQL: SELECT SUM(amount) AS total_revenue FROM orders;

Q: Show me the top 10 customers by total spending.
SQL: SELECT c.name AS customer_name, SUM(o.amount) AS total_spending FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name ORDER BY total_spending DESC LIMIT 10;

Q: What is the revenue share by product category?
SQL: SELECT category_name, ROUND(SUM(amount) * 100.0 / SUM(SUM(amount)) OVER (), 2) AS revenue_share_pct FROM products p JOIN order_items oi ON p.id = oi.product_id GROUP BY category_name ORDER BY revenue_share_pct DESC;

Q: Show monthly revenue trend for the past year.
SQL: SELECT DATE_TRUNC('month', order_date) AS order_month, SUM(amount) AS total_revenue FROM orders WHERE order_date >= NOW() - INTERVAL '1 year' GROUP BY order_month ORDER BY order_month ASC;

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

