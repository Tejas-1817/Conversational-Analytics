import React, { useState, useMemo, useRef } from 'react';
import { ChevronUp, ChevronDown, Compass } from 'lucide-react';
import type { DomainGraphNode } from '../types';

export interface CameraViewState {
  centerX: number;
  centerY: number;
  zoom: number;
  viewportWidth: number;
  viewportHeight: number;
}

export interface GraphMinimapProps {
  nodes: DomainGraphNode[];
  sourcesMap: Map<string, { name: string; color: string }>;
  focalTableId?: string | null;
  onSelectNode: (node: DomainGraphNode) => void;
  nodeCoordinates?: Map<string, [number, number]>;
  cameraView?: CameraViewState | null;
  onPanTo?: (targetX: number, targetY: number) => void;
}

export const GraphMinimap: React.FC<GraphMinimapProps> = ({
  nodes,
  sourcesMap,
  focalTableId,
  onSelectNode,
  nodeCoordinates,
  cameraView,
  onPanTo,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // Determine whether we have real coordinates from ECharts layout
  const hasRealCoords = useMemo(() => {
    if (!nodeCoordinates || nodeCoordinates.size === 0) return false;
    let found = 0;
    for (const node of nodes) {
      if (nodeCoordinates.has(node.id)) {
        found++;
        if (found >= 2) return true;
      }
    }
    return found > 0;
  }, [nodeCoordinates, nodes]);

  // Compute bounding box across all active nodes with valid coordinates
  const bounds = useMemo(() => {
    if (!hasRealCoords || !nodeCoordinates) {
      return { minX: 0, maxX: 100, minY: 0, maxY: 100, spanX: 100, spanY: 100 };
    }

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    let validCount = 0;

    nodes.forEach((node) => {
      const pt = nodeCoordinates.get(node.id);
      if (pt && !isNaN(pt[0]) && !isNaN(pt[1])) {
        minX = Math.min(minX, pt[0]);
        maxX = Math.max(maxX, pt[0]);
        minY = Math.min(minY, pt[1]);
        maxY = Math.max(maxY, pt[1]);
        validCount++;
      }
    });

    if (validCount === 0 || !isFinite(minX)) {
      return { minX: 0, maxX: 100, minY: 0, maxY: 100, spanX: 100, spanY: 100 };
    }

    // 12% padding margin around layout bounds
    const rawSpanX = Math.max(80, maxX - minX);
    const rawSpanY = Math.max(80, maxY - minY);
    const padX = rawSpanX * 0.12;
    const padY = rawSpanY * 0.12;

    const bMinX = minX - padX;
    const bMaxX = maxX + padX;
    const bMinY = minY - padY;
    const bMaxY = maxY + padY;

    return {
      minX: bMinX,
      maxX: bMaxX,
      minY: bMinY,
      maxY: bMaxY,
      spanX: Math.max(10, bMaxX - bMinX),
      spanY: Math.max(10, bMaxY - bMinY),
    };
  }, [hasRealCoords, nodeCoordinates, nodes]);

  // Project nodes into minimap percentage space (0% to 100%)
  const miniNodes = useMemo(() => {
    if (nodes.length === 0) return [];

    return nodes.map((node, index) => {
      let x = 50;
      let y = 50;

      const pt = hasRealCoords && nodeCoordinates ? nodeCoordinates.get(node.id) : null;
      if (pt && !isNaN(pt[0]) && !isNaN(pt[1])) {
        // Real coordinate projection
        x = ((pt[0] - bounds.minX) / bounds.spanX) * 100;
        y = ((pt[1] - bounds.minY) / bounds.spanY) * 100;
      } else {
        // Fallback: circular distribution while force simulation converges
        const total = nodes.length;
        const angle = index * ((2 * Math.PI) / Math.max(1, total));
        const radius = Math.min(42, 20 + Math.sqrt(total) * 2.5);
        x = 50 + radius * Math.cos(angle);
        y = 50 + radius * Math.sin(angle) * 0.75;
      }

      const src = sourcesMap.get(node.source_id);
      const isFocal = node.id === focalTableId;

      return {
        id: node.id,
        node,
        x: Math.max(5, Math.min(95, x)),
        y: Math.max(5, Math.min(95, y)),
        color: isFocal ? '#F59E0B' : src?.color || '#4F46E5',
        size: isFocal ? 7.5 : 4.5,
        isFocal,
      };
    });
  }, [nodes, hasRealCoords, nodeCoordinates, bounds, sourcesMap, focalTableId]);

  // Calculate Camera Viewport Rectangle in minimap space
  const cameraRect = useMemo(() => {
    if (!cameraView || !hasRealCoords || bounds.spanX <= 0 || bounds.spanY <= 0) {
      return null;
    }

    const { centerX, centerY, zoom, viewportWidth, viewportHeight } = cameraView;
    if (zoom <= 0 || viewportWidth <= 0 || viewportHeight <= 0) {
      return null;
    }

    // Visible canvas span in graph coordinates
    const visW = viewportWidth / zoom;
    const visH = viewportHeight / zoom;

    const camMinX = centerX - visW / 2;
    const camMinY = centerY - visH / 2;

    const left = ((camMinX - bounds.minX) / bounds.spanX) * 100;
    const top = ((camMinY - bounds.minY) / bounds.spanY) * 100;
    const width = (visW / bounds.spanX) * 100;
    const height = (visH / bounds.spanY) * 100;

    return {
      left: Math.max(-50, Math.min(150, left)),
      top: Math.max(-50, Math.min(150, top)),
      width: Math.max(4, Math.min(200, width)),
      height: Math.max(4, Math.min(200, height)),
    };
  }, [cameraView, hasRealCoords, bounds]);

  // Handle click on minimap background to translate camera
  const handleMinimapClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!onPanTo || !containerRef.current || !hasRealCoords) return;

    const rect = containerRef.current.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) / rect.width; // 0 to 1
    const clickY = (e.clientY - rect.top) / rect.height; // 0 to 1

    const targetX = bounds.minX + clickX * bounds.spanX;
    const targetY = bounds.minY + clickY * bounds.spanY;

    onPanTo(targetX, targetY);
  };

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '16px',
        right: '16px',
        zIndex: 20,
        background: 'rgba(255, 255, 255, 0.94)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.08)',
        overflow: 'hidden',
        transition: 'all 0.2s ease',
      }}
    >
      {/* Header bar */}
      <div
        onClick={() => setIsExpanded((prev) => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          background: '#F8FAFC',
          borderBottom: isExpanded ? '1px solid var(--border-color)' : 'none',
          cursor: 'pointer',
          userSelect: 'none',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', fontWeight: 700, color: '#334155' }}>
          <Compass size={13} style={{ color: 'var(--primary)' }} />
          <span>Radar View ({nodes.length})</span>
        </div>
        <button
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            color: '#64748B',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      {/* Minimap Body */}
      {isExpanded && (
        <div style={{ padding: '8px' }}>
          <div
            ref={containerRef}
            onClick={handleMinimapClick}
            style={{
              position: 'relative',
              width: '150px',
              height: '95px',
              background: '#0F172A',
              borderRadius: '6px',
              overflow: 'hidden',
              cursor: 'crosshair',
            }}
          >
            {/* Subtle Grid Lines */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                backgroundImage:
                  'radial-gradient(circle, rgba(255, 255, 255, 0.12) 1px, transparent 1px)',
                backgroundSize: '16px 16px',
              }}
            />

            {/* Radar Center Crosshair */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: 0,
                right: 0,
                height: '1px',
                background: 'rgba(255, 255, 255, 0.08)',
              }}
            />
            <div
              style={{
                position: 'absolute',
                left: '50%',
                top: 0,
                bottom: 0,
                width: '1px',
                background: 'rgba(255, 255, 255, 0.08)',
              }}
            />

            {/* Camera Viewport Frustum Rectangle */}
            {cameraRect && (
              <div
                style={{
                  position: 'absolute',
                  left: `${cameraRect.left}%`,
                  top: `${cameraRect.top}%`,
                  width: `${cameraRect.width}%`,
                  height: `${cameraRect.height}%`,
                  border: '1.5px solid rgba(99, 102, 241, 0.85)',
                  background: 'rgba(99, 102, 241, 0.16)',
                  borderRadius: '3px',
                  pointerEvents: 'none',
                  boxShadow: '0 0 6px rgba(99, 102, 241, 0.3)',
                  transition: 'all 0.08s ease-out',
                }}
              />
            )}

            {/* Mini Nodes */}
            {miniNodes.map((mn) => (
              <div
                key={mn.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectNode(mn.node);
                }}
                title={`Click to focus: ${mn.node.table_name}`}
                style={{
                  position: 'absolute',
                  left: `${mn.x}%`,
                  top: `${mn.y}%`,
                  width: `${mn.size}px`,
                  height: `${mn.size}px`,
                  borderRadius: '50%',
                  background: mn.color,
                  transform: 'translate(-50%, -50%)',
                  boxShadow: mn.isFocal ? '0 0 8px #F59E0B' : '0 0 3px rgba(0, 0, 0, 0.5)',
                  cursor: 'pointer',
                  border: mn.isFocal ? '1.5px solid #FFFFFF' : '0.5px solid rgba(255, 255, 255, 0.6)',
                  transition: 'transform 0.15s ease',
                  zIndex: mn.isFocal ? 5 : 2,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1.8)')}
                onMouseLeave={(e) => (e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1)')}
              />
            ))}
          </div>

          <div
            style={{
              marginTop: '6px',
              fontSize: '9.5px',
              color: '#64748B',
              textAlign: 'center',
            }}
          >
            Click dot or box to pan canvas
          </div>
        </div>
      )}
    </div>
  );
};
