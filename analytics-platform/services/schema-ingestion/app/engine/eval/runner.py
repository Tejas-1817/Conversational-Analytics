import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BenchmarkCollection, EvaluationDataset, EvaluationResult, EvaluationRun
from app.schemas_eval import EvaluationDatasetOut

from .evaluator import EvaluatorService


class BenchmarkRunner:
    @staticmethod
    def run_collection(db: Session, tenant_id: uuid.UUID, collection_id: uuid.UUID, triggered_by: str) -> EvaluationRun:
        # 1. Verify collection exists and belongs to tenant
        collection = db.scalar(select(BenchmarkCollection).where(
            BenchmarkCollection.id == collection_id,
            BenchmarkCollection.tenant_id == tenant_id
        ))
        if not collection:
            raise ValueError("Collection not found or access denied")

        datasets = db.scalars(select(EvaluationDataset).where(
            EvaluationDataset.collection_id == collection_id
        )).all()

        # 2. Create Run Record
        run = EvaluationRun(
            tenant_id=tenant_id,
            collection_id=collection_id,
            status="running",
            triggered_by=triggered_by
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        results = []
        total_score = 0.0
        total_latency = 0
        passes = 0
        errors = 0

        # 3. Evaluate each dataset
        for ds in datasets:
            ds_out = EvaluationDatasetOut.model_validate(ds)
            res_out = EvaluatorService.evaluate_dataset(db, tenant_id, ds_out)

            # Save Result
            res = EvaluationResult(
                run_id=run.id,
                dataset_id=ds.id,
                generated_intent=res_out.generated_intent,
                generated_plan=res_out.generated_plan,
                generated_sql=res_out.generated_sql,
                generated_result=res_out.generated_result,
                generated_chart=res_out.generated_chart,
                generated_answer=res_out.generated_answer,
                execution_time_ms=res_out.execution_time_ms,
                error=res_out.error,
                intent_score=res_out.intent_score,
                plan_score=res_out.plan_score,
                sql_score=res_out.sql_score,
                result_score=res_out.result_score,
                chart_score=res_out.chart_score,
                nl_score=res_out.nl_score,
                reliability_score=res_out.reliability_score,
                is_pass=res_out.is_pass,
                failure_reasons=res_out.failure_reasons
            )
            db.add(res)
            results.append(res_out)

            if res_out.reliability_score is not None:
                total_score += float(res_out.reliability_score)
            if res_out.execution_time_ms:
                total_latency += res_out.execution_time_ms
            if res_out.is_pass:
                passes += 1
            if res_out.error:
                errors += 1

        db.commit()

        # 4. Finalize Run
        n = len(datasets)
        run.status = "completed"
        run.finished_at = datetime.now()
        if n > 0:
            run.overall_score = total_score / n
            run.pass_rate = passes / n
            run.avg_latency_ms = total_latency // n
            run.error_rate = errors / n

        db.commit()
        db.refresh(run)
        return run
