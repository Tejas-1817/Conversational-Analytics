/**
 * Graph traversal utilities for ERD relationship exploration.
 * Provides BFS-based connected component discovery, degree computation,
 * and endpoint validation for schema tables.
 */

export interface RelationshipEdge {
  source_table_id: string;
  target_table_id: string;
  [key: string]: any;
}

/**
 * Traverses foreign-key relationships bidirectionally using Breadth-First Search (BFS)
 * to find all table IDs connected to the given selected table.
 *
 * Traversal properties:
 * - Bidirectional: both incoming and outgoing foreign keys count as connections.
 * - Handles cycles: nodes are tracked in a visited set to avoid infinite loops.
 * - Handles self-references: self-loops (source === target) do not cause recursion or redundant traversal.
 * - Handles duplicate edges: multiple foreign keys between the same tables are deduplicated in adjacency sets.
 * - Handles isolated tables: if the selected table has no relationships, returns a set containing only the selected table.
 * - Handles nonexistent / empty input safely: returns an empty set if selectedTableId is blank or unavailable.
 * - Time Complexity: O(V + E) where V is reachable tables and E is examined relationships.
 *
 * @param selectedTableId Stable ID of the root selected table.
 * @param edges Available relationship edges within the user's authorized schema scope.
 * @param maxHops Optional limit on traversal distance (e.g., 1 for direct 1-hop connections, undefined for all reachable).
 * @returns Set of stable table IDs reachable from selectedTableId, including selectedTableId itself.
 */
export function getConnectedTableIds(
  selectedTableId: string,
  edges: RelationshipEdge[],
  maxHops?: number
): Set<string> {
  const result = new Set<string>();

  // If no root table provided, return empty set
  if (!selectedTableId || typeof selectedTableId !== 'string' || selectedTableId.trim() === '') {
    return result;
  }

  // The root table is always included in its own component
  result.add(selectedTableId);

  // If no edges provided or hop limit is 0, return just the selected table
  if (!edges || edges.length === 0 || maxHops === 0) {
    return result;
  }

  // 1. Build bidirectional adjacency map: tableId -> Set of neighbor tableIds
  // Using a Set naturally deduplicates multi-column / composite / repeated foreign keys
  const adjacency = new Map<string, Set<string>>();

  for (const edge of edges) {
    const src = edge?.source_table_id;
    const tgt = edge?.target_table_id;

    // Safety checks for malformed edges
    if (!src || !tgt) continue;

    // Skip self-referencing links from adjacency expansion (already includes selectedTableId)
    if (src === tgt) continue;

    if (!adjacency.has(src)) adjacency.set(src, new Set());
    if (!adjacency.has(tgt)) adjacency.set(tgt, new Set());

    adjacency.get(src)!.add(tgt);
    adjacency.get(tgt)!.add(src);
  }

  // If the root table has no connections in the graph, return just {selectedTableId}
  if (!adjacency.has(selectedTableId)) {
    return result;
  }

  // 2. BFS Traversal with hop distance tracking
  // Queue item stores [tableId, hopDistance]
  const queue: Array<[string, number]> = [[selectedTableId, 0]];
  const visited = new Set<string>([selectedTableId]);

  const hopLimit = typeof maxHops === 'number' && maxHops >= 0 ? maxHops : Infinity;

  while (queue.length > 0) {
    const [currentId, currentHops] = queue.shift()!;

    // If we've reached the hop limit, do not expand neighbors further
    if (currentHops >= hopLimit) {
      continue;
    }

    const neighbors = adjacency.get(currentId);
    if (!neighbors) continue;

    for (const neighborId of neighbors) {
      if (!visited.has(neighborId)) {
        visited.add(neighborId);
        result.add(neighborId);
        queue.push([neighborId, currentHops + 1]);
      }
    }
  }

  return result;
}

/**
 * Filters relationship edges to ensure both source and target tables exist
 * in the visible node set, preventing orphan edges or broken canvas links.
 *
 * @param edges Available relationship edges.
 * @param visibleNodeIds Set of currently visible table IDs.
 * @returns Array of edges whose endpoints are both present in visibleNodeIds.
 */
export function filterEdgesByVisibleNodes<T extends RelationshipEdge>(
  edges: T[],
  visibleNodeIds: Set<string>
): T[] {
  if (!edges || edges.length === 0 || !visibleNodeIds || visibleNodeIds.size === 0) {
    return [];
  }
  return edges.filter(
    (edge) =>
      edge?.source_table_id &&
      edge?.target_table_id &&
      visibleNodeIds.has(edge.source_table_id) &&
      visibleNodeIds.has(edge.target_table_id)
  );
}

/**
 * Computes table degrees (incoming + outgoing relationships) across available edges.
 * Self-referencing relationships are counted once or twice as connections.
 *
 * @param edges Available relationship edges.
 * @returns Map from table_id to total degree count.
 */
export function computeNodeDegreeMap(
  edges: RelationshipEdge[]
): Map<string, number> {
  const degreeMap = new Map<string, number>();
  if (!edges) return degreeMap;

  for (const edge of edges) {
    const src = edge?.source_table_id;
    const tgt = edge?.target_table_id;
    if (!src || !tgt) continue;

    degreeMap.set(src, (degreeMap.get(src) || 0) + 1);
    // If not a self-loop, also increment target degree
    if (src !== tgt) {
      degreeMap.set(tgt, (degreeMap.get(tgt) || 0) + 1);
    }
  }

  return degreeMap;
}
