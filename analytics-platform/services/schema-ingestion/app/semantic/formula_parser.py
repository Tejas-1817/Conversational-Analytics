import ast
from typing import List, Set

class InvalidExpressionError(Exception):
    pass

class CircularDependencyError(Exception):
    pass


class MetricFormulaParser:
    """Parses and validates business formulas like 'Gross Revenue - Discount'."""
    
    ALLOWED_NODES = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.operator,
        ast.unaryop,
        ast.Num,
        ast.Name,
        ast.Load,
        ast.Constant
    )

    @classmethod
    def extract_metrics(cls, expression: str) -> List[str]:
        """Returns a list of metric names referenced in the expression."""
        if not expression or not expression.strip():
            return []
            
        try:
            # We use ast.parse to safely parse the math expression.
            # mode='eval' ensures it's a single expression, not arbitrary statements.
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise InvalidExpressionError(f"Syntax error in formula: {str(e)}")

        metrics = set()
        for node in ast.walk(tree):
            if not isinstance(node, cls.ALLOWED_NODES):
                raise InvalidExpressionError(f"Unsupported formula component: {type(node).__name__}. Only basic arithmetic is allowed.")
            
            if isinstance(node, ast.Name):
                metrics.add(node.id)

        return list(metrics)

    @classmethod
    def validate_no_cycles(cls, metric_name: str, expression: str, all_metrics: dict[str, str]):
        """
        Validates that adding/updating this expression won't create a circular dependency.
        all_metrics maps metric_name -> expression.
        """
        # Build adjacency list
        graph = {}
        for m_name, expr in all_metrics.items():
            if expr:
                graph[m_name] = cls.extract_metrics(expr)
            else:
                graph[m_name] = []
                
        # Inject the proposed expression
        graph[metric_name] = cls.extract_metrics(expression)

        # Detect cycle using DFS
        visited = set()
        path = set()

        def dfs(node: str) -> bool:
            if node in path:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            path.add(node)
            
            for neighbor in graph.get(node, []):
                if dfs(neighbor):
                    return True
                    
            path.remove(node)
            return False

        if dfs(metric_name):
            raise CircularDependencyError(f"Circular dependency detected involving metric '{metric_name}'")

