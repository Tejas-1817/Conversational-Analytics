import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import ConversationMessage

class ConversationContext:
    def __init__(self, chat_history: str, last_intent: dict | None, last_plan: dict | None):
        self.chat_history = chat_history
        self.last_intent = last_intent
        self.last_plan = last_plan

class ConversationContextManager:
    @staticmethod
    def build_context(db: Session, conv_id: uuid.UUID) -> ConversationContext:
        """
        Retrieves the conversation history and the most recent successful logical query plan
        to provide context for follow-up questions.
        """
        messages = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv_id)
            .order_by(ConversationMessage.created_at.asc())
        ).all()

        history_lines = []
        last_intent = None
        last_plan = None
        
        for m in messages:
            if m.content:
                history_lines.append(f"{m.role}: {m.content}")
            
            # Carry forward the most recent valid intent and plan
            if m.role == "assistant":
                if m.intent:
                    last_intent = m.intent
                if m.query_plan:
                    last_plan = m.query_plan

        return ConversationContext(
            chat_history="\n".join(history_lines[-10:]), # Keep last 10 messages to avoid token bloat
            last_intent=last_intent,
            last_plan=last_plan
        )
