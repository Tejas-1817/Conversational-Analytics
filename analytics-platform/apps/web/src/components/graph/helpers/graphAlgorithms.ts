import type { DomainGraphNode, DomainGraphEdge } from '../types';

export interface JoinStep {
  fromTableId: string;
  fromTableName: string;
  fromColumnName: string;
  toTableId: string;
  toTableName: string;
  toColumnName: string;
  cardinality: string;
  status: string;
  confidence: number;
  edgeId: string;
}

export interface ShortestPathResult {
  found: boolean;
  sourceTableId: string;
  targetTableId: string;
  pathTableIds: string[];
  pathEdgeIds: string[];
  steps: JoinStep[];
  sqlJoinSnippet: string;
  errorMessage?: string;
}

/**
 * Finds the shortest join path between two tables using Breadth-First Search (BFS).
 * Returns ordered steps and a formatted SQL JOIN snippet.
 */
export function findShortestJoinPath(
  nodes: DomainGraphNode[],
  edges: DomainGraphEdge[],
  sourceTableId: string,
  targetTableId: string
): ShortestPathResult {
  const nodesMap = new Map<string, DomainGraphNode>();
  nodes.forEach((n) => nodesMap.set(n.id, n));

  const sourceNode = nodesMap.get(sourceTableId);
  const targetNode = nodesMap.get(targetTableId);

  if (!sourceNode || !targetNode) {
    return {
      found: false,
      sourceTableId,
      targetTableId,
      pathTableIds: [],
      pathEdgeIds: [],
      steps: [],
      sqlJoinSnippet: '',
      errorMessage: 'Source or target table not found in domain.',
    };
  }

  if (sourceTableId === targetTableId) {
    return {
      found: true,
      sourceTableId,
      targetTableId,
      pathTableIds: [sourceTableId],
      pathEdgeIds: [],
      steps: [],
      sqlJoinSnippet: `-- Same table selected: ${sourceNode.table_name}\nSELECT * FROM ${sourceNode.table_name};`,
    };
  }

  // Build bidirectional adjacency list: tableId -> Array<{ neighborId: string, edge: DomainGraphEdge, isOutbound: boolean }>
  interface AdjEdge {
    neighborId: string;
    edge: DomainGraphEdge;
    isOutbound: boolean;
  }
  const adj = new Map<string, AdjEdge[]>();

  edges.forEach((e) => {
    if (!adj.has(e.source_table_id)) adj.set(e.source_table_id, []);
    if (!adj.has(e.target_table_id)) adj.set(e.target_table_id, []);

    adj.get(e.source_table_id)!.push({
      neighborId: e.target_table_id,
      edge: e,
      isOutbound: true,
    });
    adj.get(e.target_table_id)!.push({
      neighborId: e.source_table_id,
      edge: e,
      isOutbound: false,
    });
  });

  // BFS Queue: store current tableId and path taken so far
  interface QueueItem {
    tableId: string;
    path: Array<{ tableId: string; edge: DomainGraphEdge; isOutbound: boolean }>;
  }

  const queue: QueueItem[] = [{ tableId: sourceTableId, path: [] }];
  const visited = new Set<string>([sourceTableId]);

  let finalPath: Array<{ tableId: string; edge: DomainGraphEdge; isOutbound: boolean }> | null = null;

  while (queue.length > 0) {
    const current = queue.shift()!;

    if (current.tableId === targetTableId) {
      finalPath = current.path;
      break;
    }

    const neighbors = adj.get(current.tableId) || [];
    for (const n of neighbors) {
      if (!visited.has(n.neighborId)) {
        visited.add(n.neighborId);
        queue.push({
          tableId: n.neighborId,
          path: [...current.path, { tableId: n.neighborId, edge: n.edge, isOutbound: n.isOutbound }],
        });
      }
    }
  }

  if (!finalPath) {
    return {
      found: false,
      sourceTableId,
      targetTableId,
      pathTableIds: [],
      pathEdgeIds: [],
      steps: [],
      sqlJoinSnippet: '',
      errorMessage: `No join path connects "${sourceNode.table_name}" to "${targetNode.table_name}".`,
    };
  }

  // Reconstruct path tables and steps
  const pathTableIds: string[] = [sourceTableId];
  const pathEdgeIds: string[] = [];
  const steps: JoinStep[] = [];

  let prevTableId = sourceTableId;
  for (const seg of finalPath) {
    pathTableIds.push(seg.tableId);
    pathEdgeIds.push(seg.edge.id);

    const prevNode = nodesMap.get(prevTableId);
    const currNode = nodesMap.get(seg.tableId);

    // Depending on edge direction, assign from/to columns accurately
    let fromCol = seg.edge.source_column_name;
    let toCol = seg.edge.target_column_name;
    if (!seg.isOutbound) {
      // Traversed reverse edge
      fromCol = seg.edge.target_column_name;
      toCol = seg.edge.source_column_name;
    }

    steps.push({
      fromTableId: prevTableId,
      fromTableName: prevNode?.table_name || prevTableId,
      fromColumnName: fromCol,
      toTableId: seg.tableId,
      toTableName: currNode?.table_name || seg.tableId,
      toColumnName: toCol,
      cardinality: seg.edge.cardinality || 'many_to_one',
      status: seg.edge.status,
      confidence: seg.edge.confidence,
      edgeId: seg.edge.id,
    });

    prevTableId = seg.tableId;
  }

  // Generate formatted SQL JOIN snippet
  const sqlLines: string[] = [
    `-- Shortest Join Route: ${sourceNode.table_name} ➔ ${targetNode.table_name} (${steps.length} hops)`,
    `SELECT *`,
    `FROM ${sourceNode.table_name}`,
  ];

  for (const step of steps) {
    sqlLines.push(
      `JOIN ${step.toTableName} ON ${step.fromTableName}.${step.fromColumnName} = ${step.toTableName}.${step.toColumnName}`
    );
  }
  sqlLines.push(`;`);

  return {
    found: true,
    sourceTableId,
    targetTableId,
    pathTableIds,
    pathEdgeIds,
    steps,
    sqlJoinSnippet: sqlLines.join('\n'),
  };
}

/**
 * Returns neighbor table IDs connected to focalTableId within 1 or 2 hops,
 * plus the count of unrevealed connections for each neighbor.
 */
export function getFocalNeighborhood(
  edges: DomainGraphEdge[],
  focalTableId: string,
  hops: 1 | 2 = 1
): {
  visibleNodeIds: Set<string>;
  unrevealedCounts: Map<string, number>;
} {
  const directNeighbors = new Set<string>();
  const totalDegree = new Map<string, number>();

  edges.forEach((e) => {
    totalDegree.set(e.source_table_id, (totalDegree.get(e.source_table_id) || 0) + 1);
    totalDegree.set(e.target_table_id, (totalDegree.get(e.target_table_id) || 0) + 1);

    if (e.source_table_id === focalTableId) directNeighbors.add(e.target_table_id);
    if (e.target_table_id === focalTableId) directNeighbors.add(e.source_table_id);
  });

  const visibleNodeIds = new Set<string>([focalTableId, ...directNeighbors]);

  if (hops === 2) {
    const secondHop = new Set<string>();
    edges.forEach((e) => {
      if (directNeighbors.has(e.source_table_id) && e.target_table_id !== focalTableId) {
        secondHop.add(e.target_table_id);
      }
      if (directNeighbors.has(e.target_table_id) && e.source_table_id !== focalTableId) {
        secondHop.add(e.source_table_id);
      }
    });
    secondHop.forEach((id) => visibleNodeIds.add(id));
  }

  // Calculate unrevealed connection count for each visible node
  const unrevealedCounts = new Map<string, number>();
  visibleNodeIds.forEach((id) => {
    let connectionsInView = 0;
    edges.forEach((e) => {
      if (
        (e.source_table_id === id && visibleNodeIds.has(e.target_table_id)) ||
        (e.target_table_id === id && visibleNodeIds.has(e.source_table_id))
      ) {
        connectionsInView++;
      }
    });
    const total = totalDegree.get(id) || 0;
    unrevealedCounts.set(id, Math.max(0, total - connectionsInView));
  });

  return { visibleNodeIds, unrevealedCounts };
}
