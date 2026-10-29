import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { GraphMinimap, type CameraViewState } from '../widgets/GraphMinimap';
import type { DomainGraphNode } from '../types';

describe('GraphMinimap Component', () => {
  const mockNodes: DomainGraphNode[] = [
    {
      id: 'tbl-1',
      table_id: 'tbl-1',
      table_name: 'users',
      schema_name: 'public',
      source_id: 'src-1',
      source_name: 'Postgres',
      source_type: 'postgres',
      column_count: 3,
      columns: [],
    },
    {
      id: 'tbl-2',
      table_id: 'tbl-2',
      table_name: 'orders',
      schema_name: 'public',
      source_id: 'src-1',
      source_name: 'Postgres',
      source_type: 'postgres',
      column_count: 5,
      columns: [],
    },
  ];

  const mockSourcesMap = new Map([
    ['src-1', { name: 'Postgres', color: '#4F46E5' }],
  ]);

  const mockNodeCoords = new Map<string, [number, number]>([
    ['tbl-1', [100, 200]],
    ['tbl-2', [300, 400]],
  ]);

  const mockCameraView: CameraViewState = {
    centerX: 200,
    centerY: 300,
    zoom: 1,
    viewportWidth: 800,
    viewportHeight: 600,
  };

  it('renders minimap header and table count correctly', () => {
    render(
      <GraphMinimap
        nodes={mockNodes}
        sourcesMap={mockSourcesMap}
        onSelectNode={vi.fn()}
        nodeCoordinates={mockNodeCoords}
        cameraView={mockCameraView}
      />
    );

    expect(screen.getByText('Topology Radar')).toBeDefined();
    expect(screen.getByText('2 nodes')).toBeDefined();
  });

  it('renders camera viewport frustum box when cameraView is provided', () => {
    const { container } = render(
      <GraphMinimap
        nodes={mockNodes}
        sourcesMap={mockSourcesMap}
        onSelectNode={vi.fn()}
        nodeCoordinates={mockNodeCoords}
        cameraView={mockCameraView}
      />
    );

    // Look for the frustum rectangle (border: 1.5px solid #3B82F6)
    const frustumBox = container.querySelector(
      'div[style*="border: 1.5px solid rgb(59, 130, 246)"]'
    ) || container.querySelector(
      'div[style*="border: 1.5px solid #3B82F6"]'
    );
    expect(frustumBox).not.toBeNull();
  });

  it('triggers onPanTo with calculated graph coordinates when minimap is clicked', () => {
    const onPanToMock = vi.fn();

    const { container } = render(
      <GraphMinimap
        nodes={mockNodes}
        sourcesMap={mockSourcesMap}
        onSelectNode={vi.fn()}
        nodeCoordinates={mockNodeCoords}
        cameraView={mockCameraView}
        onPanTo={onPanToMock}
      />
    );

    // Find the minimap radar canvas container
    const radarContainer = container.querySelector(
      'div[style*="width: 196px"][style*="height: 140px"]'
    ) as HTMLElement;

    expect(radarContainer).toBeDefined();

    // Mock getBoundingClientRect
    radarContainer.getBoundingClientRect = () => ({
      left: 0,
      top: 0,
      width: 196,
      height: 140,
      right: 196,
      bottom: 140,
      x: 0,
      y: 0,
      toJSON: () => {},
    });

    fireEvent.click(radarContainer, { clientX: 98, clientY: 70 });

    expect(onPanToMock).toHaveBeenCalledTimes(1);
    const [targetX, targetY] = onPanToMock.mock.calls[0];
    expect(typeof targetX).toBe('number');
    expect(typeof targetY).toBe('number');
    expect(isFinite(targetX)).toBe(true);
    expect(isFinite(targetY)).toBe(true);
  });
});
