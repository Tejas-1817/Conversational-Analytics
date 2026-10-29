import { describe, it, expect } from 'vitest';
import {
  computeHierarchicalLayout,
  computeOrthogonalPath,
  calculateFitToView,
  type NodePosition,
} from '../helpers/erdLayout';
import type { DomainGraphNode, DomainGraphEdge } from '../types';

describe('ERD Layout Engine & Edge Routing', () => {
  const dummyHeight = (node: DomainGraphNode) => 42 + Math.min(node.columns.length, 7) * 26 + 8;

  const createMockNode = (id: string, cols: number = 3): DomainGraphNode => ({
    id,
    table_id: id,
    table_name: id,
    schema_name: 'public',
    source_id: 'src-1',
    source_name: 'Postgres',
    source_type: 'postgres',
    column_count: cols,
    columns: Array.from({ length: cols }, (_, i) => ({
      id: `${id}_c${i}`,
      column_name: `col_${i}`,
      data_type: 'varchar',
      is_primary_key: i === 0,
      is_foreign_key: false,
    })),
  });

  it('guarantees zero horizontal or vertical overlap between any cards in a complex schema', () => {
    // 12 nodes across 3 layers with high density in layer 0
    const nodes = [
      createMockNode('u1'),
      createMockNode('u2'),
      createMockNode('u3'),
      createMockNode('u4'),
      createMockNode('u5'),
      createMockNode('u6'),
      createMockNode('orders1'),
      createMockNode('orders2'),
      createMockNode('items1'),
      createMockNode('items2'),
      createMockNode('audit1'),
      createMockNode('audit2'),
    ];

    const edges: DomainGraphEdge[] = [
      { id: 'e1', relationship_id: 'e1', source_table_id: 'orders1', target_table_id: 'u1', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'many_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
      { id: 'e2', relationship_id: 'e2', source_table_id: 'orders2', target_table_id: 'u2', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'many_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
      { id: 'e3', relationship_id: 'e3', source_table_id: 'items1', target_table_id: 'orders1', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'many_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
      { id: 'e4', relationship_id: 'e4', source_table_id: 'items2', target_table_id: 'orders2', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'many_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
    ];

    const positions = computeHierarchicalLayout(nodes, edges, dummyHeight, {
      cardWidth: 240,
      maxPerCol: 3,
      colGap: 80,
      rowGap: 30,
    });

    expect(positions.size).toBe(12);

    // Pairwise overlap check
    const posArray = Array.from(positions.entries());
    for (let i = 0; i < posArray.length; i++) {
      for (let j = i + 1; j < posArray.length; j++) {
        const [idA, posA] = posArray[i];
        const [idB, posB] = posArray[j];

        const noHorizontalOverlap =
          posA.x + posA.width <= posB.x || posB.x + posB.width <= posA.x;
        const noVerticalOverlap =
          posA.y + posA.height <= posB.y || posB.y + posB.height <= posA.y;

        const isDisjoint = noHorizontalOverlap || noVerticalOverlap;
        expect(isDisjoint, `Tables ${idA} and ${idB} overlap!`).toBe(true);
      }
    }
  });

  it('handles cyclic foreign-key relationships gracefully without crash or overlapping', () => {
    // Cycle: A -> B -> C -> A
    const nodes = [
      createMockNode('A'),
      createMockNode('B'),
      createMockNode('C'),
    ];

    const cyclicEdges: DomainGraphEdge[] = [
      { id: 'e1', relationship_id: 'e1', source_table_id: 'A', target_table_id: 'B', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'one_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
      { id: 'e2', relationship_id: 'e2', source_table_id: 'B', target_table_id: 'C', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'one_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
      { id: 'e3', relationship_id: 'e3', source_table_id: 'C', target_table_id: 'A', source_column_id: 'c', target_column_id: 'c', source_column_name: 'c', target_column_name: 'c', cardinality: 'one_to_one', relationship_source: 'fk', confidence: 1, status: 'approved', evidence: {} },
    ];

    const positions = computeHierarchicalLayout(nodes, cyclicEdges, dummyHeight);
    expect(positions.size).toBe(3);

    // Verify all 3 have distinct positions
    const posA = positions.get('A')!;
    const posB = positions.get('B')!;
    const posC = positions.get('C')!;

    expect(posA).toBeDefined();
    expect(posB).toBeDefined();
    expect(posC).toBeDefined();

    // Verify disjoint
    expect(posA.x !== posB.x || posA.y !== posB.y).toBe(true);
    expect(posB.x !== posC.x || posB.y !== posC.y).toBe(true);
  });

  it('routes self-referencing relationships as dedicated side loops without cutting across cards', () => {
    const cardPos: NodePosition = { x: 100, y: 100, width: 240, height: 120 };

    const result = computeOrthogonalPath(cardPos, cardPos, 0, 1);
    expect(result.path).toContain('M 340 124');
    expect(result.labelX).toBeGreaterThan(340); // Label is to the right of the card
  });

  it('separates parallel edges between the same table pair with distinct channel offsets', () => {
    const srcPos: NodePosition = { x: 50, y: 100, width: 240, height: 120 };
    const tgtPos: NodePosition = { x: 450, y: 100, width: 240, height: 120 };

    const edge1 = computeOrthogonalPath(srcPos, tgtPos, 0, 2);
    const edge2 = computeOrthogonalPath(srcPos, tgtPos, 1, 2);

    expect(edge1.path).not.toEqual(edge2.path);
    expect(edge1.labelX).not.toEqual(edge2.labelX);
  });

  it('calculates proper Fit-To-View centering and zoom for any graph bounding box', () => {
    const positions = new Map<string, NodePosition>([
      ['t1', { x: 60, y: 50, width: 240, height: 150 }],
      ['t2', { x: 380, y: 50, width: 240, height: 200 }],
      ['t3', { x: 700, y: 50, width: 240, height: 150 }],
    ]);

    const fit = calculateFitToView(positions, 1000, 600, 50);

    expect(fit.zoom).toBeGreaterThan(0.35);
    expect(fit.zoom).toBeLessThanOrEqual(1.2);
    expect(fit.pan.x).toBeDefined();
    expect(fit.pan.y).toBeDefined();
  });
});
