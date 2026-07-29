import uuid
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TableMeta, ColumnMeta, SemanticMetric, SemanticDimension, SemanticKPI, BusinessGlossary, SemanticJoin
from app.schemas_semantic_ai import AITableEnrichmentSchema
from app.schemas_validation import ValidationStatus, ValidationEvidence, ValidationResult, ValidationReport
from app.semantic.formula_parser import MetricFormulaParser, InvalidExpressionError, CircularDependencyError

class SemanticValidationService:
    
    @staticmethod
    def validate_metric(db: Session, tenant_id: uuid.UUID, metric_name: str, expression: str,
                        is_calculated: bool, source_table_id: uuid.UUID = None, source_column_id: uuid.UUID = None):
        """Validates manual metric creation/update logic."""
        if not is_calculated:
            if not source_table_id or not source_column_id:
                raise HTTPException(status_code=400, detail="Base metrics require source_table_id and source_column_id")
            table = db.scalar(select(TableMeta).where(TableMeta.id == source_table_id, TableMeta.is_active == True))
            if not table:
                raise HTTPException(status_code=400, detail=f"Source table {source_table_id} not found or inactive")
            column = db.scalar(select(ColumnMeta).where(ColumnMeta.id == source_column_id, ColumnMeta.is_active == True))
            if not column:
                raise HTTPException(status_code=400, detail=f"Source column {source_column_id} not found or inactive")
        if is_calculated:
            if not expression:
                raise HTTPException(status_code=400, detail="Calculated metrics require an expression")
            try:
                deps = MetricFormulaParser.extract_metrics(expression)
                existing_metrics = db.execute(
                    select(SemanticMetric.name, SemanticMetric.expression)
                    .where(SemanticMetric.tenant_id == tenant_id)
                ).all()
                all_metrics = {m.name: m.expression for m in existing_metrics}
                for dep in deps:
                    if dep not in all_metrics and dep != metric_name:
                        raise HTTPException(status_code=400, detail=f"Referenced metric '{dep}' does not exist")
                MetricFormulaParser.validate_no_cycles(metric_name, expression, all_metrics)
            except (InvalidExpressionError, CircularDependencyError) as e:
                raise HTTPException(status_code=400, detail=str(e))

    @classmethod
    def validate_table_enrichment(
        cls, db: Session, table: TableMeta, enrichment: AITableEnrichmentSchema
    ) -> Tuple[AITableEnrichmentSchema, ValidationReport]:
        """
        Validates all semantic objects generated for a table.
        Returns the enrichment object and the generated report.
        """
        report = ValidationReport()
        col_map = {c.column_name.lower(): c for c in (table.columns or [])}
        
        dim_results, dim_valid = cls._validate_dimensions(table, col_map, enrichment.dimensions)
        meas_results, meas_valid = cls._validate_measures(table, col_map, enrichment.measures)
        kpi_results, kpi_valid = cls._validate_kpis(db, table, enrichment.kpis)
        rel_results, rel_valid = cls._validate_relationships(db, table, col_map, enrichment.relationships)
        gloss_results, gloss_valid = cls._validate_glossary(table, enrichment.glossary_terms)

        all_results = dim_results + meas_results + kpi_results + rel_results + gloss_results
        report.results = all_results
        report.total_objects = len(all_results)
        
        for r in all_results:
            if r.status == ValidationStatus.VALIDATED:
                report.validated_objects += 1
            elif r.status == ValidationStatus.NEEDS_REVIEW:
                report.needs_review_objects += 1
            elif r.status == ValidationStatus.AMBIGUOUS:
                report.ambiguous_objects += 1
            elif r.status == ValidationStatus.INSUFFICIENT_EVIDENCE:
                report.failed_validations += 1

        return enrichment, report

    @classmethod
    def _validate_dimensions(cls, table: TableMeta, col_map: dict, dimensions: list) -> Tuple[List[ValidationResult], list]:
        results = []
        valid_dims = []
        seen = set()
        
        for dim in dimensions:
            evidence = []
            status = ValidationStatus.VALIDATED
            
            if dim.business_name.lower() in seen:
                evidence.append(ValidationEvidence(passed=False, message="Duplicate dimension business name"))
                status = ValidationStatus.NEEDS_REVIEW
            else:
                seen.add(dim.business_name.lower())

            col = col_map.get(dim.source_column_name.lower())
            if not col:
                evidence.append(ValidationEvidence(passed=False, message=f"Source column '{dim.source_column_name}' does not exist on table '{table.table_name}'"))
                status = ValidationStatus.INSUFFICIENT_EVIDENCE
            else:
                evidence.append(ValidationEvidence(passed=True, message=f"Column '{col.column_name}' exists (Type: {col.data_type})"))
                
                if dim.is_time_dimension:
                    if 'timestamp' in col.data_type.lower() or 'date' in col.data_type.lower() or 'time' in col.data_type.lower():
                        evidence.append(ValidationEvidence(passed=True, message="Datatype supports temporal semantics"))
                    else:
                        evidence.append(ValidationEvidence(passed=False, message=f"Datatype '{col.data_type}' may not fully support temporal semantics"))
                        status = ValidationStatus.NEEDS_REVIEW

            results.append(ValidationResult(
                object_type="dimension",
                object_name=dim.business_name,
                status=status,
                evidence=evidence
            ))
            if status == ValidationStatus.VALIDATED:
                valid_dims.append(dim)
                
        return results, valid_dims

    @classmethod
    def _validate_measures(cls, table: TableMeta, col_map: dict, measures: list) -> Tuple[List[ValidationResult], list]:
        results = []
        valid_meas = []
        seen = set()
        
        valid_aggs = {"SUM", "AVG", "COUNT", "COUNT_DISTINCT", "MIN", "MAX", "CUSTOM"}

        for meas in measures:
            evidence = []
            status = ValidationStatus.VALIDATED
            
            if meas.business_name.lower() in seen:
                evidence.append(ValidationEvidence(passed=False, message="Duplicate measure business name"))
                status = ValidationStatus.NEEDS_REVIEW
            else:
                seen.add(meas.business_name.lower())
                
            col = col_map.get(meas.source_column_name.lower())
            if not col:
                evidence.append(ValidationEvidence(passed=False, message=f"Source column '{meas.source_column_name}' does not exist on table '{table.table_name}'"))
                status = ValidationStatus.INSUFFICIENT_EVIDENCE
            else:
                evidence.append(ValidationEvidence(passed=True, message=f"Column '{col.column_name}' exists"))
                
                raw_agg = (meas.aggregation_type or "COUNT").upper()
                if raw_agg not in valid_aggs:
                    evidence.append(ValidationEvidence(passed=False, message=f"Aggregation '{raw_agg}' is not supported"))
                    status = ValidationStatus.NEEDS_REVIEW
                else:
                    evidence.append(ValidationEvidence(passed=True, message=f"Aggregation '{raw_agg}' is valid"))
                    
                if raw_agg in ["SUM", "AVG"]:
                    if not any(t in col.data_type.lower() for t in ["int", "float", "numeric", "decimal", "double", "real"]):
                        evidence.append(ValidationEvidence(passed=False, message=f"Aggregation '{raw_agg}' may be incompatible with datatype '{col.data_type}'"))
                        if status == ValidationStatus.VALIDATED:
                            status = ValidationStatus.AMBIGUOUS

            results.append(ValidationResult(
                object_type="measure",
                object_name=meas.business_name,
                status=status,
                evidence=evidence
            ))
            if status == ValidationStatus.VALIDATED:
                valid_meas.append(meas)
                
        return results, valid_meas

    @classmethod
    def _validate_kpis(cls, db: Session, table: TableMeta, kpis: list) -> Tuple[List[ValidationResult], list]:
        results = []
        valid_kpis = []
        seen = set()

        for kpi in kpis:
            evidence = []
            status = ValidationStatus.VALIDATED
            
            if kpi.business_name.lower() in seen:
                evidence.append(ValidationEvidence(passed=False, message="Duplicate KPI business name"))
                status = ValidationStatus.NEEDS_REVIEW
            else:
                seen.add(kpi.business_name.lower())
                
            if not kpi.expression:
                evidence.append(ValidationEvidence(passed=False, message="KPI lacks an expression formula"))
                status = ValidationStatus.INSUFFICIENT_EVIDENCE
            else:
                evidence.append(ValidationEvidence(passed=True, message="KPI formula exists"))
                try:
                    deps = MetricFormulaParser.extract_metrics(kpi.expression)
                    evidence.append(ValidationEvidence(passed=True, message=f"Formula parses correctly, extracted deps: {deps}"))
                except InvalidExpressionError as e:
                    evidence.append(ValidationEvidence(passed=False, message=f"Formula parsing failed: {e}"))
                    status = ValidationStatus.INSUFFICIENT_EVIDENCE

            results.append(ValidationResult(
                object_type="kpi",
                object_name=kpi.business_name,
                status=status,
                evidence=evidence
            ))
            if status == ValidationStatus.VALIDATED:
                valid_kpis.append(kpi)
                
        return results, valid_kpis

    @classmethod
    def _validate_relationships(cls, db: Session, table: TableMeta, col_map: dict, relationships: list) -> Tuple[List[ValidationResult], list]:
        results = []
        valid_rels = []
        seen = set()

        for rel in relationships:
            evidence = []
            status = ValidationStatus.VALIDATED
            
            rel_sig = f"{rel.from_column_name}->{rel.to_table_name}.{rel.to_column_name}".lower()
            if rel_sig in seen:
                evidence.append(ValidationEvidence(passed=False, message="Duplicate relationship"))
                status = ValidationStatus.NEEDS_REVIEW
            else:
                seen.add(rel_sig)
                
            local_col = col_map.get(rel.from_column_name.lower())
            if not local_col:
                evidence.append(ValidationEvidence(passed=False, message=f"Source column '{rel.from_column_name}' does not exist"))
                status = ValidationStatus.INSUFFICIENT_EVIDENCE
            else:
                evidence.append(ValidationEvidence(passed=True, message=f"Source column '{rel.from_column_name}' exists"))
                
                target_table = db.query(TableMeta).filter(
                    TableMeta.source_id == table.source_id, 
                    TableMeta.table_name.ilike(rel.to_table_name)
                ).first()
                
                if not target_table:
                    evidence.append(ValidationEvidence(passed=False, message=f"Target table '{rel.to_table_name}' does not exist in schema"))
                    status = ValidationStatus.INSUFFICIENT_EVIDENCE
                else:
                    evidence.append(ValidationEvidence(passed=True, message=f"Target table '{rel.to_table_name}' exists"))
                    
                    target_col = db.query(ColumnMeta).filter(
                        ColumnMeta.table_id == target_table.id,
                        ColumnMeta.column_name.ilike(rel.to_column_name)
                    ).first()
                    
                    if not target_col:
                        evidence.append(ValidationEvidence(passed=False, message=f"Target column '{rel.to_column_name}' does not exist in table '{rel.to_table_name}'"))
                        status = ValidationStatus.INSUFFICIENT_EVIDENCE
                    else:
                        evidence.append(ValidationEvidence(passed=True, message=f"Target column '{rel.to_column_name}' exists"))
                        
                        if local_col.data_type != target_col.data_type:
                            evidence.append(ValidationEvidence(passed=False, message=f"Datatype mismatch: {local_col.data_type} != {target_col.data_type}"))
                            if status == ValidationStatus.VALIDATED:
                                status = ValidationStatus.AMBIGUOUS

            results.append(ValidationResult(
                object_type="relationship",
                object_name=rel_sig,
                status=status,
                evidence=evidence
            ))
            if status == ValidationStatus.VALIDATED:
                valid_rels.append(rel)
                
        return results, valid_rels
        
    @classmethod
    def _validate_glossary(cls, table: TableMeta, glossary_terms: list) -> Tuple[List[ValidationResult], list]:
        results = []
        valid_terms = []
        seen = set()

        for term in glossary_terms:
            evidence = []
            status = ValidationStatus.VALIDATED
            
            if term.term.lower() in seen:
                evidence.append(ValidationEvidence(passed=False, message="Duplicate glossary term"))
                status = ValidationStatus.NEEDS_REVIEW
            else:
                seen.add(term.term.lower())
                
            if not term.business_definition:
                evidence.append(ValidationEvidence(passed=False, message="Empty business definition"))
                status = ValidationStatus.NEEDS_REVIEW
            else:
                evidence.append(ValidationEvidence(passed=True, message="Business definition exists"))
                
            results.append(ValidationResult(
                object_type="glossary_term",
                object_name=term.term,
                status=status,
                evidence=evidence
            ))
            if status == ValidationStatus.VALIDATED:
                valid_terms.append(term)
                
        return results, valid_terms
