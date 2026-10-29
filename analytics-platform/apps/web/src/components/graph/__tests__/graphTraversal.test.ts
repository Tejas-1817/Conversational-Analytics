import { describe, it, expect } from 'vitest';
import {
  getConnectedTableIds,
  filterEdgesByVisibleNodes,
  computeNodeDegreeMap,
  type RelationshipEdge,
} from '../helpers/graphTraversal';

describe('Graph Traversal & ERD Filtering Utilities', () => {
  // Test Case 1: All tables mode data representation
  it('handles isolated and connected tables gracefully in degree mapping', () => {
    const edges: RelationshipEdge[] = [
      { source_table_id: 'users', target_table_id: 'orders' },
    ];
    const degrees = computeNodeDegreeMap(edges);

    expect(degrees.get('users')).toBe(1);
    expect(degrees.get('orders')).toBe(1);
    expect(degrees.get('isolated_table')).toBeUndefined();
  });

  // Test Case 2: Related mode hides degree-zero tables
  it('identifies degree-zero tables as isolated (degree === 0 or undefined)', () => {
    const edges: RelationshipEdge[] = [
      { source_table_id: 'authors', target_table_id: 'books' },
    ];
    const degrees = computeNodeDegreeMap(edges);
    const allTables = ['authors', 'books', 'audit_logs', 'temp_dump'];

    const relatedTables = allTables.filter((t) => (degrees.get(t) || 0) > 0);
    expect(relatedTables).toEqual(['authors', 'books']);
    expect(relatedTables).not.toContain('audit_logs');
    expect(relatedTables).not.toContain('temp_dump');
  });

  // Test Case 3: Related mode includes non-isolated tables from multiple disconnected components
  it('retains tables from multiple distinct, disconnected relationship clusters in related mode', () => {
    // Cluster 1: users -> orders
    // Cluster 2: inventory -> warehouses
    // Standalone: config_table
    const edges: RelationshipEdge[] = [
      { source_table_id: 'users', target_table_id: 'orders' },
      { source_table_id: 'inventory', target_table_id: 'warehouses' },
    ];
    const degrees = computeNodeDegreeMap(edges);
    const allTables = ['users', 'orders', 'inventory', 'warehouses', 'config_table'];

    const relatedTables = allTables.filter((t) => (degrees.get(t) || 0) > 0);
    expect(relatedTables).toContain('users');
    expect(relatedTables).toContain('orders');
    expect(relatedTables).toContain('inventory');
    expect(relatedTables).toContain('warehouses');
    expect(relatedTables).not.toContain('config_table');
  });

  // Test Case 4: Connected mode includes the selected table and all reachable tables (N-hop BFS)
  it('includes the selected table and all reachable tables transitively across foreign keys', () => {
    // customers -> orders -> order_items -> products
    const edges: RelationshipEdge[] = [
      { source_table_id: 'customers', target_table_id: 'orders' },
      { source_table_id: 'orders', target_table_id: 'order_items' },
      { source_table_id: 'order_items', target_table_id: 'products' },
      // Disconnected component
      { source_table_id: 'logs', target_table_id: 'servers' },
    ];

    const connectedFromCustomers = getConnectedTableIds('customers', edges);
    expect(connectedFromCustomers).toEqual(
      new Set(['customers', 'orders', 'order_items', 'products'])
    );
    expect(connectedFromCustomers.has('logs')).toBe(false);
    expect(connectedFromCustomers.has('servers')).toBe(false);

    // Bidirectional check: starting at middle of chain traverses both backwards and forwards
    const connectedFromOrderItems = getConnectedTableIds('order_items', edges);
    expect(connectedFromOrderItems).toEqual(
      new Set(['customers', 'orders', 'order_items', 'products'])
    );
  });

  // Test Case 5: Direct-connections mode includes only one-hop neighbors
  it('restricts visible connected tables to direct 1-hop neighbors when maxHops is 1', () => {
    // customers -> orders -> order_items -> products
    const edges: RelationshipEdge[] = [
      { source_table_id: 'customers', target_table_id: 'orders' },
      { source_table_id: 'orders', target_table_id: 'order_items' },
      { source_table_id: 'order_items', target_table_id: 'products' },
    ];

    // From customers: 1 hop reaches only orders
    const directFromCustomers = getConnectedTableIds('customers', edges, 1);
    expect(directFromCustomers).toEqual(new Set(['customers', 'orders']));

    // From orders: 1 hop reaches incoming (customers) and outgoing (order_items)
    const directFromOrders = getConnectedTableIds('orders', edges, 1);
    expect(directFromOrders).toEqual(new Set(['orders', 'customers', 'order_items']));
    expect(directFromOrders.has('products')).toBe(false);
  });

  // Test Case 6: Selecting a different table updates the connected component
  it('updates the connected component when selecting a different table', () => {
    const edges: RelationshipEdge[] = [
      { source_table_id: 'compA_1', target_table_id: 'compA_2' },
      { source_table_id: 'compB_1', target_table_id: 'compB_2' },
      { source_table_id: 'compB_2', target_table_id: 'compB_3' },
    ];

    const selectionA = getConnectedTableIds('compA_1', edges);
    expect(selectionA).toEqual(new Set(['compA_1', 'compA_2']));

    // Switch selection to compB_1
    const selectionB = getConnectedTableIds('compB_1', edges);
    expect(selectionB).toEqual(new Set(['compB_1', 'compB_2', 'compB_3']));
    expect(selectionB.has('compA_1')).toBe(false);
  });

  // Test Case 7: A selected isolated table produces a graph containing only that table, not an error
  it('returns a set containing only the isolated table itself without error', () => {
    const edges: RelationshipEdge[] = [
      { source_table_id: 'users', target_table_id: 'profiles' },
    ];

    const isolatedResult = getConnectedTableIds('standalone_table', edges);
    expect(isolatedResult).toBeInstanceOf(Set);
    expect(isolatedResult.size).toBe(1);
    expect(isolatedResult.has('standalone_table')).toBe(true);
  });

  // Test Case 8: A nonexistent or unavailable selected table is handled safely
  it('handles nonexistent, empty, or whitespace table IDs safely without throwing', () => {
    const edges: RelationshipEdge[] = [
      { source_table_id: 'a', target_table_id: 'b' },
    ];

    expect(getConnectedTableIds('', edges)).toEqual(new Set());
    expect(getConnectedTableIds('   ', edges)).toEqual(new Set());
    expect(getConnectedTableIds(null as any, edges)).toEqual(new Set());
    expect(getConnectedTableIds(undefined as any, edges)).toEqual(new Set());
    expect(getConnectedTableIds('ghost_table', [])).toEqual(new Set(['ghost_table']));
  });

  // Test Case 9: Cyclic relationships terminate correctly
  it('terminates correctly and without infinite loop on cyclic relationships', () => {
    // Cycle: A -> B -> C -> A, plus branch C -> D
    const cyclicEdges: RelationshipEdge[] = [
      { source_table_id: 'A', target_table_id: 'B' },
      { source_table_id: 'B', target_table_id: 'C' },
      { source_table_id: 'C', target_table_id: 'A' },
      { source_table_id: 'C', target_table_id: 'D' },
    ];

    const result = getConnectedTableIds('A', cyclicEdges);
    expect(result).toEqual(new Set(['A', 'B', 'C', 'D']));

    // Direct connections in cycle
    const directResult = getConnectedTableIds('A', cyclicEdges, 1);
    expect(directResult).toEqual(new Set(['A', 'B', 'C']));
  });

  // Test Case 10: Self-referencing relationships do not cause infinite traversal
  it('handles self-referencing relationships without recursion or infinite loop', () => {
    // employees -> employees (manager_id foreign key)
    // employees -> departments
    const selfRefEdges: RelationshipEdge[] = [
      { source_table_id: 'employees', target_table_id: 'employees' },
      { source_table_id: 'employees', target_table_id: 'departments' },
    ];

    const result = getConnectedTableIds('employees', selfRefEdges);
    expect(result).toEqual(new Set(['employees', 'departments']));
  });

  // Test Case 11: Duplicate edges do not duplicate visible nodes
  it('handles duplicate foreign key edges safely without duplicating nodes', () => {
    // Multiple foreign keys between same tables (e.g. billing_address_id and shipping_address_id)
    const duplicateEdges: RelationshipEdge[] = [
      { source_table_id: 'orders', target_table_id: 'addresses', id: 'rel-1' },
      { source_table_id: 'orders', target_table_id: 'addresses', id: 'rel-2' },
      { source_table_id: 'orders', target_table_id: 'addresses', id: 'rel-3' },
    ];

    const result = getConnectedTableIds('orders', duplicateEdges);
    expect(result).toEqual(new Set(['orders', 'addresses']));
    expect(result.size).toBe(2);
  });

  // Test Case 12: Edges with hidden endpoints are removed from the rendered graph
  it('removes edges from visible set if either source or target is not in visibleNodeIds', () => {
    const edges: RelationshipEdge[] = [
      { source_table_id: 'users', target_table_id: 'orders', id: 'e1' },
      { source_table_id: 'orders', target_table_id: 'payments', id: 'e2' },
      { source_table_id: 'users', target_table_id: 'archived_logs', id: 'e3' },
    ];

    // Suppose archived_logs and payments are hidden
    const visibleNodes = new Set(['users', 'orders']);
    const renderedEdges = filterEdgesByVisibleNodes(edges, visibleNodes);

    expect(renderedEdges.length).toBe(1);
    expect(renderedEdges[0].id).toBe('e1');
  });

  // Test Case 13: Composite foreign-key relationships remain intact
  it('keeps composite foreign-key relationships and both multi-column references intact', () => {
    const compositeEdges: RelationshipEdge[] = [
      {
        source_table_id: 'order_items',
        target_table_id: 'orders',
        source_column_id: 'col_order_id',
        target_column_id: 'col_id',
      },
      {
        source_table_id: 'order_items',
        target_table_id: 'orders',
        source_column_id: 'col_tenant_id',
        target_column_id: 'col_tenant_id',
      },
    ];

    const connected = getConnectedTableIds('order_items', compositeEdges);
    expect(connected).toEqual(new Set(['order_items', 'orders']));

    const visibleEdges = filterEdgesByVisibleNodes(compositeEdges, connected);
    expect(visibleEdges.length).toBe(2);
  });

  // Test Case 14: Direct vs N-hop traversal scope consistency
  it('accurately respects maxHops parameter from 0 to N', () => {
    // 0 -> 1 -> 2 -> 3 -> 4
    const linearEdges: RelationshipEdge[] = [
      { source_table_id: 't0', target_table_id: 't1' },
      { source_table_id: 't1', target_table_id: 't2' },
      { source_table_id: 't2', target_table_id: 't3' },
      { source_table_id: 't3', target_table_id: 't4' },
    ];

    expect(getConnectedTableIds('t0', linearEdges, 0)).toEqual(new Set(['t0']));
    expect(getConnectedTableIds('t0', linearEdges, 1)).toEqual(new Set(['t0', 't1']));
    expect(getConnectedTableIds('t0', linearEdges, 2)).toEqual(new Set(['t0', 't1', 't2']));
    expect(getConnectedTableIds('t0', linearEdges, 3)).toEqual(new Set(['t0', 't1', 't2', 't3']));
    expect(getConnectedTableIds('t0', linearEdges, Infinity)).toEqual(
      new Set(['t0', 't1', 't2', 't3', 't4'])
    );
  });

  // Test Case 15: Enterprise / schema authorization boundary preserved
  it('strictly operates within provided authorized edges without inventing external tables', () => {
    // Given only authorized tenant relationships
    const authorizedEdges: RelationshipEdge[] = [
      { source_table_id: 'tenant_users', target_table_id: 'tenant_roles' },
    ];

    const connected = getConnectedTableIds('tenant_users', authorizedEdges);
    expect(connected).toEqual(new Set(['tenant_users', 'tenant_roles']));
    expect(connected.has('system_admin_secrets')).toBe(false);
  });
});
