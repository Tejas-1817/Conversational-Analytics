import asyncio
import uuid
import sys
import traceback
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import get_session
from app.models import Conversation, ConversationMessage, Tenant, User
from app.schemas_engine import ChatRequest
from app.config import get_settings

# Let's bypass the API and call the services directly to see where it fails.
from app.engine.router_service import RouterService
from app.engine.nlu_service import NLUService
from app.engine.retrieval_service import RetrievalService
from app.engine.resolver_service import ResolverService
from app.engine.planner_service import PlannerService
from app.engine.compiler_service import CompilerService
from app.engine.executor_service import ExecutorService
from app.engine.nl_generator import NLGenerator

def run_debug():
    settings = get_settings()
    from app.db import get_engine
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = db.scalar(select(User).limit(1))
    if not user:
        print("No user found.")
        return
    tenant_id = user.tenant_id

    query = "Show total revenue by region"
    print(f"Testing query: {query}")

    try:
        from app.engine.context_manager import ConversationContext
        context = ConversationContext(chat_history="[]", last_intent=None, last_plan=None)

        # Route Intent
        route_result = RouterService.classify_intent(query)
        print(f"Router output: {route_result}")

        # NLU
        intent = NLUService.parse_intent(query, context)
        print(f"NLU Intent: {intent}")

        # Retrieval
        rag_hits = RetrievalService.retrieve(query, tenant_id, db)
        print(f"RAG Hits metrics: {len(rag_hits.metrics)}")

        # Resolver
        resolution = ResolverService.resolve_entities(db, tenant_id, intent, rag_hits)
        print(f"Resolution: metric={resolution.metric}, kpi={resolution.kpi}")

        if not resolution.metric and not resolution.kpi:
            print("No metric or KPI resolved.")
            return

        # Planner
        plan = PlannerService.generate_plan(db, intent, resolution, rag_hits)
        print(f"Plan: {plan}")

        # Compiler
        compiled = CompilerService.compile_plan(db, tenant_id, plan)
        print(f"Compiled SQL: {compiled.sql}")

        # Executor
        result = ExecutorService.execute(db, compiled)
        print(f"Execution result rows: {len(result.rows)}")

    except Exception as e:
        print("\n=== EXCEPTION CAUGHT ===")
        traceback.print_exc()

if __name__ == "__main__":
    run_debug()
