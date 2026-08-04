import time
from pathlib import Path
from ollama import Client


class OllamaSQLGenerator:
    """
    Generate SQL queries from natural language using Ollama.
    """

    def __init__(
        self,
        model: str,
        ollama_url: str,
        schema_file: str,
    ):
        self.model = model
        self.client = Client(host=ollama_url)
        self.schema = self._load_schema(schema_file)

        self.system_prompt = f"""
You are an expert PostgreSQL SQL Generator.

Below is the database schema.

==================================================
{self.schema}
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
"""

    @staticmethod
    def _load_schema(schema_file: str) -> str:
        path = Path(schema_file)

        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        return path.read_text(encoding="utf-8")

    @staticmethod
    def _clean_sql(sql: str) -> str:
        """
        Remove markdown if the model accidentally returns it.
        """
        sql = sql.strip()

        sql = sql.replace("```sql", "")
        sql = sql.replace("```", "")

        return sql.strip()

    def generate_sql(self, user_prompt: str) -> str:
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        sql = response["message"]["content"]

        return self._clean_sql(sql)


def main():

    generator = OllamaSQLGenerator(
        model="gemma4:12b",          # Change model if needed
        ollama_url="http://localhost:11434",
        schema_file=r"C:\Users\Admin\Downloads\Download the text file.txt",
    )

    print("=" * 80)
    print("Natural Language ➜ SQL Generator")
    print("=" * 80)
    print("Type 'exit' anytime to quit.\n")

    while True:

        question = input("Ask Question: ").strip()

        if question.lower() in ["exit", "quit"]:
            print("\nGoodbye!")
            break

        if not question:
            continue

        start = time.time()

        try:
            sql = generator.generate_sql(question)

            elapsed = time.time() - start

            print("\nGenerated SQL")
            print("-" * 80)
            print(sql)
            print("-" * 80)
            print(f"Response Time : {elapsed:.2f} sec\n")

        except Exception as e:
            print("\nError")
            print(e)
            print()


if __name__ == "__main__":
    main()