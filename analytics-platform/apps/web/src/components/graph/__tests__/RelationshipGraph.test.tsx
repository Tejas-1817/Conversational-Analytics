import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { RelationshipDrawer } from '../RelationshipDrawer';
import { RelationshipGraph } from '../RelationshipGraph';
import type { DomainGraphNode, DomainGraphEdge } from '../types';

// Mock echarts-for-react
vi.mock('echarts-for-react', () => ({
  default: (props: any) => (
    <div data-testid="echarts-graph-mock">
      {props.option?.series?.[0]?.type || 'graph'}
    </div>
  ),
}));

// Mock fetchApi
vi.mock('../../services/api', () => ({
  fetchApi: vi.fn(),
}));

describe('RelationshipDrawer Component', () => {
  const mockTableNode: DomainGraphNode = {
    id: 'tbl-1',
    table_id: 'tbl-1',
    table_name: 'customers',
    business_name: 'Registered Customers',
    schema_name: 'public',
    source_id: 'src-1',
    source_name: 'Postgres Production',
    source_type: 'postgres',
    row_count: 5420,
    column_count: 2,
    columns: [
      {
        id: 'col-1',
        column_name: 'id',
        data_type: 'uuid',
        is_primary_key: true,
        is_foreign_key: false,
      },
      {
        id: 'col-2',
        column_name: 'email',
        data_type: 'varchar',
        is_primary_key: false,
        is_foreign_key: false,
      },
    ],
  };

  const mockEdge: DomainGraphEdge = {
    id: 'rel-1',
    relationship_id: 'rel-1',
    source_table_id: 'tbl-2',
    source_column_id: 'col-3',
    source_column_name: 'customer_id',
    target_table_id: 'tbl-1',
    target_column_id: 'col-1',
    target_column_name: 'id',
    cardinality: 'many_to_one',
    relationship_source: 'foreign_key',
    confidence: 0.98,
    status: 'draft',
    evidence: { constraint_name: 'fk_orders_customer' },
  };

  const nodesMap = new Map<string, DomainGraphNode>([
    ['tbl-1', mockTableNode],
    [
      'tbl-2',
      {
        id: 'tbl-2',
        table_id: 'tbl-2',
        table_name: 'orders',
        schema_name: 'public',
        source_id: 'src-1',
        source_name: 'Postgres Production',
        source_type: 'postgres',
        row_count: 12000,
        column_count: 2,
        columns: [],
      },
    ],
  ]);

  it('renders table details and column breakdown when a node is selected', () => {
    render(
      <RelationshipDrawer
        isOpen={true}
        onClose={vi.fn()}
        selectedNode={mockTableNode}
        selectedEdge={null}
        nodesMap={nodesMap}
        onReviewRelationship={vi.fn()}
      />
    );

    expect(screen.getByText('customers')).toBeDefined();
    expect(screen.getByText('Registered Customers')).toBeDefined();
    expect(screen.getByText('5,420 rows')).toBeDefined();
    expect(screen.getByText('id')).toBeDefined();
    expect(screen.getByText('email')).toBeDefined();
  });

  it('renders relationship inspector and review actions when an edge is selected', () => {
    const onReviewMock = vi.fn().mockResolvedValue(undefined);

    render(
      <RelationshipDrawer
        isOpen={true}
        onClose={vi.fn()}
        selectedNode={null}
        selectedEdge={mockEdge}
        nodesMap={nodesMap}
        onReviewRelationship={onReviewMock}
      />
    );

    expect(screen.getByText('Relationship Inspector')).toBeDefined();
    expect(screen.getByText('draft')).toBeDefined();
    expect(screen.getByText('98% Confidence')).toBeDefined();
    expect(screen.getByText('customer_id')).toBeDefined();
    expect(screen.getByText('Approve Relationship')).toBeDefined();
    expect(screen.getByText('Reject / Dismiss')).toBeDefined();

    // Click Approve
    const approveBtn = screen.getByText('Approve Relationship');
    fireEvent.click(approveBtn);
    expect(onReviewMock).toHaveBeenCalledWith('rel-1', 'approve', 'many_to_one');
  });
});

describe('RelationshipGraph Component', () => {
  it('renders toolbar search and filter controls', async () => {
    const { fetchApi } = await import('../../services/api');
    (fetchApi as any).mockResolvedValue({
      domain_id: 'dom-1',
      domain_name: 'Sales Domain',
      nodes: [],
      edges: [],
      total_nodes: 0,
      total_edges: 0,
    });

    render(<RelationshipGraph domainId="dom-1" />);

    expect(screen.getByPlaceholderText('Search tables & columns...')).toBeDefined();
    expect(screen.getByText('All Links')).toBeDefined();
    expect(screen.getByText('approved')).toBeDefined();
    expect(screen.getByText('draft')).toBeDefined();
  });
});
