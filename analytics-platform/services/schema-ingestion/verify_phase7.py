import os
import sys
import uuid
import time
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.db import session_scope
from app.models import User, BenchmarkCollection, EvaluationDataset, EvaluationRun, EvaluationResult
from app.engine.eval.runner import BenchmarkRunner
from app.security.auth import create_access_token

load_dotenv()

def get_db():
    with session_scope() as db:
        yield db

def setup_test_data(db: Session):
    from app.engine.nlu_service import NLUService
    from app.engine.planner_service import PlannerService
    from app.engine.executor_service import ExecutorService
    from app.engine.nl_generator import NLGenerator
    from app.engine.executor_service import ExecutorResult
    from app.schemas_engine import NLUIntent, StructuredQueryPlan
    
    def mock_parse_intent(question):
        if "totally_wrong_table" in question:
            return NLUIntent(intent="aggregate", metric="revenue", dimensions=["region"])
        return NLUIntent(intent="aggregate", metric="revenue", dimensions=[])
        
    def mock_generate_plan(intent, resolution):
        if "region" in intent.dimensions:
            return StructuredQueryPlan(metric_id=uuid.uuid4(), dimension_ids=[uuid.uuid4()])
        return StructuredQueryPlan(metric_id=uuid.uuid4(), dimension_ids=[])
        
    def mock_execute(db, compiled):
        return ExecutorResult(columns=["revenue"], rows=[{"revenue": 1000}], execution_time_ms=10)
        
    def mock_generate_explanation(question, plan, result):
        return "Here is the revenue data."
        
    from app.engine.eval.nl_evaluator import NLEvaluator
    from app.engine.validation_service import ValidationService
    
    def mock_nl_evaluator(question, generated_answer, execution_result):
        return 1.0
        
    def mock_validate_plan(db, tenant_id, plan):
        pass
        
    from app.engine.compiler_service import CompilerService, CompiledQuery
    def mock_compile_plan(db, tenant_id, plan):
        if plan.dimension_ids:
            return CompiledQuery(sql="SELECT SUM(revenue), region FROM totally_wrong_table GROUP BY wrong_col", params={})
        return CompiledQuery(sql="SELECT SUM(revenue) FROM sales", params={})
        
    from app.engine.resolver_service import ResolverService
    def mock_resolve_entities(db, tenant_id, intent):
        return None
        
    from app.engine.chart_recommender import ChartRecommender
    def mock_recommend_chart(plan):
        if plan.dimension_ids:
            return "bar_chart"
        return "kpi_card"
        
    NLUService.parse_intent = staticmethod(mock_parse_intent)
    ResolverService.resolve_entities = staticmethod(mock_resolve_entities)
    PlannerService.generate_plan = staticmethod(mock_generate_plan)
    ValidationService.validate_plan = staticmethod(mock_validate_plan)
    CompilerService.compile_plan = staticmethod(mock_compile_plan)
    ExecutorService.execute = staticmethod(mock_execute)
    ChartRecommender.recommend = staticmethod(mock_recommend_chart)
    NLGenerator.generate_explanation = staticmethod(mock_generate_explanation)
    NLEvaluator.evaluate = staticmethod(mock_nl_evaluator)

    # Find or create a user and tenant
    user = db.query(User).filter(User.email == "admin@company.com").first()
    if not user:
        print("Admin user not found. Run bootstrap first.")
        sys.exit(1)
        
    tenant_id = user.tenant_id
    
    # Create collection
    collection = db.query(BenchmarkCollection).filter(
        BenchmarkCollection.tenant_id == tenant_id,
        BenchmarkCollection.name == "Verification Benchmark Suite"
    ).first()
    
    if not collection:
        collection = BenchmarkCollection(
            tenant_id=tenant_id,
            name="Verification Benchmark Suite",
            description="Phase 7 Test Data",
            domain="Finance",
            created_by="admin@company.com"
        )
        db.add(collection)
        db.commit()
        db.refresh(collection)
        print(f"Created Collection ID: {collection.id}")
    else:
        print(f"Reusing Collection ID: {collection.id}")
    
    # Create a passing dataset
    ds1 = EvaluationDataset(
        collection_id=collection.id,
        question="What is the revenue?",
        expected_intent={"intent": "aggregate", "metric": "revenue", "dimensions": []},
        expected_plan={"metric_id": str(uuid.uuid4()), "dimension_ids": []},
        expected_sql="SELECT SUM(revenue) FROM sales",
        expected_chart="kpi_card",
        expected_result={"columns": ["revenue"], "rows": [{"revenue": 1000}]}
    )
    
    # Create a failing dataset (bad SQL expectation)
    ds2 = EvaluationDataset(
        collection_id=collection.id,
        question="Show me revenue by region",
        expected_intent={"intent": "aggregate", "metric": "revenue", "dimensions": ["region"]},
        expected_plan={"metric_id": str(uuid.uuid4()), "dimension_ids": [str(uuid.uuid4())]},
        expected_sql="SELECT SUM(revenue), region FROM totally_wrong_table GROUP BY wrong_col",
        expected_chart="bar_chart",
        expected_result={"columns": ["region", "revenue"], "rows": [{"region": "NA", "revenue": 500}]}
    )
    
    if db.query(EvaluationDataset).filter(EvaluationDataset.collection_id == collection.id).count() == 0:
        db.add_all([ds1, ds2])
        db.commit()
    
    return user, collection

def execute_run(db: Session, user: User, collection: BenchmarkCollection):
    print("\n--- Executing Benchmark Run ---")
    run = BenchmarkRunner.run_collection(db, user.tenant_id, collection.id, user.email)
    
    print(f"Run ID: {run.id}")
    print(f"Overall Score: {run.overall_score}")
    print(f"Pass Rate: {run.pass_rate}")
    
    for res in run.results:
        print(f"\nDataset ID: {res.dataset_id}")
        print(f"Intent Score: {res.intent_score}")
        print(f"Plan Score: {res.plan_score}")
        print(f"SQL Score: {res.sql_score}")
        print(f"Result Score: {res.result_score}")
        print(f"Chart Score: {res.chart_score}")
        print(f"Reliability Score: {res.reliability_score}")
        print(f"Passed: {res.is_pass}")
        if not res.is_pass:
            print(f"Failure Reasons: {res.failure_reasons}")
            
    return run

if __name__ == "__main__":
    db = next(get_db())
    user, collection = setup_test_data(db)
    
    # Run 1
    print("\n=== RUN A ===")
    run_a = execute_run(db, user, collection)
    
    # Run 2 (simulate same run)
    print("\n=== RUN B ===")
    run_b = execute_run(db, user, collection)
    
    print("\n=== API TEST ===")
    token = create_access_token(str(user.id), user.role, str(user.tenant_id))
    headers = {"Authorization": f"Bearer {token}"}
    
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    
    res = client.get("/eval/collections", headers=headers)
    print(f"GET /eval/collections -> {res.status_code}")
    if res.status_code == 200:
        print(res.json())
    
    res2 = client.get(f"/eval/runs/{run_b.id}", headers=headers)
    print(f"GET /eval/runs/ID -> {res2.status_code}")
    if res2.status_code == 200:
        print(f"Run Status: {res2.json()['status']}")
    
    # Let's print out the SQL evaluator behavior explicitly
    print("\n=== SQL EVALUATOR EXAMPLES ===")
    from app.engine.eval.sql_evaluator import SQLEvaluator
    score_pass = SQLEvaluator.evaluate(
        "SELECT SUM(revenue) FROM sales GROUP BY region", 
        "SELECT SUM(revenue) \n FROM sales \n GROUP BY region"
    )
    score_fail = SQLEvaluator.evaluate(
        "SELECT SUM(revenue) FROM sales GROUP BY region", 
        "SELECT SUM(revenue) FROM totally_wrong_table"
    )
    print(f"SQL PASS Score: {score_pass} (Expected 1.0)")
    print(f"SQL FAIL Score: {score_fail} (Expected < 1.0)")
