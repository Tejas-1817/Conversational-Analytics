import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ErdRelationshipCanvas } from '../ErdRelationshipCanvas';
import type { DomainGraphNode, DomainGraphEdge } from '../types';

describe('ErdRelationshipCanvas 3-Mode Filter & Traversal UI', () => {
  const mockNodes: DomainGraphNode[] = [
    {
      id: 'users',
      table_id: 'users',
      table_name: 'users',
      schema_name: 'public',
      source_id: 'src-1',
      source_name: 'Postgres',
      source_type: 'postgres',
      column_count: 2,
      columns: [
        { id: 'u_id', column_name: 'id', data_type: 'uuid', is_primary_key: true, is_foreign_key: false },
        { id: 'u_email', column_name: 'email', data_type: 'varchar', is_primary_key: false, is_foreign_key: false },
      ],
    },
    {
      id: 'orders',
      table_id: 'orders',
      table_name: 'orders',
      schema_name: 'public',
      source_id: 'src-1',
      source_name: 'Postgres',
      source_type: 'postgres',
      column_count: 2,
      columns: [
        { id: 'o_id', column_name: 'id', data_type: 'uuid', is_primary_key: true, is_foreign_key: false },
        { id: 'o_user_id', column_name: 'user_id', data_type: 'uuid', is_primary_key: false, is_foreign_key: true },
      ],
    },
    {
      id: 'audit_logs',
      table_id: 'audit_logs',
      table_name: 'audit_logs',
      schema_name: 'public',
      source_id: 'src-1',
      source_name: 'Postgres',
      source_type: 'postgres',
      column_count: 1,
      columns: [
        { id: 'log_id', column_name: 'id', data_type: 'uuid', is_primary_key: true, is_foreign_key: false },
      ],
    },
  ];

  const mockEdges: DomainGraphEdge[] = [
    {
      id: 'e1',
      relationship_id: 'e1',
      source_table_id: 'orders',
      source_column_id: 'o_user_id',
      source_column_name: 'user_id',
      target_table_id: 'users',
      target_column_id: 'u_id',
      target_column_name: 'id',
      cardinality: 'many_to_one',
      relationship_source: 'foreign_key',
      confidence: 1.0,
      status: 'approved',
      evidence: {},
    },
  ];

  it('renders all three filter modes in the toolbar segmented control', () => {
    render(
      <ErdRelationshipCanvas
        nodes={mockNodes}
        edges={mockEdges}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="all"
        onChangeFilterMode={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Show all' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Related only' })).toBeDefined();
    expect(screen.getByRole('button', { name: /Connected to selected/i })).toBeDefined();
  });

  it('calls onChangeFilterMode when a different mode is clicked', () => {
    const onChangeFilterMode = vi.fn();

    render(
      <ErdRelationshipCanvas
        nodes={mockNodes}
        edges={mockEdges}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="all"
        onChangeFilterMode={onChangeFilterMode}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Related only' }));
    expect(onChangeFilterMode).toHaveBeenCalledWith('related');

    fireEvent.click(screen.getByRole('button', { name: /Connected to selected/i }));
    expect(onChangeFilterMode).toHaveBeenCalledWith('connected');
  });

  it('displays the empty state message when connected mode is active and no table is selected', () => {
    render(
      <ErdRelationshipCanvas
        nodes={[]}
        edges={[]}
        allNodes={mockNodes}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="connected"
        onChangeFilterMode={vi.fn()}
      />
    );

    expect(
      screen.getByText('Select a table to view its connected tables.')
    ).toBeDefined();
  });

  it('renders relationship scope controls (All connected vs Direct only) when connected mode is active', () => {
    const onChangeConnectedScope = vi.fn();

    render(
      <ErdRelationshipCanvas
        nodes={[mockNodes[0], mockNodes[1]]}
        edges={mockEdges}
        selectedNodeId="orders"
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="connected"
        onChangeFilterMode={vi.fn()}
        connectedScope="all"
        onChangeConnectedScope={onChangeConnectedScope}
      />
    );

    const directBtn = screen.getByRole('button', { name: /Direct only \(1-hop\)/i });
    expect(directBtn).toBeDefined();
    fireEvent.click(directBtn);
    expect(onChangeConnectedScope).toHaveBeenCalledWith('direct');

    const allBtn = screen.getByRole('button', { name: 'All connected' });
    expect(allBtn).toBeDefined();
    fireEvent.click(allBtn);
    expect(onChangeConnectedScope).toHaveBeenCalledWith('all');
  });

  it('displays Root table info in status bar when connected mode is active with a selected table', () => {
    render(
      <ErdRelationshipCanvas
        nodes={[mockNodes[0], mockNodes[1]]}
        edges={mockEdges}
        selectedNodeId="users"
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="connected"
        onChangeFilterMode={vi.fn()}
      />
    );

    expect(screen.getByText('Root:')).toBeDefined();
    expect(screen.getByText('users')).toBeDefined();
  });

  it('displays isolated indicator when selected table has no relationships', () => {
    render(
      <ErdRelationshipCanvas
        nodes={[mockNodes[2]]} // audit_logs has 0 relationships
        edges={[]}
        selectedNodeId="audit_logs"
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="connected"
        onChangeFilterMode={vi.fn()}
      />
    );

    expect(screen.getByText('Root:')).toBeDefined();
    expect(screen.getByText('audit_logs')).toBeDefined();
    expect(screen.getByText('(Isolated table • 0 relationships)')).toBeDefined();
  });

  it('renders the Fit to View button in toolbar controls', () => {
    render(
      <ErdRelationshipCanvas
        nodes={mockNodes}
        edges={mockEdges}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="all"
        onChangeFilterMode={vi.fn()}
      />
    );

    const fitBtn = screen.getByTitle('Fit Graph to View (Auto-Center & Scale)');
    expect(fitBtn).toBeDefined();
    fireEvent.click(fitBtn);
  });

  it('renders toolbar Zoom In, Zoom Out, and percentage controls', () => {
    render(
      <ErdRelationshipCanvas
        nodes={mockNodes}
        edges={mockEdges}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="all"
        onChangeFilterMode={vi.fn()}
      />
    );

    const zoomInBtn = screen.getByTitle('Zoom In');
    const zoomOutBtn = screen.getByTitle('Zoom Out');
    const zoomLevel = screen.getByTitle('Current Zoom Level');

    expect(zoomInBtn).toBeDefined();
    expect(zoomOutBtn).toBeDefined();
    expect(zoomLevel).toBeDefined();
    expect(zoomLevel.textContent).toBe('100%');

    fireEvent.click(zoomInBtn);
    expect(screen.getByTitle('Current Zoom Level').textContent).toBe('115%');

    fireEvent.click(zoomOutBtn);
    expect(screen.getByTitle('Current Zoom Level').textContent).toBe('98%');
  });

  it('prevents browser default zoom and adjusts canvas scale when wheel event occurs on canvas', () => {
    const { container } = render(
      <ErdRelationshipCanvas
        nodes={mockNodes}
        edges={mockEdges}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onSelectEdge={vi.fn()}
        searchQuery=""
        onSearchChange={vi.fn()}
        filterMode="all"
        onChangeFilterMode={vi.fn()}
      />
    );

    const canvasDiv = container.querySelector('div[style*="radial-gradient"]') as HTMLDivElement;
    expect(canvasDiv).toBeDefined();

    const wheelEvent = new WheelEvent('wheel', {
      deltaY: -100,
      bubbles: true,
      cancelable: true,
    });
    const preventDefaultSpy = vi.spyOn(wheelEvent, 'preventDefault');

    canvasDiv.dispatchEvent(wheelEvent);
    expect(preventDefaultSpy).toHaveBeenCalled();
  });
});
