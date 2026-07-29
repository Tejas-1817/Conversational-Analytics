from app.schemas_benchmark import BenchmarkTestCase
from typing import Dict, List

BENCHMARK_DATASETS: Dict[str, List[BenchmarkTestCase]] = {
    "HR": [
        BenchmarkTestCase(
            id="hr_001",
            question="Show employee headcount by department",
            domain="HR",
            expected_semantic_objects=["Employee Headcount", "Department"],
            expected_sql_structure=["GROUP BY", "COUNT"],
            expected_columns=["department", "headcount"]
        ),
        BenchmarkTestCase(
            id="hr_002",
            question="What is the average salary for engineers?",
            domain="HR",
            expected_semantic_objects=["Average Salary", "Job Title"],
            expected_columns=["avg_salary"]
        )
    ],
    "Sales": [
        BenchmarkTestCase(
            id="sales_001",
            question="Total revenue this quarter vs last quarter",
            domain="Sales",
            expected_semantic_objects=["Total Revenue", "Quarter"],
            expected_sql_structure=["GROUP BY"],
            expected_columns=["quarter", "total_revenue"]
        ),
        BenchmarkTestCase(
            id="sales_002",
            question="Top 5 sales reps by deal size",
            domain="Sales",
            expected_semantic_objects=["Deal Size", "Sales Rep"],
            expected_sql_structure=["ORDER BY", "DESC", "LIMIT"],
            expected_columns=["sales_rep", "deal_size"]
        )
    ],
    "Finance": [
        BenchmarkTestCase(
            id="fin_001",
            question="Net profit margin by region",
            domain="Finance",
            expected_semantic_objects=["Net Profit Margin", "Region"],
            expected_sql_structure=["GROUP BY"],
            expected_columns=["region", "net_profit_margin"]
        )
    ],
    "E-commerce": [
        BenchmarkTestCase(
            id="ecom_001",
            question="Cart abandonment rate by device type",
            domain="E-commerce",
            expected_semantic_objects=["Cart Abandonment Rate", "Device Type"],
            expected_columns=["device_type", "abandonment_rate"]
        )
    ]
}

def get_dataset(name: str) -> List[BenchmarkTestCase]:
    if name.lower() == "all":
        all_cases = []
        for cases in BENCHMARK_DATASETS.values():
            all_cases.extend(cases)
        return all_cases
    return BENCHMARK_DATASETS.get(name, [])
