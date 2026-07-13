import pytest
from app.semantic.formula_parser import MetricFormulaParser, InvalidExpressionError, CircularDependencyError

def test_extract_metrics():
    # Valid extractions
    assert set(MetricFormulaParser.extract_metrics("Gross_Revenue - Discounts")) == {"Gross_Revenue", "Discounts"}
    assert set(MetricFormulaParser.extract_metrics("(A + B) / C * 100")) == {"A", "B", "C"}
    assert set(MetricFormulaParser.extract_metrics("Revenue")) == {"Revenue"}
    assert MetricFormulaParser.extract_metrics("") == []

def test_invalid_expressions():
    # Function calls are blocked
    with pytest.raises(InvalidExpressionError):
        MetricFormulaParser.extract_metrics("SUM(Revenue)")
        
    # Arbitrary code execution blocked
    with pytest.raises(InvalidExpressionError):
        MetricFormulaParser.extract_metrics("__import__('os').system('ls')")
        
    with pytest.raises(InvalidExpressionError):
        MetricFormulaParser.extract_metrics("A = 1")

def test_circular_dependency():
    all_metrics = {
        "Net_Revenue": "Gross_Revenue - Discounts",
        "Gross_Revenue": "Total_Sales",
    }
    
    # Valid: Adding Discounts = Promo + Refund
    MetricFormulaParser.validate_no_cycles("Discounts", "Promo + Refund", all_metrics)
    
    # Invalid: Gross Revenue depends on Net Revenue
    with pytest.raises(CircularDependencyError):
        MetricFormulaParser.validate_no_cycles("Total_Sales", "Net_Revenue + Tax", all_metrics)
        
    # Invalid: Self-referential
    with pytest.raises(CircularDependencyError):
        MetricFormulaParser.validate_no_cycles("Total_Sales", "Total_Sales + 1", all_metrics)
