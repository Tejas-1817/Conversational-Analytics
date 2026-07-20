import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas_engine import NLUIntent
from app.engine.resolver_service import ResolverService
from app.engine.planner_service import PlannerService
from app.engine.compiler_service import CompilerService
from sqlalchemy.orm import Session
from app.db import session_scope
from app.config import get_settings

def run_pipeline(intent_json: str):
    import uuid
    with session_scope() as db:
        try:
            tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
            intent = NLUIntent.model_validate_json(intent_json)
            
            # 1. Resolve
            resolved = ResolverService.resolve_entities(db, tenant_id, intent)
            print("Resolved Context:")
            print("Metric:", resolved.metric.business_name if resolved.metric else None)
            print("Dimensions:", [d.business_name for d in resolved.dimensions] if resolved.dimensions else [])
            print("Time Granularity:", intent.time_granularity)
            
            # 2. Plan
            plan = PlannerService.generate_plan(db, intent, resolved)
            print("Execution Plan:")
            print(f" - metrics: {plan.metric_ids}")
            print(f" - dimensions: {plan.dimension_ids}")
            print(f" - filters: {plan.filters}")
            print(f" - time_granularity: {plan.time_granularity}")
                
            # 3. Compile
            compiled = CompilerService.compile_plan(db, tenant_id, plan)
            print("Generated SQL:")
            print(compiled.sql)
            print("Params:", compiled.params)
            print("-" * 40)
        except Exception as e:
            traceback.print_exc()

if __name__ == "__main__":
    q4_intent = '{"intent":"aggregate","metric":"Revenue","dimensions":[],"filters":[],"time_granularity":"month"}'
    q19_intent = '{"intent":"aggregate","metric":"Total income","dimensions":[],"filters":[{"field":"Region","operator":"IN","value":["all"]}]}'
    
    print("Testing Q4...")
    run_pipeline(q4_intent)
        
    print("Testing Q19...")
    run_pipeline(q19_intent)
