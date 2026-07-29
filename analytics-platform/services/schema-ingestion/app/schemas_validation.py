from typing import List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum

class ValidationStatus(str, Enum):
    VALIDATED = "VALIDATED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class ValidationEvidence(BaseModel):
    passed: bool = Field(description="Whether this specific check passed.")
    message: str = Field(description="Explanation of the evidence.")

class ValidationResult(BaseModel):
    object_type: str = Field(description="The type of semantic object, e.g., 'dimension', 'measure', 'relationship', 'kpi', 'glossary_term'.")
    object_name: str = Field(description="The business name or identifier of the object.")
    status: ValidationStatus = Field(description="The final validation status for this object.")
    evidence: List[ValidationEvidence] = Field(default_factory=list, description="A list of checks that form the evidence for the decision.")

class ValidationReport(BaseModel):
    total_objects: int = 0
    validated_objects: int = 0
    failed_validations: int = 0
    warnings: int = 0
    ambiguous_objects: int = 0
    needs_review_objects: int = 0
    results: List[ValidationResult] = Field(default_factory=list)
