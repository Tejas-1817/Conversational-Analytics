import { describe, it, expect } from 'vitest';
import {
  computeDeterministicRadialPositions,
  formatInsideNodeLabel,
  calculateDensityAwareForceParams,
} from '../helpers/topologyLayout';
import type { DomainGraphNode, DomainGraphEdge } from '../types';

describe('topologyLayout Unit Tests', () => {
  const createMockNode = (id: string, name: string): DomainGraphNode => ({
    id,
    table_id: id,
    table_name: name,
    schema_name: 'public',
    source_id: 'src-1',
    source_name: 'Postgres',
    source_type: 'postgres',
    column_count: 5,
    columns: [],
  });

  const createMockEdge = (
    id: string,
    source: string,
    target: string
  ): DomainGraphEdge => ({
    id,
    relationship_id: id,
    source_table_id: source,
    source_column_id: 'col_a',
    source_column_name: 'col_a',
    target_table_id: target,
    target_column_id: 'col_b',
    target_column_name: 'col_b',
    cardinality: 'many_to_one',
    relationship_source: 'foreign_key',
    confidence: 0.95,
    status: 'approved',
    evidence: {},
  });

  describe('computeDeterministicRadialPositions', () => {
    it('places focal root at center [0, 0]', () => {
      const nodes = [createMockNode('users', 'users')];
      const positions = computeDeterministicRadialPositions('users', nodes, []);

      expect(positions.get('users')).toEqual([0, 0]);
    });

    it('positions 1-hop neighbors evenly on concentric circle R1', () => {
      const nodes = [
        createMockNode('users', 'users'),
        createMockNode('orders', 'orders'),
        createMockNode('profiles', 'profiles'),
        createMockNode('sessions', 'sessions'),
      ];
      const edges = [
        createMockEdge('e1', 'orders', 'users'),
        createMockEdge('e2', 'profiles', 'users'),
        createMockEdge('e3', 'sessions', 'users'),
      ];

      const positions = computeDeterministicRadialPositions('users', nodes, edges, 1);

      expect(positions.get('users')).toEqual([0, 0]);
      expect(positions.size).toBe(4);

      // Verify each 1-hop neighbor is placed at radius R1 distance from [0, 0]
      const K1 = 3;
      const expectedR1 = Math.max(180, Math.min(290, 140 + K1 * 9));

      ['orders', 'profiles', 'sessions'].forEach((id) => {
        const pt = positions.get(id);
        expect(pt).toBeDefined();
        const dist = Math.sqrt(pt![0] ** 2 + pt![1] ** 2);
        expect(Math.abs(dist - expectedR1)).toBeLessThanOrEqual(2);
      });
    });

    it('positions 2-hop neighbors on outer ring R2 clustered near their parent', () => {
      const nodes = [
        createMockNode('users', 'users'),
        createMockNode('orders', 'orders'),
        createMockNode('order_items', 'order_items'),
      ];
      const edges = [
        createMockEdge('e1', 'orders', 'users'),
        createMockEdge('e2', 'order_items', 'orders'),
      ];

      const positions = computeDeterministicRadialPositions('users', nodes, edges, 2);

      expect(positions.get('users')).toEqual([0, 0]);
      expect(positions.has('orders')).toBe(true);
      expect(positions.has('order_items')).toBe(true);

      const pt1 = positions.get('orders')!;
      const pt2 = positions.get('order_items')!;

      const dist1 = Math.sqrt(pt1[0] ** 2 + pt1[1] ** 2);
      const dist2 = Math.sqrt(pt2[0] ** 2 + pt2[1] ** 2);

      expect(dist2).toBeGreaterThan(dist1);
    });
  });

  describe('formatInsideNodeLabel', () => {
    it('returns empty string for very low effective zoom size', () => {
      expect(formatInsideNodeLabel('customers', 34, 0.2)).toBe('');
    });

    it('returns full table name if length is within capacity', () => {
      expect(formatInsideNodeLabel('users', 44, 1)).toBe('users');
      expect(formatInsideNodeLabel('orders', 44, 1)).toBe('orders');
    });

    it('intelligently truncates long table names with ellipsis', () => {
      const truncated = formatInsideNodeLabel('customer_order_fulfillments', 36, 1);
      expect(truncated.endsWith('…')).toBe(true);
      expect(truncated.length).toBeLessThanOrEqual(5);
    });

    it('allows more characters when zoomed in', () => {
      const zoom1 = formatInsideNodeLabel('international_payments', 44, 1);
      const zoomHigh = formatInsideNodeLabel('international_payments', 44, 2.5);

      expect(zoomHigh.length).toBeGreaterThanOrEqual(zoom1.length);
    });
  });

  describe('calculateDensityAwareForceParams', () => {
    it('scales repulsion and edge length gracefully for small graphs', () => {
      const params = calculateDensityAwareForceParams(5, 4);

      expect(params.repulsion[0]).toBeGreaterThanOrEqual(140);
      expect(params.repulsion[1]).toBeGreaterThanOrEqual(350);
      expect(params.gravity).toBeGreaterThan(0.01);
      expect(params.gravity).toBeLessThan(0.04);
    });

    it('dampens gravity and increases repulsion for 65+ table schemas', () => {
      const params = calculateDensityAwareForceParams(65, 81);

      // Repulsion should scale to prevent central pile-up
      expect(params.repulsion[1]).toBeGreaterThan(800);
      // Gravity should be gentle to avoid excessive inward pull
      expect(params.gravity).toBeLessThan(0.015);
      expect(params.edgeLength[1]).toBeGreaterThan(150);
    });
  });
});
