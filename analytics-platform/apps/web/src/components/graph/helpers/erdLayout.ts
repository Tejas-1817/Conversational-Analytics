import type { DomainGraphNode, DomainGraphEdge } from '../types';

export interface NodePosition {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OrthogonalPathResult {
  path: string;
  labelX: number;
  labelY: number;
}

export interface ViewportFit {
  pan: { x: number; y: number };
  zoom: number;
}

export interface LayoutOptions {
  cardWidth?: number;
  maxPerCol?: number;
  colGap?: number;
  rowGap?: number;
  layerSpacing?: number;
  startX?: number;
  startY?: number;
}

/**
 * Computes a cycle-proof hierarchical layout (Sugiyama-style) for database ERD tables.
 *
 * Guarantees:
 * 1. ZERO horizontal card overlap: Each layer and sub-column gets an explicit, accumulated X coordinate.
 * 2. ZERO vertical card overlap: Cards are stacked using cumulative dynamic heights plus row gaps.
 * 3. Cycle safety: Three-color DFS extracts back-edges into a true DAG before topological ranking.
 * 4. Crossing minimization: Nodes within layers are sorted using barycentric neighbor heuristics.
 * 5. Scale resilience: Disconnected components and deep schemas are placed cleanly without artificial layer capping.
 */
export function computeHierarchicalLayout(
  nodes: DomainGraphNode[],
  edges: DomainGraphEdge[],
  getNodeHeight: (node: DomainGraphNode) => number,
  options?: LayoutOptions
): Map<string, NodePosition> {
  const CARD_WIDTH = options?.cardWidth ?? 240;
  const MAX_PER_COL = options?.maxPerCol ?? 4;
  const COL_GAP = options?.colGap ?? 80;
  const ROW_GAP = options?.rowGap ?? 32;
  const LAYER_SPACING = options?.layerSpacing ?? 30;
  const START_X = options?.startX ?? 60;
  const START_Y = options?.startY ?? 50;

  const positions = new Map<string, NodePosition>();
  if (!nodes || nodes.length === 0) return positions;

  const nodeIds = new Set(nodes.map((n) => n.id));
  const validEdges = edges.filter(
    (e) =>
      e.source_table_id !== e.target_table_id &&
      nodeIds.has(e.source_table_id) &&
      nodeIds.has(e.target_table_id)
  );

  // 1. Build adjacency list for cycle detection
  const adj = new Map<string, string[]>();
  nodes.forEach((n) => adj.set(n.id, []));
  validEdges.forEach((e) => {
    const list = adj.get(e.source_table_id);
    if (list && !list.includes(e.target_table_id)) {
      list.push(e.target_table_id);
    }
  });

  // 2. DFS Three-Color Cycle Detection to extract clean DAG
  // 0: unvisited, 1: visiting (in current stack), 2: visited
  const state = new Map<string, number>();
  const dagAdj = new Map<string, string[]>();
  nodes.forEach((n) => {
    state.set(n.id, 0);
    dagAdj.set(n.id, []);
  });

  function dfs(u: string) {
    state.set(u, 1);
    const neighbors = adj.get(u) || [];
    for (const v of neighbors) {
      if (state.get(v) === 1) {
        // Back-edge forming a cycle: exclude from DAG ranking
        continue;
      }
      dagAdj.get(u)!.push(v);
      if (state.get(v) === 0) {
        dfs(v);
      }
    }
    state.set(u, 2);
  }

  for (const n of nodes) {
    if (state.get(n.id) === 0) {
      dfs(n.id);
    }
  }

  // 3. Compute topological ranks on the DAG
  const inDegree = new Map<string, number>();
  nodes.forEach((n) => inDegree.set(n.id, 0));
  dagAdj.forEach((targets) => {
    targets.forEach((v) => {
      inDegree.set(v, (inDegree.get(v) || 0) + 1);
    });
  });

  const queue: string[] = [];
  const layers = new Map<string, number>();

  nodes.forEach((n) => {
    if ((inDegree.get(n.id) || 0) === 0) {
      layers.set(n.id, 0);
      queue.push(n.id);
    }
  });

  while (queue.length > 0) {
    const u = queue.shift()!;
    const uLayer = layers.get(u) || 0;
    const targets = dagAdj.get(u) || [];

    for (const v of targets) {
      const currentVLayer = layers.get(v) ?? -1;
      if (uLayer + 1 > currentVLayer) {
        layers.set(v, uLayer + 1);
      }
      const remaining = (inDegree.get(v) || 1) - 1;
      inDegree.set(v, remaining);
      if (remaining <= 0) {
        queue.push(v);
      }
    }
  }

  // Fallback for any unvisited nodes
  nodes.forEach((n) => {
    if (!layers.has(n.id)) {
      layers.set(n.id, 0);
    }
  });

  // 4. Group nodes by layer
  const layerBuckets = new Map<number, DomainGraphNode[]>();
  nodes.forEach((n) => {
    const l = layers.get(n.id) || 0;
    if (!layerBuckets.has(l)) layerBuckets.set(l, []);
    layerBuckets.get(l)!.push(n);
  });

  const sortedLayerIndices = Array.from(layerBuckets.keys()).sort((a, b) => a - b);

  // 5. Barycentric Crossing Reduction
  const connectedMap = new Map<string, string[]>();
  nodes.forEach((n) => connectedMap.set(n.id, []));
  validEdges.forEach((e) => {
    connectedMap.get(e.source_table_id)?.push(e.target_table_id);
    connectedMap.get(e.target_table_id)?.push(e.source_table_id);
  });

  const nodeRankOrder = new Map<string, number>();
  (layerBuckets.get(sortedLayerIndices[0]) || []).forEach((n, idx) => {
    nodeRankOrder.set(n.id, idx);
  });

  for (let i = 1; i < sortedLayerIndices.length; i++) {
    const layerIdx = sortedLayerIndices[i];
    const bucket = layerBuckets.get(layerIdx) || [];

    const withBarycenter = bucket.map((node) => {
      const neighbors = connectedMap.get(node.id) || [];
      const neighborRanks = neighbors
        .map((nbrId) => nodeRankOrder.get(nbrId))
        .filter((r): r is number => r !== undefined);

      const barycenter =
        neighborRanks.length > 0
          ? neighborRanks.reduce((sum, r) => sum + r, 0) / neighborRanks.length
          : Infinity;

      return { node, barycenter };
    });

    withBarycenter.sort((a, b) => a.barycenter - b.barycenter);
    const sortedNodes = withBarycenter.map((item) => item.node);
    layerBuckets.set(layerIdx, sortedNodes);

    sortedNodes.forEach((node, idx) => {
      nodeRankOrder.set(node.id, idx);
    });
  }

  // 6. Coordinate Computation with Strict Non-Overlapping Sub-Columns
  let currentX = START_X;

  sortedLayerIndices.forEach((layerIdx) => {
    const bucketNodes = layerBuckets.get(layerIdx) || [];
    const numSubCols = Math.max(1, Math.ceil(bucketNodes.length / MAX_PER_COL));

    for (let subColIdx = 0; subColIdx < numSubCols; subColIdx++) {
      const colNodes = bucketNodes.slice(
        subColIdx * MAX_PER_COL,
        (subColIdx + 1) * MAX_PER_COL
      );

      let currentY = START_Y;

      colNodes.forEach((node) => {
        const h = getNodeHeight(node);
        positions.set(node.id, {
          x: currentX,
          y: currentY,
          width: CARD_WIDTH,
          height: h,
        });
        currentY += h + ROW_GAP;
      });

      // Advance X for this sub-column
      currentX += CARD_WIDTH + COL_GAP;
    }

    // Additional spacing between different relationship layers
    currentX += LAYER_SPACING;
  });

  return positions;
}

/**
 * Computes an orthogonal SVG routing path between source and target cards.
 *
 * Supports:
 * - Clean forward routes through distributed horizontal-vertical-horizontal channels.
 * - Direct backward routes from source left to target right without cutting across cards.
 * - Dedicated side loops for self-referencing relationships.
 * - Channel spreading to prevent parallel edges between the same table pair from overlapping.
 */
export function computeOrthogonalPath(
  src: NodePosition,
  tgt: NodePosition,
  edgeIndex: number = 0,
  totalEdgesBetweenPair: number = 1
): OrthogonalPathResult {
  const r = 8; // Corner fillet radius

  // Self-referencing relationship (e.g. employee reports_to employee)
  if (src.x === tgt.x && src.y === tgt.y) {
    const x0 = src.x + src.width;
    const y0 = src.y + 24;
    const loopW = 28 + (edgeIndex % 3) * 8;
    const loopH = 34 + (edgeIndex % 3) * 8;

    const path = [
      `M ${x0} ${y0}`,
      `H ${x0 + loopW}`,
      `V ${y0 + loopH}`,
      `H ${x0}`,
    ].join(' ');

    return {
      path,
      labelX: x0 + loopW + 4,
      labelY: y0 + loopH / 2,
    };
  }

  // Channel offset to prevent parallel links from overlapping
  const rawSpread =
    totalEdgesBetweenPair > 1
      ? (edgeIndex - (totalEdgesBetweenPair - 1) / 2) * 14
      : 0;
  const maxSpread = Math.max(4, Math.min(src.height, tgt.height) / 2 - 10); 
  const spreadOffset = Math.max(-maxSpread, Math.min(maxSpread, rawSpread));

  // 1. Forward route: Source is to the left of Target
  if (tgt.x >= src.x + src.width + 16) {
    const x1 = src.x + src.width;
    const y1 = src.y + src.height / 2 + spreadOffset;
    const x2 = tgt.x;
    const y2 = tgt.y + tgt.height / 2 + spreadOffset;

    const midX = (x1 + x2) / 2 + spreadOffset;
    const isLevel = Math.abs(y2 - y1) < 4;

    if (isLevel) {
      return {
        path: `M ${x1} ${y1} L ${x2} ${y2}`,
        labelX: (x1 + x2) / 2,
        labelY: y1,
      };
    }

    const goesDown = y2 > y1;
    const fillet1 = goesDown
      ? `Q ${midX} ${y1} ${midX} ${y1 + r}`
      : `Q ${midX} ${y1} ${midX} ${y1 - r}`;
    const fillet2 = goesDown
      ? `Q ${midX} ${y2} ${midX + r} ${y2}`
      : `Q ${midX} ${y2} ${midX + r} ${y2}`;

    const d = [
      `M ${x1} ${y1}`,
      `H ${midX - r}`,
      fillet1,
      `V ${goesDown ? y2 - r : y2 + r}`,
      fillet2,
      `H ${x2}`,
    ].join(' ');

    return {
      path: d,
      labelX: midX,
      labelY: (y1 + y2) / 2,
    };
  }

  // 2. Backward route: Target is to the left of Source
  if (src.x >= tgt.x + tgt.width + 16) {
    const x1 = src.x;
    const y1 = src.y + src.height / 2 + spreadOffset;
    const x2 = tgt.x + tgt.width;
    const y2 = tgt.y + tgt.height / 2 + spreadOffset;

    const midX = (x1 + x2) / 2 + spreadOffset;
    const isLevel = Math.abs(y2 - y1) < 4;

    if (isLevel) {
      return {
        path: `M ${x1} ${y1} L ${x2} ${y2}`,
        labelX: (x1 + x2) / 2,
        labelY: y1,
      };
    }

    const goesDown = y2 > y1;
    const fillet1 = goesDown
      ? `Q ${midX} ${y1} ${midX} ${y1 + r}`
      : `Q ${midX} ${y1} ${midX} ${y1 - r}`;
    const fillet2 = goesDown
      ? `Q ${midX} ${y2} ${midX - r} ${y2}`
      : `Q ${midX} ${y2} ${midX - r} ${y2}`;

    const d = [
      `M ${x1} ${y1}`,
      `H ${midX + r}`,
      fillet1,
      `V ${goesDown ? y2 - r : y2 + r}`,
      fillet2,
      `H ${x2}`,
    ].join(' ');

    return {
      path: d,
      labelX: midX,
      labelY: (y1 + y2) / 2,
    };
  }

  // 3. Same column or overlapping cards: route cleanly around right-side gutter
  const rightEdge = Math.max(src.x + src.width, tgt.x + tgt.width);
  const y1 = src.y + src.height / 2;
  const y2 = tgt.y + tgt.height / 2;
  const gutterX = rightEdge + 28 + Math.abs(spreadOffset) + (edgeIndex % 3) * 12;

  const goesDown = y2 > y1;
  const fillet1 = goesDown
    ? `Q ${gutterX} ${y1} ${gutterX} ${y1 + r}`
    : `Q ${gutterX} ${y1} ${gutterX} ${y1 - r}`;
  const fillet2 = goesDown
    ? `Q ${gutterX} ${y2} ${gutterX - r} ${y2}`
    : `Q ${gutterX} ${y2} ${gutterX - r} ${y2}`;

  const d = [
    `M ${src.x + src.width} ${y1}`,
    `H ${gutterX - r}`,
    fillet1,
    `V ${goesDown ? y2 - r : y2 + r}`,
    fillet2,
    `H ${tgt.x + tgt.width}`,
  ].join(' ');

  return {
    path: d,
    labelX: gutterX + 16,
    labelY: (y1 + y2) / 2,
  };
}

/**
 * Calculates pan coordinates and zoom scale to fit the entire node layout
 * neatly inside the container viewport with comfortable margins.
 */
export function calculateFitToView(
  positions: Map<string, NodePosition>,
  containerWidth: number,
  containerHeight: number,
  padding: number = 60
): ViewportFit {
  if (!positions || positions.size === 0) {
    return { pan: { x: 60, y: 40 }, zoom: 1 };
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  positions.forEach((pos) => {
    minX = Math.min(minX, pos.x);
    maxX = Math.max(maxX, pos.x + pos.width);
    minY = Math.min(minY, pos.y);
    maxY = Math.max(maxY, pos.y + pos.height);
  });

  const graphW = Math.max(10, maxX - minX);
  const graphH = Math.max(10, maxY - minY);

  const availW = Math.max(100, containerWidth - padding * 2);
  const availH = Math.max(100, containerHeight - padding * 2);

  const scaleX = availW / graphW;
  const scaleY = availH / graphH;

  // Clamp zoom between 0.35 and 1.2
  const fitZoom = Math.min(1.2, Math.max(0.35, Math.min(scaleX, scaleY)));

  const graphCenterX = minX + graphW / 2;
  const graphCenterY = minY + graphH / 2;

  const panX = containerWidth / 2 - graphCenterX * fitZoom;
  const panY = containerHeight / 2 - graphCenterY * fitZoom;

  return {
    pan: { x: Math.round(panX), y: Math.round(panY) },
    zoom: Number(fitZoom.toFixed(2)),
  };
}
