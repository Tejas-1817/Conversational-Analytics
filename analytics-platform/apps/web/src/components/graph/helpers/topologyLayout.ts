import type { DomainGraphNode, DomainGraphEdge } from '../types';

/**
 * Computes deterministic concentric sunflower/radial coordinates for focal neighborhood exploration.
 * Places rootId at [0, 0], 1-hop direct neighbors evenly spaced on inner ring (radius R1),
 * and 2-hop neighbors on outer ring (radius R2) clustered near their respective 1-hop parent.
 */
export function computeDeterministicRadialPositions(
  rootId: string,
  nodes: DomainGraphNode[],
  edges: DomainGraphEdge[],
  hops: 1 | 2 = 1
): Map<string, [number, number]> {
  const positions = new Map<string, [number, number]>();
  positions.set(rootId, [0, 0]);

  // Identify direct 1-hop neighbors
  const directNeighborIds = new Set<string>();
  edges.forEach((e) => {
    if (e.source_table_id === rootId && e.target_table_id !== rootId) {
      directNeighborIds.add(e.target_table_id);
    }
    if (e.target_table_id === rootId && e.source_table_id !== rootId) {
      directNeighborIds.add(e.source_table_id);
    }
  });

  const directList = Array.from(directNeighborIds).sort((a, b) => {
    const na = nodes.find((n) => n.id === a)?.table_name || a;
    const nb = nodes.find((n) => n.id === b)?.table_name || b;
    return na.localeCompare(nb);
  });

  const K1 = directList.length;
  // Radius scaled gracefully by number of neighbors
  const R1 = Math.max(180, Math.min(290, 140 + K1 * 9));

  // Store angles for 1-hop neighbors to cluster 2-hop children near their parents
  const neighborAngles = new Map<string, number>();

  directList.forEach((id, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, K1) - Math.PI / 2;
    neighborAngles.set(id, angle);
    positions.set(id, [
      Math.round(R1 * Math.cos(angle)),
      Math.round(R1 * Math.sin(angle)),
    ]);
  });

  if (hops === 2) {
    // Collect 2-hop neighbors mapped to their 1-hop parent
    const secondHopMap = new Map<string, Set<string>>();
    const secondHopAll = new Set<string>();

    edges.forEach((e) => {
      const src1 = directNeighborIds.has(e.source_table_id);
      const tgt1 = directNeighborIds.has(e.target_table_id);

      if (src1 && e.target_table_id !== rootId && !directNeighborIds.has(e.target_table_id)) {
        if (!secondHopMap.has(e.source_table_id)) secondHopMap.set(e.source_table_id, new Set());
        secondHopMap.get(e.source_table_id)!.add(e.target_table_id);
        secondHopAll.add(e.target_table_id);
      }
      if (tgt1 && e.source_table_id !== rootId && !directNeighborIds.has(e.source_table_id)) {
        if (!secondHopMap.has(e.target_table_id)) secondHopMap.set(e.target_table_id, new Set());
        secondHopMap.get(e.target_table_id)!.add(e.source_table_id);
        secondHopAll.add(e.source_table_id);
      }
    });

    const R2 = R1 + Math.max(160, Math.min(280, 120 + secondHopAll.size * 6));

    // Place 2-hop neighbors near their parent angle
    directList.forEach((pId) => {
      const children = Array.from(secondHopMap.get(pId) || []).filter((cId) => !positions.has(cId));
      if (children.length === 0) return;

      const pAngle = neighborAngles.get(pId) || 0;
      const arcSpread = Math.min(Math.PI / 3, children.length * 0.16);
      children.forEach((cId, ci) => {
        const offset = children.length === 1 ? 0 : -arcSpread / 2 + (ci * arcSpread) / (children.length - 1);
        const cAngle = pAngle + offset;
        positions.set(cId, [
          Math.round(R2 * Math.cos(cAngle)),
          Math.round(R2 * Math.sin(cAngle)),
        ]);
      });
    });

    // Any remaining 2-hop nodes without a direct slot
    const unplaced = Array.from(secondHopAll).filter((id) => !positions.has(id));
    if (unplaced.length > 0) {
      unplaced.forEach((uId, ui) => {
        const angle = (2 * Math.PI * ui) / unplaced.length;
        positions.set(uId, [
          Math.round(R2 * Math.cos(angle)),
          Math.round(R2 * Math.sin(angle)),
        ]);
      });
    }
  }

  return positions;
}

/**
 * Truncates node table name intelligently to fit cleanly centered inside the circle.
 * Adapts to node symbol size and current camera zoom level.
 */
export function formatInsideNodeLabel(
  tableName: string,
  symbolSize: number,
  zoomLevel: number = 1
): string {
  if (!tableName) return '';
  // Effective visual pixel diameter on screen
  const effectiveSize = symbolSize * ((zoomLevel - 1) * 0.25 + 1);

  if (effectiveSize < 24) return ''; // Too small to read text cleanly

  const maxLen = effectiveSize >= 52 ? 10 : effectiveSize >= 42 ? 7 : effectiveSize >= 34 ? 5 : 4;

  if (tableName.length <= maxLen) {
    return tableName;
  }
  return tableName.slice(0, Math.max(1, maxLen - 1)) + '…';
}

/**
 * Calculates calibrated force-directed physics parameters based on graph scale and density.
 */
export function calculateDensityAwareForceParams(nodeCount: number, edgeCount: number) {
  const N = Math.max(1, nodeCount);
  const E = Math.max(0, edgeCount);
  const D = N > 1 ? (2 * E) / (N * (N - 1)) : 0;

  const minRep = Math.max(160, Math.min(450, Math.round(120 + N * 4)));
  const maxRep = Math.max(400, Math.min(1300, Math.round(320 + N * 12)));

  const minEdgeLen = Math.max(80, Math.min(130, Math.round(60 + Math.sqrt(N) * 5)));
  const maxEdgeLen = Math.max(140, Math.min(240, Math.round(95 + Math.sqrt(N) * 9)));

  const gravity = Math.max(0.006, Math.min(0.035, 0.14 / (Math.pow(N, 0.55) * (1 + 2 * D))));

  return {
    repulsion: [minRep, maxRep] as [number, number],
    edgeLength: [minEdgeLen, maxEdgeLen] as [number, number],
    gravity,
  };
}
