"""Deterministic Join Graph Builder.

Constructs an adjacency graph of all tables and Foreign Keys, finding
cycle-free join paths across the connected database schema.
"""
from typing import Any, Dict, List, Set


class JoinGraphBuilder:
    """Pure Python graph traversal for join paths."""

    def build_join_paths(self, catalog: Dict[str, Any], max_depth: int = 3) -> List[Dict[str, Any]]:
        tables = catalog.get("tables", {})
        adj: Dict[str, List[Dict[str, str]]] = {t: [] for t in tables}

        for table_name, table_info in tables.items():
            for fk in table_info.get("foreign_keys", []):
                src_col = fk.get("constrained_columns", [""])[0] if fk.get("constrained_columns") else ""
                target_table = fk.get("referred_table", "")
                target_col = fk.get("referred_columns", [""])[0] if fk.get("referred_columns") else ""

                if target_table in adj and src_col and target_col:
                    adj[table_name].append({
                        "target": target_table,
                        "source_col": src_col,
                        "target_col": target_col
                    })
                    adj[target_table].append({
                        "target": table_name,
                        "source_col": target_col,
                        "target_col": src_col
                    })

        join_paths: List[Dict[str, Any]] = []
        visited_pairs: Set[str] = set()

        def dfs(current: str, target: str, path: List[Dict[str, str]], depth: int):
            if depth > max_depth:
                return
            if current == target:
                pair_key = f"{path[0]['source']}->{target}"
                if pair_key not in visited_pairs:
                    visited_pairs.add(pair_key)
                    join_paths.append({
                        "source_table": path[0]["source"],
                        "target_table": target,
                        "join_path_json": {"hops": path},
                        "status": "Draft"
                    })
                return

            for neighbor in adj.get(current, []):
                next_table = neighbor["target"]
                if not any(node["source"] == next_table for node in path):
                    hop = {
                        "source": current,
                        "source_col": neighbor["source_col"],
                        "target": next_table,
                        "target_col": neighbor["target_col"]
                    }
                    dfs(next_table, target, path + [hop], depth + 1)

        table_names = list(tables.keys())
        for i in range(len(table_names)):
            for j in range(i + 1, len(table_names)):
                t1, t2 = table_names[i], table_names[j]
                dfs(t1, t2, [], 0)

        return join_paths
