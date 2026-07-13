import time
from sqlalchemy.orm import Session
import uuid

from app.schemas_eval import EvaluationDatasetOut, EvaluationResultOut
from app.engine.nlu_service import NLUService
from app.engine.resolver_service import ResolverService
from app.engine.planner_service import PlannerService
from app.engine.validation_service import ValidationService
from app.engine.compiler_service import CompilerService
from app.engine.executor_service import ExecutorService
from app.engine.chart_recommender import ChartRecommender
from app.engine.nl_generator import NLGenerator

from .intent_evaluator import IntentEvaluator
from .plan_evaluator import PlanEvaluator
from .sql_evaluator import SQLEvaluator
from .result_evaluator import ResultEvaluator
from .chart_evaluator import ChartEvaluator
from .nl_evaluator import NLEvaluator
from .scorer import ReliabilityScorer

class EvaluatorService:
    @staticmethod
    def evaluate_dataset(db: Session, tenant_id: uuid.UUID, dataset: EvaluationDatasetOut) -> EvaluationResultOut:
        start_time = time.time()
        
        gen_intent = None
        gen_plan = None
        gen_sql = None
        gen_result = None
        gen_chart = None
        gen_nl = None
        error = None
        
        try:
            # 1. NLU
            intent = NLUService.parse_intent(dataset.question)
            gen_intent = intent.model_dump(mode="json")
            
            # 2. Resolve
            resolution = ResolverService.resolve_entities(db, tenant_id, intent)
            
            # 3. Plan
            plan = PlannerService.generate_plan(intent, resolution)
            gen_plan = plan.model_dump(mode="json")
            
            # 4. Validate
            ValidationService.validate_plan(db, tenant_id, plan)
            
            # 5. Compile
            compiled = CompilerService.compile_plan(db, tenant_id, plan)
            gen_sql = compiled.sql
            
            # 6. Execute
            exec_res = ExecutorService.execute(db, compiled)
            gen_result = {"columns": exec_res.columns, "rows": exec_res.rows}
            
            # 7. Chart
            gen_chart = ChartRecommender.recommend(plan)
            
            # 8. NL
            gen_nl = NLGenerator.generate_explanation(dataset.question, plan, exec_res)
            
        except Exception as e:
            error = str(e)
            
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Calculate individual scores
        intent_score = IntentEvaluator.evaluate(dataset.expected_intent, gen_intent) if dataset.expected_intent else None
        plan_score = PlanEvaluator.evaluate(dataset.expected_plan, gen_plan) if dataset.expected_plan else None
        sql_score = SQLEvaluator.evaluate(dataset.expected_sql, gen_sql) if dataset.expected_sql else None
        result_score = ResultEvaluator.evaluate(dataset.expected_result, gen_result) if dataset.expected_result else None
        chart_score = ChartEvaluator.evaluate(dataset.expected_chart, gen_chart) if dataset.expected_chart else None
        nl_score = NLEvaluator.evaluate(dataset.question, gen_nl, gen_result) if not error else None
        
        # Final Reliability Score
        reliability_score = ReliabilityScorer.calculate_score(
            intent_score, plan_score, sql_score, result_score, chart_score, nl_score
        )
        
        is_pass = reliability_score >= 0.8
        failure_reasons = []
        if error:
            failure_reasons.append(f"Execution Error: {error}")
        if reliability_score < 0.8:
            failure_reasons.append(f"Low Reliability Score: {reliability_score:.2f}")

        return EvaluationResultOut(
            id=uuid.uuid4(),  # Temporary ID, will be overwritten by DB
            run_id=uuid.uuid4(),
            dataset_id=dataset.id,
            generated_intent=gen_intent,
            generated_plan=gen_plan,
            generated_sql=gen_sql,
            generated_result=gen_result,
            generated_chart=gen_chart,
            generated_answer=gen_nl,
            execution_time_ms=execution_time_ms,
            error=error,
            intent_score=intent_score,
            plan_score=plan_score,
            sql_score=sql_score,
            result_score=result_score,
            chart_score=chart_score,
            nl_score=nl_score,
            reliability_score=reliability_score,
            is_pass=is_pass,
            failure_reasons=failure_reasons,
            created_at=time.time() # Just a placeholder
        )
