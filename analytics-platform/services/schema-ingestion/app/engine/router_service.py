from app.llm.provider import get_llm_provider
from app.schemas_engine import RouterResult
from typing import Tuple

class RouterService:
    @staticmethod
    def classify_intent(query: str) -> RouterResult:
        provider = get_llm_provider()
        prompt = f"""
You are an intelligent Intent Router for an Analytics AI Assistant.
Your job is to classify the user's message into one of the following routes:
1. "analytics": The user is asking a data question, looking for metrics, trends, or charts (e.g. "Show revenue", "Top 10 customers").
2. "greeting": The user is simply saying hello or greeting you (e.g. "Hi", "Hello", "Good morning", "Hiiii").
3. "help": The user is asking for help, what you can do, or instructions (e.g. "Help", "What can you do?", "How do I use this?").
4. "conversation": The user is engaging in general chat, small talk, expressing thanks, or asking non-analytics questions (e.g. "How are you?", "Who are you?", "Thanks", "Goodbye").
5. "unknown": If you are completely unsure or it is garbage text.

USER MESSAGE: {query}

Return a JSON object matching the RouterResult schema with 'route', 'confidence' (0.0-1.0), and 'reason'.
"""
        try:
            result = provider.generate_structured(prompt, RouterResult)
            return result
        except Exception as e:
            print(f"RouterService Exception: {e}")
            # Fallback
            return RouterResult(route="unknown", confidence=0.0, reason="Failed to classify")

    @staticmethod
    def handle_greeting() -> str:
        return (
            "Hello! I'm your AI Analytics Assistant.\n"
            "You can ask questions like:\n"
            "• Show revenue by month\n"
            "• Top 10 customers\n"
            "• Revenue by region\n"
            "• Profit by product\n\n"
            "How can I help you today?"
        )

    @staticmethod
    def handle_help() -> str:
        return (
            "**Capabilities & Help**\n"
            "I can query your business data, generate charts, and find insights.\n\n"
            "Example questions you can ask:\n"
            "• Show monthly revenue\n"
            "• Top 10 customers\n"
            "• Revenue by region\n"
            "• Sales trend\n"
            "• Profit by category\n"
            "• Compare 2025 vs 2026\n"
            "• Average order value\n\n"
            "Just type your question in plain English, and I'll generate the governed SQL and chart for you."
        )

    @staticmethod
    def handle_conversation(query: str) -> str:
        provider = get_llm_provider()
        prompt = f"""
You are an AI Analytics Assistant. A user just sent you a conversational message.
Respond politely and naturally in 1-2 sentences. Gently steer them back to asking data analytics questions if appropriate.
Do not provide a SQL query or chart.

USER: {query}
ASSISTANT:"""
        try:
            return provider.generate_text(prompt)
        except Exception:
            return "I'm here to help you analyze your data! What would you like to know?"
