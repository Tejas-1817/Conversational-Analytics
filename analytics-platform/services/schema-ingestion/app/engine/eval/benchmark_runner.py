import time
import uuid
import statistics
from typing import List
from sqlalchemy.orm import Session
import structlog

from app.schemas_benchmark import BenchmarkTestCase, TestCaseResult, BenchmarkReport
from app.engine.query_intelligence_service import QueryIntelligenceService
from app.engine.retrieval_service import RetrievalService, RetrievalHits

logger = structlog.get_logger(__name__)

class BenchmarkRunnerService:
    @staticmethod
    def run_benchmark(db: Session, tenant_id: uuid.UUID, test_cases: List[BenchmarkTestCase]) -> BenchmarkReport:
        results = []
        failure_reasons = {}

        def record_failure(reason: str):
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        for tc in test_cases:
            start_time = time.time()
            
            # Semantic Retrieval Accuracy Evaluation
            retrieval_start = time.time()
            hits: RetrievalHits = RetrievalService.retrieve(tc.question, tenant_id, db)
            
            # Calculate Precision and Recall on retrieved semantic objects
            retrieved_names = [m.business_name.lower() for m, _ in hits.metrics] + \
                              [d.business_name.lower() for d, _ in hits.dimensions]
            
            expected_lower = [e.lower() for e in tc.expected_semantic_objects]
            
            true_positives = sum(1 for e in expected_lower if e in retrieved_names)
            precision = true_positives / len(retrieved_names) if retrieved_names else 0.0
            recall = true_positives / len(expected_lower) if expected_lower else 1.0

            # Run full generation pipeline
            gen_result = QueryIntelligenceService.answer_question(db, tenant_id, tc.question)
            
            total_latency_ms = int((time.time() - start_time) * 1000)
            
            sql = gen_result.get("sql")
            explanation = gen_result.get("explanation", "")
            confidence = gen_result.get("confidence", 0.0)
            execution_meta = gen_result.get("execution_metadata")
            referenced = [r.lower() for r in gen_result.get("referenced_semantics", [])]
            
            # Safety and generation evaluation
            sql_is_valid = bool(sql)
            safety_violation_detected = "rejected for safety reasons" in explanation
            
            # Hallucination check (if it used objects not expected or retrieved)
            # In a real scenario, we might check if referenced objects are exactly the ones passed in context
            hallucination_detected = False
            for ref in referenced:
                if ref not in retrieved_names:
                    hallucination_detected = True
            
            execution_success = False
            returned_columns = []
            schema_matched = False
            exec_error = None
            
            if sql and execution_meta:
                execution_success = True
                returned_columns = execution_meta.get("columns", [])
                
                if tc.expected_columns:
                    expected_cols_lower = [c.lower() for c in tc.expected_columns]
                    actual_cols_lower = [c.lower() for c in returned_columns]
                    schema_matched = all(c in actual_cols_lower for c in expected_cols_lower)
                else:
                    schema_matched = True # trivially match if not specified
            elif sql and not execution_meta:
                # execution failed
                exec_error = "Execution failed or blocked"
            
            # Calibration error: absolute difference between confidence and actual success (1 or 0)
            actual_success = 1.0 if (sql_is_valid and execution_success and not hallucination_detected and schema_matched) else 0.0
            calibration_error = abs(confidence - actual_success)
            
            if actual_success == 0.0:
                if safety_violation_detected: record_failure("Safety Violation")
                elif hallucination_detected: record_failure("Hallucination")
                elif not sql_is_valid: record_failure("No SQL Generated")
                elif not execution_success: record_failure("Execution Failed")
                elif not schema_matched: record_failure("Schema Mismatch")
                else: record_failure("Unknown Error")

            res = TestCaseResult(
                test_case_id=tc.id,
                question=tc.question,
                domain=tc.domain,
                retrieval_precision=precision,
                retrieval_recall=recall,
                generated_sql=sql,
                sql_is_valid=sql_is_valid,
                hallucination_detected=hallucination_detected,
                safety_violation_detected=safety_violation_detected,
                execution_success=execution_success,
                execution_error=exec_error,
                returned_columns=returned_columns,
                schema_matched=schema_matched,
                reported_confidence=confidence,
                calibration_error=calibration_error,
                total_latency_ms=total_latency_ms
            )
            results.append(res)
            
        # Aggregate
        total = len(results)
        if total == 0:
            return BenchmarkReport(
                run_id=str(uuid.uuid4()),
                total_test_cases=0,
                success_rate=0.0,
                avg_retrieval_precision=0.0,
                avg_retrieval_recall=0.0,
                hallucination_rate=0.0,
                safety_violation_rate=0.0,
                sql_validity_rate=0.0,
                execution_success_rate=0.0,
                schema_match_rate=0.0,
                avg_calibration_error=0.0,
                avg_latency_ms=0,
                p95_latency_ms=0,
                failure_reasons={},
                results=[]
            )
            
        success_count = sum(1 for r in results if r.sql_is_valid and r.execution_success and r.schema_matched and not r.hallucination_detected)
        
        latencies = [r.total_latency_ms for r in results]
        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        if p95_idx >= len(latencies):
            p95_idx = len(latencies) - 1
            
        report = BenchmarkReport(
            run_id=str(uuid.uuid4()),
            total_test_cases=total,
            success_rate=success_count / total,
            avg_retrieval_precision=sum(r.retrieval_precision for r in results) / total,
            avg_retrieval_recall=sum(r.retrieval_recall for r in results) / total,
            hallucination_rate=sum(1 for r in results if r.hallucination_detected) / total,
            safety_violation_rate=sum(1 for r in results if r.safety_violation_detected) / total,
            sql_validity_rate=sum(1 for r in results if r.sql_is_valid) / total,
            execution_success_rate=sum(1 for r in results if r.execution_success) / total,
            schema_match_rate=sum(1 for r in results if r.schema_matched) / total,
            avg_calibration_error=sum(r.calibration_error for r in results) / total,
            avg_latency_ms=int(statistics.mean(latencies)),
            p95_latency_ms=latencies[p95_idx],
            failure_reasons=failure_reasons,
            results=results
        )
        return report
