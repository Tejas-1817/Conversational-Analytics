import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Table as TableIcon,
  Key,
  Link2,
  Search,
  Share2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  X,
  ChevronLeft,
  Target,
  Zap,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Sparkles,
  Layers,
  Network,
} from 'lucide-react';
import type {
  DomainGraphNode,
  DomainGraphEdge,
  TableFilterMode,
  ConnectedScope,
} from './types';
import {
  type NodePosition,
  computeHierarchicalLayout,
  computeOrthogonalPath,
  calculateFitToView,
} from './helpers/erdLayout';

interface ErdRelationshipCanvasProps {
  nodes: DomainGraphNode[];
  edges: DomainGraphEdge[];
  allNodes?: DomainGraphNode[];
  selectedNodeId: string | null;
  selectedEdgeId?: string | null;
  onSelectNode: (node: DomainGraphNode | null) => void;
  onSelectEdge: (edge: DomainGraphEdge | null) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  filterMode?: TableFilterMode;
  onChangeFilterMode?: (mode: TableFilterMode) => void;
  connectedScope?: ConnectedScope;
  onChangeConnectedScope?: (scope: ConnectedScope) => void;
  relatedOnly?: boolean;
  onToggleRelatedOnly?: () => void;
  onRefresh?: () => void;
  viewMode?: 'erd' | 'neo4j_circle';
  onToggleViewMode?: (mode: 'erd' | 'neo4j_circle') => void;
  onFocusTable?: (tableId: string) => void;
  onFindPathFromTable?: (tableId: string) => void;
  onInspectTableFull?: (tableId: string) => void;
  onReviewRelationship?: (
    relationshipId: string,
    action: 'approve' | 'reject',
    cardinality?: string
  ) => Promise<void>;
  isReviewing?: boolean;
  workspaceName?: string;
  workspaceSubtitle?: string;
}

const CARD_WIDTH = 240;
const HEADER_HEIGHT = 42;
const ROW_HEIGHT = 26;
const BOTTOM_PADDING = 8;
const COMPACT_CARD_HEIGHT = 56;

export const ErdRelationshipCanvas: React.FC<ErdRelationshipCanvasProps> = ({
  nodes,
  edges,
  allNodes = [],
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
  searchQuery,
  onSearchChange,
  filterMode,
  onChangeFilterMode,
  connectedScope = 'all',
  onChangeConnectedScope,
  relatedOnly = false,
  onToggleRelatedOnly,
  onRefresh,
  viewMode = 'erd',
  onToggleViewMode,
  onFocusTable,
  onFindPathFromTable,
  onInspectTableFull,
  onReviewRelationship,
  isReviewing = false,
  workspaceName = 'Database Schema',
  workspaceSubtitle,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Active table filter mode ('all' | 'related' | 'connected')
  const activeFilterMode: TableFilterMode = filterMode ?? (relatedOnly ? 'related' : 'all');

  const handleFilterModeChange = (mode: TableFilterMode) => {
    if (onChangeFilterMode) {
      onChangeFilterMode(mode);
    } else if (onToggleRelatedOnly) {
      if ((mode === 'related' && !relatedOnly) || (mode === 'all' && relatedOnly)) {
        onToggleRelatedOnly();
      }
    }
  };

  // Pan & Zoom state
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 60, y: 40 });
  const [zoom, setZoom] = useState<number>(1);
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Refs for high-frequency native wheel & pinch gestures to prevent closure staleness
  const panRef = useRef(pan);
  panRef.current = pan;
  const zoomRef = useRef(zoom);
  const isCompact = zoom < 0.62;
  zoomRef.current = zoom;

  // Sidebar toggle state
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState<boolean>(true);
  const [tableSearchQuery, setTableSearchQuery] = useState<string>('');
  const [columnFilterQuery, setColumnFilterQuery] = useState<string>('');

  // Node Positions Map: table_id -> { x, y, width, height }
  const [nodePositions, setNodePositions] = useState<Map<string, NodePosition>>(new Map());

  // Dragging node state
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragStartPosRef = useRef<{ x: number; y: number } | null>(null);
  const hasDraggedRef = useRef<boolean>(false);
  const panStartPosRef = useRef<{ x: number; y: number } | null>(null);
  const hasPannedRef = useRef<boolean>(false);

  // Selected edge state for review dropdown
  const [reviewCardinality, setReviewCardinality] = useState<string>('one_to_many');

  // Map of nodes for quick lookup
  const nodesMap = useMemo(() => {
    const map = new Map<string, DomainGraphNode>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  // Currently inspected node object
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodesMap.get(selectedNodeId) || null;
  }, [selectedNodeId, nodesMap]);

  // Currently inspected edge object
  const selectedEdge = useMemo(() => {
    if (!selectedEdgeId) return null;
    return edges.find((e) => e.id === selectedEdgeId || e.relationship_id === selectedEdgeId) || null;
  }, [selectedEdgeId, edges]);

  // Update reviewCardinality when selectedEdge changes
  useEffect(() => {
    if (selectedEdge) {
      setReviewCardinality(selectedEdge.cardinality || 'one_to_many');
    }
  }, [selectedEdge]);

  // Compute table height based on column count (limit visible columns to 7 to prevent giant cards)
  const getNodeHeight = useCallback((node: DomainGraphNode, isCompact: boolean = false) => {
    if (isCompact) {
      return COMPACT_CARD_HEIGHT;
    }
    const visibleCols = Math.min(node.columns.length, 7);
    return HEADER_HEIGHT + visibleCols * ROW_HEIGHT + BOTTOM_PADDING;
  }, []);

  // Previous nodes key to prevent wiping user drag adjustments on unrelated state updates
  const prevNodesKeyRef = useRef<string>('');

  // Compute Left-to-Right Hierarchical layout for initial positions (Cycle-Proof & Non-Overlapping)
  useEffect(() => {
    if (nodes.length === 0) {
      setNodePositions(new Map());
      return;
    }

    // Check if node set is identical to preserve user-dragged adjustments
    const currentNodesKey = nodes.map((n) => n.id).sort().join(':::');
    if (currentNodesKey === prevNodesKeyRef.current && nodePositions.size === nodes.length) {
      return;
    }
    prevNodesKeyRef.current = currentNodesKey;

    const newPositions = computeHierarchicalLayout(nodes, edges, getNodeHeight, {
      cardWidth: CARD_WIDTH,
      maxPerCol: 4,
      colGap: 80,
      rowGap: 32,
      layerSpacing: 35,
      startX: 60,
      startY: 50,
    });

    setNodePositions(newPositions);

    // Auto-fit to view with safe container measurement
    const timer = setTimeout(() => {
      if (containerRef.current && newPositions.size > 0) {
        const containerW = containerRef.current.clientWidth || 900;
        const containerH = containerRef.current.clientHeight || 650;
        const fit = calculateFitToView(newPositions, containerW, containerH, 50);
        setPan(fit.pan);
        setZoom(fit.zoom);
      }
    }, 40);

    return () => clearTimeout(timer);
  }, [nodes, edges, getNodeHeight]);

  // Set of connected edges and nodes for current selection
  const { activeNodeIds, activeEdgeIds, nodeRelationships } = useMemo(() => {
    const activeNodes = new Set<string>();
    const activeEdges = new Set<string>();
    const rels: Array<{
      edge: DomainGraphEdge;
      direction: 'outgoing' | 'incoming';
      connectedNode: DomainGraphNode | undefined;
    }> = [];

    if (selectedNodeId) {
      activeNodes.add(selectedNodeId);
      edges.forEach((e) => {
        if (e.source_table_id === selectedNodeId) {
          activeEdges.add(e.id);
          activeNodes.add(e.target_table_id);
          rels.push({
            edge: e,
            direction: 'outgoing',
            connectedNode: nodesMap.get(e.target_table_id),
          });
        } else if (e.target_table_id === selectedNodeId) {
          activeEdges.add(e.id);
          activeNodes.add(e.source_table_id);
          rels.push({
            edge: e,
            direction: 'incoming',
            connectedNode: nodesMap.get(e.source_table_id),
          });
        }
      });
    } else if (selectedEdge) {
      activeEdges.add(selectedEdge.id);
      activeNodes.add(selectedEdge.source_table_id);
      activeNodes.add(selectedEdge.target_table_id);
    }

    return { activeNodeIds: activeNodes, activeEdgeIds: activeEdges, nodeRelationships: rels };
  }, [selectedNodeId, selectedEdge, edges, nodesMap]);

  // Pan / Canvas Mouse Handlers
  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left mouse button
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    panStartPosRef.current = { x: e.clientX, y: e.clientY };
    hasPannedRef.current = false;
  };

  const handleCanvasMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      if (panStartPosRef.current) {
        const dist = Math.hypot(e.clientX - panStartPosRef.current.x, e.clientY - panStartPosRef.current.y);
        if (dist > 4) {
          hasPannedRef.current = true;
        }
      }
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    } else if (draggingNodeId) {
      if (dragStartPosRef.current) {
        const dist = Math.hypot(e.clientX - dragStartPosRef.current.x, e.clientY - dragStartPosRef.current.y);
        if (dist > 4) {
          hasDraggedRef.current = true;
        }
      }
      if (hasDraggedRef.current) {
        const newPos = {
          x: (e.clientX - pan.x) / zoom - dragOffset.x,
          y: (e.clientY - pan.y) / zoom - dragOffset.y,
        };
        setNodePositions((prev) => {
          const next = new Map(prev);
          const curr = next.get(draggingNodeId);
          if (curr) {
            next.set(draggingNodeId, { ...curr, x: newPos.x, y: newPos.y });
          }
          return next;
        });
      }
    }
  };

  const handleCanvasMouseUp = () => {
    setIsPanning(false);
    setDraggingNodeId(null);
    dragStartPosRef.current = null;
  };

  // Viewport-centered Zoom for toolbar buttons
  const handleZoomByFactor = useCallback((factor: number) => {
    if (!containerRef.current) return;
    const containerW = containerRef.current.clientWidth || 900;
    const containerH = containerRef.current.clientHeight || 650;
    const centerX = containerW / 2;
    const centerY = containerH / 2;

    const currentZoom = zoomRef.current;
    const currentPan = panRef.current;
    const nextZoom = Math.min(2.5, Math.max(0.35, currentZoom * factor));

    if (Math.abs(nextZoom - currentZoom) > 0.0001) {
      const worldX = (centerX - currentPan.x) / currentZoom;
      const worldY = (centerY - currentPan.y) / currentZoom;
      const nextPan = {
        x: centerX - worldX * nextZoom,
        y: centerY - worldY * nextZoom,
      };

      zoomRef.current = nextZoom;
      panRef.current = nextPan;
      setZoom(nextZoom);
      setPan(nextPan);
    }
  }, []);

  // Native non-passive wheel listener attached to canvas container
  // Crucial: React 18/19 passive wheel listeners ignore e.preventDefault(),
  // which causes the browser to zoom the whole web page instead of the ERD canvas!
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onNativeWheel = (e: WheelEvent) => {
      // Completely prevent browser-level page zoom and document scroll
      e.preventDefault();
      e.stopPropagation();

      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      let factor: number;
      if (e.ctrlKey) {
        // Trackpad pinch gesture or Ctrl + Wheel: smooth exponential zoom
        factor = Math.exp(-e.deltaY * 0.008);
      } else {
        // Standard mouse wheel notch: normalize step
        const normalizedDelta = Math.max(-100, Math.min(100, e.deltaY));
        factor = normalizedDelta < 0 ? 1.08 : 0.92;
      }

      // Clamp factor to avoid large single-frame jumps
      factor = Math.min(1.3, Math.max(0.7, factor));

      const currentZoom = zoomRef.current;
      const currentPan = panRef.current;
      const nextZoom = Math.min(2.5, Math.max(0.35, currentZoom * factor));

      if (Math.abs(nextZoom - currentZoom) > 0.0001) {
        // Keep the exact point under the mouse cursor stationary
        const worldX = (mouseX - currentPan.x) / currentZoom;
        const worldY = (mouseY - currentPan.y) / currentZoom;
        const nextPan = {
          x: mouseX - worldX * nextZoom,
          y: mouseY - worldY * nextZoom,
        };

        zoomRef.current = nextZoom;
        panRef.current = nextPan;
        setZoom(nextZoom);
        setPan(nextPan);
      }
    };

    container.addEventListener('wheel', onNativeWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', onNativeWheel);
    };
  }, []);

  // Node Drag Start (only initializes potential drag gesture, does not prematurely select)
  const handleNodeMouseDown = (e: React.MouseEvent, nodeId: string) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const nodePos = nodePositions.get(nodeId);
    if (!nodePos) return;

    // Calculate click offset relative to node top-left in zoomed space
    const clickX = (e.clientX - pan.x) / zoom;
    const clickY = (e.clientY - pan.y) / zoom;

    setDraggingNodeId(nodeId);
    setDragOffset({
      x: clickX - nodePos.x,
      y: clickY - nodePos.y,
    });
    dragStartPosRef.current = { x: e.clientX, y: e.clientY };
    hasDraggedRef.current = false;
  };

  // Fit View to fit all nodes neatly inside viewport
  const handleFitToView = useCallback(() => {
    if (nodePositions.size === 0 || !containerRef.current) return;
    const containerW = containerRef.current.clientWidth || 900;
    const containerH = containerRef.current.clientHeight || 650;
    const fit = calculateFitToView(nodePositions, containerW, containerH, 50);
    panRef.current = fit.pan;
    zoomRef.current = fit.zoom;
    setPan(fit.pan);
    setZoom(fit.zoom);
  }, [nodePositions]);

  // Center on a specific table
  const handleCenterOnTable = (nodeId: string) => {
    const targetNode =
      nodesMap.get(nodeId) || (allNodes ? allNodes.find((n) => n.id === nodeId) : null);
    onSelectNode(targetNode || null);
    onSelectEdge(null);

    const pos = nodePositions.get(nodeId);
    if (!pos || !containerRef.current) return;
    const containerW = containerRef.current.clientWidth || 800;
    const containerH = containerRef.current.clientHeight || 600;

    const targetX = containerW / 2 - (pos.x + pos.width / 2) * zoom;
    const targetY = containerH / 2 - (pos.y + pos.height / 2) * zoom;
    const newPan = { x: targetX, y: targetY };
    panRef.current = newPan;
    setPan(newPan);
  };

  // Parallel edge tracker to distribute channels between the same pair of tables
  const edgePairInfo = useMemo(() => {
    const pairCounts = new Map<string, number>();
    const pairIndices = new Map<string, number>();

    edges.forEach((e) => {
      const key = [e.source_table_id, e.target_table_id].sort().join(':::');
      pairCounts.set(key, (pairCounts.get(key) || 0) + 1);
    });

    const pairTracker = new Map<string, number>();
    edges.forEach((e) => {
      const key = [e.source_table_id, e.target_table_id].sort().join(':::');
      const idx = pairTracker.get(key) || 0;
      pairIndices.set(e.id, idx);
      pairTracker.set(key, idx + 1);
    });

    return { pairCounts, pairIndices };
  }, [edges]);

  // Filtered tables for the left sidebar
  const sidebarSourceTables = useMemo(() => {
    // If in connected mode with no table selected, use allNodes so user can select a table
    if (activeFilterMode === 'connected' && !selectedNodeId && allNodes && allNodes.length > 0) {
      return allNodes;
    }
    return nodes;
  }, [activeFilterMode, selectedNodeId, allNodes, nodes]);

  const sidebarFilteredTables = useMemo(() => {
    if (!tableSearchQuery.trim()) return sidebarSourceTables;
    const q = tableSearchQuery.toLowerCase();
    return sidebarSourceTables.filter(
      (t) =>
        t.table_name.toLowerCase().includes(q) ||
        (t.business_name || '').toLowerCase().includes(q)
    );
  }, [sidebarSourceTables, tableSearchQuery]);

  // Computed stats for selected table
  const selectedNodeStats = useMemo(() => {
    if (!selectedNode) return { cols: 0, pks: 0, rels: 0 };
    const pks = selectedNode.columns.filter((c) => c.is_primary_key).length;
    return {
      cols: selectedNode.columns.length,
      pks,
      rels: nodeRelationships.length,
    };
  }, [selectedNode, nodeRelationships]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '740px',
        background: '#FFFFFF',
        border: '1px solid var(--border-color, #E2E8F0)',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
        userSelect: 'none',
      }}
    >
      {/* ========================================================================= */}
      {/* 1. TOP HEADER BAR (Exact Match to Reference Screenshots) */}
      {/* ========================================================================= */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid #F1F5F9',
          background: '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          zIndex: 10,
        }}
      >
        {/* Left: Title & Subtitle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <button
            onClick={() => setIsLeftSidebarOpen((prev) => !prev)}
            title={isLeftSidebarOpen ? 'Hide tables list' : 'Show tables list'}
            style={{
              background: isLeftSidebarOpen ? '#EEF2FF' : '#F8FAFC',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              padding: '6px 8px',
              cursor: 'pointer',
              color: isLeftSidebarOpen ? '#4F46E5' : '#64748B',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '11px',
              fontWeight: 600,
              transition: 'all 0.15s ease',
            }}
          >
            <Layers size={14} />
            <span>Tables</span>
          </button>

          <div>
            <div style={{ fontSize: '22px', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em' }}>
              Relationship map
            </div>
            <div style={{ fontSize: '13px', color: '#64748B', marginTop: '2px' }}>
              Explore tables, columns, and foreign-key relationships.
            </div>
          </div>
        </div>

        {/* Right: Search Input & "Related only" Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', width: '240px' }}>
            <Search
              size={15}
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#94A3B8',
              }}
            />
            <input
              type="text"
              placeholder="Find table or column..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 14px 8px 36px',
                fontSize: '12.5px',
                borderRadius: '9999px',
                border: '1px solid #E2E8F0',
                background: '#FFFFFF',
                color: '#1E293B',
                outline: 'none',
                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
              }}
            />
          </div>

          {/* 3-Mode Filter Segmented Control */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: '#F1F5F9',
              borderRadius: '9999px',
              padding: '3px',
              border: '1px solid #E2E8F0',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
            }}
          >
            <button
              onClick={() => handleFilterModeChange('all')}
              title="Show all tables (including standalone / isolated tables)"
              style={{
                padding: '5px 12px',
                borderRadius: '9999px',
                border: 'none',
                fontSize: '11.5px',
                fontWeight: activeFilterMode === 'all' ? 700 : 500,
                cursor: 'pointer',
                background: activeFilterMode === 'all' ? '#FFFFFF' : 'transparent',
                color: activeFilterMode === 'all' ? '#1E293B' : '#64748B',
                boxShadow: activeFilterMode === 'all' ? '0 1px 2px rgba(0, 0, 0, 0.08)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              Show all
            </button>
            <button
              onClick={() => handleFilterModeChange('related')}
              title="Show all tables with at least one foreign-key relationship (degree > 0)"
              style={{
                padding: '5px 12px',
                borderRadius: '9999px',
                border: 'none',
                fontSize: '11.5px',
                fontWeight: activeFilterMode === 'related' ? 700 : 500,
                cursor: 'pointer',
                background: activeFilterMode === 'related' ? '#FFFFFF' : 'transparent',
                color: activeFilterMode === 'related' ? '#1E293B' : '#64748B',
                boxShadow: activeFilterMode === 'related' ? '0 1px 2px rgba(0, 0, 0, 0.08)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              Related only
            </button>
            <button
              onClick={() => handleFilterModeChange('connected')}
              title={
                selectedNodeId
                  ? 'Show tables connected to the selected table'
                  : 'Select a table to view its connected tables'
              }
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                borderRadius: '9999px',
                border: 'none',
                fontSize: '11.5px',
                fontWeight: activeFilterMode === 'connected' ? 700 : 500,
                cursor: 'pointer',
                background: activeFilterMode === 'connected' ? '#4F46E5' : 'transparent',
                color: activeFilterMode === 'connected' ? '#FFFFFF' : '#64748B',
                boxShadow: activeFilterMode === 'connected' ? '0 1px 2px rgba(0, 0, 0, 0.1)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <Network size={13} />
              <span>Connected to selected</span>
            </button>
          </div>

          {/* Relationship Scope: Visible when "Connected to selected" mode is active */}
          {activeFilterMode === 'connected' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                background: '#EEF2FF',
                borderRadius: '9999px',
                padding: '2px',
                border: '1px solid #C7D2FE',
              }}
            >
              <button
                onClick={() => onChangeConnectedScope && onChangeConnectedScope('all')}
                title="Traverse all connected hops across the entire reachable component"
                style={{
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: (!connectedScope || connectedScope === 'all') ? 700 : 500,
                  cursor: 'pointer',
                  background: (!connectedScope || connectedScope === 'all') ? '#4F46E5' : 'transparent',
                  color: (!connectedScope || connectedScope === 'all') ? '#FFFFFF' : '#4F46E5',
                  transition: 'all 0.15s ease',
                }}
              >
                All connected
              </button>
              <button
                onClick={() => onChangeConnectedScope && onChangeConnectedScope('direct')}
                title="Show only direct (1-hop) incoming and outgoing foreign-key neighbors"
                style={{
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: connectedScope === 'direct' ? 700 : 500,
                  cursor: 'pointer',
                  background: connectedScope === 'direct' ? '#4F46E5' : 'transparent',
                  color: connectedScope === 'direct' ? '#FFFFFF' : '#4F46E5',
                  transition: 'all 0.15s ease',
                }}
              >
                Direct only (1-hop)
              </button>
            </div>
          )}

          {/* View Mode Toggle: ERD vs Topology */}
          {onToggleViewMode && (
            <div
              style={{
                display: 'flex',
                background: '#F1F5F9',
                borderRadius: '9999px',
                padding: '3px',
                border: '1px solid #E2E8F0',
              }}
            >
              <button
                onClick={() => onToggleViewMode('erd')}
                style={{
                  padding: '5px 12px',
                  borderRadius: '9999px',
                  border: 'none',
                  fontSize: '11.5px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: viewMode === 'erd' ? '#4F46E5' : 'transparent',
                  color: viewMode === 'erd' ? '#FFFFFF' : '#64748B',
                  transition: 'all 0.15s ease',
                }}
              >
                ERD
              </button>
              <button
                onClick={() => onToggleViewMode('neo4j_circle')}
                style={{
                  padding: '5px 12px',
                  borderRadius: '9999px',
                  border: 'none',
                  fontSize: '11.5px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: viewMode === 'neo4j_circle' ? '#4F46E5' : 'transparent',
                  color: viewMode === 'neo4j_circle' ? '#FFFFFF' : '#64748B',
                  transition: 'all 0.15s ease',
                }}
              >
                Topology
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. SECONDARY STATUS / INSTRUCTION BAR */}
      {/* ========================================================================= */}
      <div
        style={{
          padding: '8px 24px',
          borderBottom: '1px solid #F1F5F9',
          background: '#FAFAFA',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
          zIndex: 9,
        }}
      >
        {/* Stats Bullets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontWeight: 600, color: '#475569' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#4F46E5' }} />
            <span>{nodes.length} tables</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#4F46E5' }} />
            <span>{edges.length} relationships</span>
          </div>
          {activeFilterMode === 'connected' && selectedNode && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#4F46E5' }}>
              <span style={{ fontSize: '11px', fontWeight: 500, color: '#64748B' }}>Root:</span>
              <span style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 700 }}>
                {selectedNode.table_name}
              </span>
              {nodes.length === 1 && edges.length === 0 && (
                <span style={{ fontSize: '11px', fontWeight: 500, color: '#94A3B8' }}>
                  (Isolated table • 0 relationships)
                </span>
              )}
            </div>
          )}
        </div>

        {/* Right: Hint & Zoom Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', color: '#64748B' }}>
          <span>Click edge or table to inspect • Scroll to zoom</span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <button
              onClick={() => handleZoomByFactor(1.15)}
              title="Zoom In"
              style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '6px',
                padding: '4px 6px',
                cursor: 'pointer',
                color: '#64748B',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ZoomIn size={14} />
            </button>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: '#64748B',
                minWidth: '38px',
                textAlign: 'center',
                userSelect: 'none',
              }}
              title="Current Zoom Level"
            >
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => handleZoomByFactor(0.85)}
              title="Zoom Out"
              style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '6px',
                padding: '4px 6px',
                cursor: 'pointer',
                color: '#64748B',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <ZoomOut size={14} />
            </button>
            <button
              onClick={handleFitToView}
              title="Fit Graph to View (Auto-Center & Scale)"
              style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '6px',
                padding: '4px 6px',
                cursor: 'pointer',
                color: '#64748B',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <Maximize2 size={14} />
            </button>
            {onRefresh && (
              <button
                onClick={onRefresh}
                title="Refresh Graph"
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E2E8F0',
                  borderRadius: '6px',
                  padding: '4px 6px',
                  cursor: 'pointer',
                  color: '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <RefreshCw size={14} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. MAIN WORKSPACE BODY: (Optional Left Sidebar + Canvas + Optional Right Panel) */}
      {/* ========================================================================= */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* ======================================================================= */}
        {/* LEFT SIDEBAR: TABLES LIST (Matching User Reference) */}
        {/* ======================================================================= */}
        {isLeftSidebarOpen && (
          <div
            style={{
              width: '220px',
              borderRight: '1px solid #F1F5F9',
              background: '#FFFFFF',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
              zIndex: 10,
            }}
          >
            {/* Sidebar Header */}
            <div
              style={{
                padding: '12px 14px',
                borderBottom: '1px solid #F1F5F9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: '#64748B',
                  }}
                >
                  TABLES
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    background: '#F1F5F9',
                    color: '#64748B',
                    padding: '1px 6px',
                    borderRadius: '9999px',
                  }}
                >
                  {sidebarSourceTables.length}
                </span>
              </div>

              <button
                onClick={() => setIsLeftSidebarOpen(false)}
                title="Collapse sidebar"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#94A3B8',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <ChevronLeft size={16} />
              </button>
            </div>

            {/* Quick table search if > 6 tables */}
            {nodes.length > 6 && (
              <div style={{ padding: '8px 12px', borderBottom: '1px solid #F8FAFC' }}>
                <input
                  type="text"
                  placeholder="Filter tables..."
                  value={tableSearchQuery}
                  onChange={(e) => setTableSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '4px 8px',
                    fontSize: '11.5px',
                    borderRadius: '6px',
                    border: '1px solid #E2E8F0',
                    outline: 'none',
                  }}
                />
              </div>
            )}

            {/* Tables List */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '6px 8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
              }}
            >
              {sidebarFilteredTables.map((t) => {
                const isSelected = selectedNodeId === t.id;
                return (
                  <div
                    key={t.id}
                    onClick={() => handleCenterOnTable(t.id)}
                    style={{
                      padding: '7px 10px',
                      borderRadius: '6px',
                      background: isSelected ? '#EEF2FF' : 'transparent',
                      border: isSelected ? '1px solid #C7D2FE' : '1px solid transparent',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      transition: 'all 0.12s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.background = '#F8FAFC';
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                      <TableIcon
                        size={13}
                        style={{ color: isSelected ? '#4F46E5' : '#94A3B8', flexShrink: 0 }}
                      />
                      <span
                        style={{
                          fontSize: '12px',
                          fontFamily: 'ui-monospace, monospace',
                          fontWeight: isSelected ? 700 : 500,
                          color: isSelected ? '#4F46E5' : '#1E293B',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {t.table_name}
                      </span>
                    </div>

                    <span
                      style={{
                        fontSize: '10.5px',
                        fontWeight: 600,
                        color: isSelected ? '#4F46E5' : '#94A3B8',
                        background: isSelected ? '#E0E7FF' : '#F1F5F9',
                        padding: '1px 5px',
                        borderRadius: '4px',
                        flexShrink: 0,
                      }}
                    >
                      {t.column_count}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ======================================================================= */}
        {/* CENTER: INTERACTIVE CANVAS WITH DOTTED GRID BACKGROUND */}
        {/* ======================================================================= */}
        <div
          ref={containerRef}
          onMouseDown={handleCanvasMouseDown}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onClick={() => {
            if (!hasPannedRef.current) {
              onSelectNode(null);
              onSelectEdge(null);
            }
          }}
          style={{
            flex: 1,
            position: 'relative',
            overflow: 'hidden',
            touchAction: 'none',
            cursor: isPanning ? 'grabbing' : 'grab',
            backgroundColor: '#FAFAFA',
            backgroundImage: 'radial-gradient(#CBD5E1 1.25px, transparent 1.25px)',
            backgroundSize: '20px 20px',
          }}
        >
          {/* Empty state: Connected mode active but no table selected */}
          {activeFilterMode === 'connected' && !selectedNodeId && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 20,
                pointerEvents: 'none',
                padding: '24px',
              }}
            >
              <div
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E2E8F0',
                  borderRadius: '16px',
                  padding: '36px 40px',
                  maxWidth: '460px',
                  width: '100%',
                  textAlign: 'center',
                  boxShadow:
                    '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.03)',
                  pointerEvents: 'auto',
                }}
              >
                <div
                  style={{
                    width: '56px',
                    height: '56px',
                    borderRadius: '14px',
                    background: '#EEF2FF',
                    color: '#4F46E5',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 16px auto',
                  }}
                >
                  <Network size={28} />
                </div>
                <h3
                  style={{
                    margin: '0 0 8px 0',
                    fontSize: '17px',
                    fontWeight: 700,
                    color: '#0F172A',
                  }}
                >
                  Select a table to view its connected tables.
                </h3>
                <p
                  style={{
                    margin: '0 0 20px 0',
                    fontSize: '13px',
                    color: '#64748B',
                    lineHeight: 1.55,
                  }}
                >
                  Pick any table from the sidebar list or search above to explore its connected relationship network.
                </p>

                {allNodes && allNodes.length > 0 && (
                  <div style={{ marginBottom: '20px', textAlign: 'left' }}>
                    <div
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        color: '#94A3B8',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        marginBottom: '8px',
                      }}
                    >
                      Quick Select:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {allNodes.slice(0, 5).map((t) => (
                        <button
                          key={t.id}
                          onClick={() => handleCenterOnTable(t.id)}
                          style={{
                            padding: '5px 10px',
                            borderRadius: '6px',
                            background: '#F8FAFC',
                            border: '1px solid #E2E8F0',
                            fontSize: '12px',
                            fontFamily: 'ui-monospace, monospace',
                            color: '#334155',
                            cursor: 'pointer',
                            transition: 'all 0.12s ease',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.borderColor = '#C7D2FE';
                            e.currentTarget.style.background = '#EEF2FF';
                            e.currentTarget.style.color = '#4F46E5';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.borderColor = '#E2E8F0';
                            e.currentTarget.style.background = '#F8FAFC';
                            e.currentTarget.style.color = '#334155';
                          }}
                        >
                          {t.table_name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={() => handleFilterModeChange('all')}
                  style={{
                    padding: '9px 18px',
                    borderRadius: '8px',
                    background: '#4F46E5',
                    color: '#FFFFFF',
                    border: 'none',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: '0 2px 4px rgba(79, 70, 229, 0.2)',
                    transition: 'background 0.15s ease',
                  }}
                >
                  Show all tables
                </button>
              </div>
            </div>
          )}

          {/* Empty state: 0 nodes in all/related mode */}
          {nodes.length === 0 && activeFilterMode !== 'connected' && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10,
                pointerEvents: 'none',
              }}
            >
              <div
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E2E8F0',
                  borderRadius: '12px',
                  padding: '24px 32px',
                  textAlign: 'center',
                  boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)',
                  pointerEvents: 'auto',
                }}
              >
                <p style={{ margin: '0 0 12px 0', fontSize: '13.5px', color: '#64748B' }}>
                  No tables match the current filter criteria.
                </p>
                {searchQuery && (
                  <button
                    onClick={() => onSearchChange('')}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '6px',
                      background: '#F1F5F9',
                      border: '1px solid #CBD5E1',
                      fontSize: '12px',
                      fontWeight: 600,
                      color: '#334155',
                      cursor: 'pointer',
                    }}
                  >
                    Clear search
                  </button>
                )}
              </div>
            </div>
          )}
          {/* Transformable Canvas Layer */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: '0 0',
            }}
          >
            {/* SVG LAYER: ORTHOGONAL RELATIONSHIP LINES & BADGES */}
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '10000px',
                height: '10000px',
                pointerEvents: 'none',
                overflow: 'visible',
              }}
            >
              <defs>
                {/* Idle Arrowhead */}
                <marker
                  id="arrow-idle"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#CBD5E1" />
                </marker>

                {/* Active / Highlighted Arrowhead */}
                <marker
                  id="arrow-active"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#6366F1" />
                </marker>
              </defs>

              {/* Render Links */}
              {edges.map((e) => {
                const srcPos = nodePositions.get(e.source_table_id);
                const tgtPos = nodePositions.get(e.target_table_id);
                if (!srcPos || !tgtPos) return null;

                const srcNode = nodesMap.get(e.source_table_id);
                const tgtNode = nodesMap.get(e.target_table_id);

                const effectiveSrcPos = {
                  ...srcPos,
                  height: srcNode ? getNodeHeight(srcNode, isCompact) : (isCompact ? COMPACT_CARD_HEIGHT : srcPos.height),
                  };
                  const effectiveTgtPos = {
                    ...tgtPos,
                    height: tgtNode ? getNodeHeight(tgtNode, isCompact) : (isCompact ? COMPACT_CARD_HEIGHT : tgtPos.height),
                  };

                const pairKey = [e.source_table_id, e.target_table_id].sort().join(':::');
                const totalForPair = edgePairInfo.pairCounts.get(pairKey) || 1;
                const edgeIdx = edgePairInfo.pairIndices.get(e.id) || 0;

                const { path, labelX, labelY } = computeOrthogonalPath(
                  effectiveSrcPos,
                  effectiveTgtPos,
                  edgeIdx,
                  totalForPair
                );
                const isActive = activeEdgeIds.has(e.id);
                const badgeText = e.cardinality === 'one_to_many' ? '1:N' : e.cardinality === 'many_to_one' ? '1:N' : '1:1';

                return (
                  <g
                    key={e.id}
                    style={{ pointerEvents: 'auto', cursor: 'pointer' }}
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectEdge(e);
                      onSelectNode(null);
                    }}
                  >
                    {/* Thicker transparent stroke for easy hover/clicking */}
                    <path
                      d={path}
                      fill="none"
                      stroke="transparent"
                      strokeWidth={14}
                    />

                    {/* Visible Orthogonal Line */}
                    <path
                      d={path}
                      fill="none"
                      stroke={isActive ? '#6366F1' : '#CBD5E1'}
                      strokeWidth={isActive ? 2.5 : 1.75}
                      markerEnd={isActive ? 'url(#arrow-active)' : 'url(#arrow-idle)'}
                      style={{ transition: 'stroke 0.15s ease, stroke-width 0.15s ease' }}
                    />

                    {/* Cardinality Badge (1:N) */}
                    <g
                      transform={`translate(${labelX}, ${labelY})`}
                      style={{ pointerEvents: 'auto' }}
                    >
                      <rect
                        x={-15}
                        y={-9}
                        width={30}
                        height={18}
                        rx={4}
                        fill="#FFFFFF"
                        stroke={isActive ? '#6366F1' : '#CBD5E1'}
                        strokeWidth={isActive ? 1.5 : 1}
                        style={{ filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.05))' }}
                      />
                      <text
                        x={0}
                        y={3.5}
                        textAnchor="middle"
                        fill={isActive ? '#4F46E5' : '#64748B'}
                        fontSize={9.5}
                        fontWeight={700}
                        fontFamily="ui-monospace, monospace"
                      >
                        {badgeText}
                      </text>
                    </g>
                  </g>
                );
              })}
            </svg>

            {/* HTML DOM LAYER: LIGHT-MODE ERD TABLE CARDS */}
            {nodes.map((node) => {
              const pos = nodePositions.get(node.id);
              if (!pos) return null;

              const isSelected = selectedNodeId === node.id;
              const isConnected = activeNodeIds.has(node.id);
              const visibleCols = node.columns.slice(0, 7);

              return (
                <div
                  key={node.id}
                  onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!hasDraggedRef.current) {
                      onSelectNode(node);
                      onSelectEdge(null);
                    }
                  }}
                  style={{
                    position: 'absolute',
                    left: `${pos.x}px`,
                    top: `${pos.y}px`,
                    width: `${CARD_WIDTH}px`,
                    height: `${getNodeHeight(node, isCompact)}px`,
                    background: '#FFFFFF',
                    borderRadius: '12px',
                    border: isSelected
                      ? '2px solid #818CF8'
                      : isConnected
                      ? '1.5px solid #A5B4FC'
                      : '1px solid #E2E8F0',
                    boxShadow: isSelected
                      ? '0 0 0 4px rgba(129, 140, 248, 0.22), 0 10px 25px rgba(0, 0, 0, 0.08)'
                      : '0 4px 16px rgba(15, 23, 42, 0.05)',
                    cursor: draggingNodeId === node.id ? 'grabbing' : 'pointer',
                    zIndex: isSelected ? 30 : isConnected ? 20 : 10,
                    transition: draggingNodeId === node.id ? 'none' : 'box-shadow 0.15s ease, border 0.15s ease',
                    overflow: 'visible',
                  }}
                >
                  {/* Left Port Dot */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-4px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: isConnected ? '#6366F1' : '#94A3B8',
                      border: '1.5px solid #FFFFFF',
                      boxShadow: '0 0 2px rgba(0,0,0,0.2)',
                    }}
                  />

                  {/* Right Port Dot */}
                  <div
                    style={{
                      position: 'absolute',
                      right: '-4px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: isConnected ? '#6366F1' : '#94A3B8',
                      border: '1.5px solid #FFFFFF',
                      boxShadow: '0 0 2px rgba(0,0,0,0.2)',
                    }}
                  />

                  {/* Semantic Zoom LOD: Compact View when zoomed out (zoom < 0.62) */}
                  {zoom < 0.62 ? (
                    <div style={{ padding: '8px 12px' }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: '4px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                          <TableIcon size={14} style={{ color: '#4F46E5', flexShrink: 0 }} />
                          <span
                            style={{
                              fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                              fontWeight: 700,
                              fontSize: '13px',
                              color: '#0F172A',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {node.table_name}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: '10.5px',
                            fontWeight: 700,
                            color: '#4F46E5',
                            background: '#EEF2FF',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            flexShrink: 0,
                          }}
                        >
                          {node.column_count} cols
                        </span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '11px',
                          color: '#64748B',
                        }}
                      >
                        <span style={{ textTransform: 'lowercase' }}>{node.schema_name}</span>
                        <span>{(node.row_count || 0).toLocaleString()} rows</span>
                      </div>
                    </div>
                  ) : (
                    <>
                      {/* Table Header */}
                      <div
                        style={{
                          padding: '10px 14px',
                          borderBottom: '1px solid #F1F5F9',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          background: isSelected ? '#F8FAFC' : '#FFFFFF',
                          borderTopLeftRadius: '11px',
                          borderTopRightRadius: '11px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                          <TableIcon size={14} style={{ color: '#4F46E5', flexShrink: 0 }} />
                          <span
                            style={{
                              fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                              fontWeight: 700,
                              fontSize: '13px',
                              color: '#0F172A',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {node.table_name}
                          </span>
                        </div>

                        {/* Column Count Badge */}
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            color: '#64748B',
                            background: '#F1F5F9',
                            padding: '2px 7px',
                            borderRadius: '6px',
                            flexShrink: 0,
                          }}
                        >
                          {node.column_count}
                        </span>
                      </div>

                      {/* Column Rows */}
                      <div style={{ padding: '4px 0 8px 0' }}>
                        {visibleCols.map((col) => {
                          const isPk = col.is_primary_key;
                          const isFk = col.is_foreign_key;
                          const dataType = (col.data_type || 'VARCHAR').toUpperCase();

                          return (
                            <div
                              key={col.id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '4px 14px',
                                fontSize: '11.5px',
                                fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                              }}
                            >
                              {/* Left: Icon + Column Name */}
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                                {isPk ? (
                                  <Key size={12} style={{ color: '#0284C7', flexShrink: 0 }} />
                                ) : isFk ? (
                                  <Link2 size={12} style={{ color: '#0284C7', flexShrink: 0 }} />
                                ) : (
                                  <span style={{ color: '#94A3B8', fontSize: '13px', lineHeight: 1, padding: '0 2px' }}>
                                    •
                                  </span>
                                )}

                                <span
                                  style={{
                                    color: isPk || isFk ? '#0F172A' : '#334155',
                                    fontWeight: isPk || isFk ? 600 : 400,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {col.column_name}
                                </span>
                              </div>

                              {/* Right: Data Type */}
                              <span
                                style={{
                                  color: '#64748B',
                                  fontSize: '10px',
                                  fontWeight: 500,
                                  flexShrink: 0,
                                  marginLeft: '10px',
                                }}
                              >
                                {dataType}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ======================================================================= */}
        {/* RIGHT SIDEBAR: TABLE / RELATIONSHIP DETAILS PANEL (Exact Match to Screenshot) */}
        {/* ======================================================================= */}
        {(selectedNode || selectedEdge) && (
          <div
            style={{
              width: '340px',
              borderLeft: '1px solid #E2E8F0',
              background: '#FFFFFF',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
              zIndex: 20,
              boxShadow: '-4px 0 16px rgba(0, 0, 0, 0.04)',
              overflowY: 'auto',
            }}
          >
            {/* ------------------------------------------------------------------- */}
            {/* VIEW A: TABLE DETAILS */}
            {/* ------------------------------------------------------------------- */}
            {selectedNode && (
              <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
                {/* Header: Title + Close */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                    <div>
                      <div
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          letterSpacing: '0.08em',
                          color: '#64748B',
                        }}
                      >
                        TABLE DETAILS
                      </div>
                      <div
                        style={{
                          fontSize: '20px',
                          fontWeight: 800,
                          color: '#0F172A',
                          fontFamily: 'ui-monospace, monospace',
                          marginTop: '2px',
                        }}
                      >
                        {selectedNode.table_name}
                      </div>
                    </div>

                    <button
                      onClick={() => onSelectNode(null)}
                      title="Close details"
                      style={{
                        background: '#F8FAFC',
                        border: '1px solid #E2E8F0',
                        borderRadius: '6px',
                        width: '28px',
                        height: '28px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        color: '#64748B',
                      }}
                    >
                      <X size={15} />
                    </button>
                  </div>

                  {/* Description */}
                  <div style={{ fontSize: '12.5px', color: '#475569', marginTop: '6px', lineHeight: 1.4 }}>
                    {selectedNode.business_name ||
                      `Table containing ${selectedNode.column_count} columns in schema ${selectedNode.schema_name}.`}
                  </div>
                </div>

                {/* 3 Metrics Cards in a Row: Columns, Primary keys, Relations */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    background: '#F8FAFC',
                    border: '1px solid #E2E8F0',
                    borderRadius: '8px',
                    padding: '12px 8px',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ borderRight: '1px solid #E2E8F0' }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: '#0F172A' }}>
                      {selectedNodeStats.cols}
                    </div>
                    <div style={{ fontSize: '10.5px', color: '#64748B', marginTop: '2px' }}>Columns</div>
                  </div>
                  <div style={{ borderRight: '1px solid #E2E8F0' }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: '#0F172A' }}>
                      {selectedNodeStats.pks}
                    </div>
                    <div style={{ fontSize: '10.5px', color: '#64748B', marginTop: '2px' }}>Primary keys</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: '#0F172A' }}>
                      {selectedNodeStats.rels}
                    </div>
                    <div style={{ fontSize: '10.5px', color: '#64748B', marginTop: '2px' }}>Relations</div>
                  </div>
                </div>

                {/* Quick Action Buttons */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  {onFocusTable && (
                    <button
                      onClick={() => onFocusTable(selectedNode.id)}
                      title="Filter canvas to this table and direct connections"
                      style={{
                        flex: 1,
                        padding: '7px 10px',
                        background: '#EEF2FF',
                        border: '1px solid #C7D2FE',
                        borderRadius: '6px',
                        color: '#4F46E5',
                        fontSize: '11.5px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '5px',
                      }}
                    >
                      <Target size={13} />
                      <span>Focus Table</span>
                    </button>
                  )}
                  {onFindPathFromTable && (
                    <button
                      onClick={() => onFindPathFromTable(selectedNode.id)}
                      title="Find shortest join route to another table"
                      style={{
                        flex: 1,
                        padding: '7px 10px',
                        background: '#F0FDF4',
                        border: '1px solid #BBF7D0',
                        borderRadius: '6px',
                        color: '#15803D',
                        fontSize: '11.5px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '5px',
                      }}
                    >
                      <Zap size={13} />
                      <span>Join Path</span>
                    </button>
                  )}
                </div>

                {/* COLUMNS SECTION */}
                <div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '10px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          letterSpacing: '0.08em',
                          color: '#64748B',
                        }}
                      >
                        COLUMNS
                      </span>
                      <span
                        style={{
                          fontSize: '10.5px',
                          fontWeight: 600,
                          background: '#F1F5F9',
                          color: '#64748B',
                          padding: '1px 6px',
                          borderRadius: '9999px',
                        }}
                      >
                        {selectedNode.columns.length}
                      </span>
                    </div>

                    {selectedNode.columns.length > 5 && (
                      <input
                        type="text"
                        placeholder="Search col..."
                        value={columnFilterQuery}
                        onChange={(e) => setColumnFilterQuery(e.target.value)}
                        style={{
                          padding: '3px 8px',
                          fontSize: '11px',
                          borderRadius: '4px',
                          border: '1px solid #E2E8F0',
                          width: '100px',
                          outline: 'none',
                        }}
                      />
                    )}
                  </div>

                  {/* Columns List */}
                  <div
                    style={{
                      border: '1px solid #F1F5F9',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      background: '#FFFFFF',
                    }}
                  >
                    {selectedNode.columns
                      .filter((c) =>
                        columnFilterQuery
                          ? c.column_name.toLowerCase().includes(columnFilterQuery.toLowerCase()) ||
                            c.data_type.toLowerCase().includes(columnFilterQuery.toLowerCase())
                          : true
                      )
                      .map((col, idx, arr) => {
                        const isPk = col.is_primary_key;
                        const isFk = col.is_foreign_key;
                        const dataType = (col.data_type || 'VARCHAR').toUpperCase();

                        return (
                          <div
                            key={col.id}
                            style={{
                              padding: '8px 12px',
                              borderBottom: idx === arr.length - 1 ? 'none' : '1px solid #F8FAFC',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                              {/* Left Badge: PK / FK / Bullet */}
                              {isPk ? (
                                <span
                                  style={{
                                    fontSize: '9.5px',
                                    fontWeight: 800,
                                    background: '#FEF3C7',
                                    color: '#B45309',
                                    padding: '2px 5px',
                                    borderRadius: '4px',
                                    flexShrink: 0,
                                  }}
                                >
                                  PK
                                </span>
                              ) : isFk ? (
                                <span
                                  style={{
                                    fontSize: '9.5px',
                                    fontWeight: 800,
                                    background: '#DBEAFE',
                                    color: '#1D4ED8',
                                    padding: '2px 5px',
                                    borderRadius: '4px',
                                    flexShrink: 0,
                                  }}
                                >
                                  FK
                                </span>
                              ) : (
                                <span
                                  style={{
                                    width: '18px',
                                    height: '18px',
                                    borderRadius: '4px',
                                    background: '#F1F5F9',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: '#94A3B8',
                                    fontSize: '12px',
                                    flexShrink: 0,
                                  }}
                                >
                                  •
                                </span>
                              )}

                              <div>
                                <div
                                  style={{
                                    fontSize: '12.5px',
                                    fontFamily: 'ui-monospace, monospace',
                                    fontWeight: isPk || isFk ? 600 : 500,
                                    color: '#0F172A',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {col.column_name}
                                </div>
                                <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '1px' }}>
                                  {isPk ? 'Primary Key' : 'Not null'}
                                </div>
                              </div>
                            </div>

                            {/* Right: Data Type */}
                            <span
                              style={{
                                fontSize: '10.5px',
                                fontFamily: 'ui-monospace, monospace',
                                color: '#64748B',
                                flexShrink: 0,
                                marginLeft: '8px',
                              }}
                            >
                              {dataType}
                            </span>
                          </div>
                        );
                      })}
                  </div>
                </div>

                {/* RELATIONS SECTION */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        color: '#64748B',
                      }}
                    >
                      RELATIONS
                    </span>
                    <span
                      style={{
                        fontSize: '10.5px',
                        fontWeight: 600,
                        background: '#F1F5F9',
                        color: '#64748B',
                        padding: '1px 6px',
                        borderRadius: '9999px',
                      }}
                    >
                      {nodeRelationships.length}
                    </span>
                  </div>

                  {nodeRelationships.length === 0 ? (
                    <div style={{ fontSize: '11.5px', color: '#94A3B8', fontStyle: 'italic', padding: '4px 0' }}>
                      No relationships detected for this table.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {nodeRelationships.map(({ edge, direction, connectedNode }) => {
                        const targetTableName = connectedNode?.table_name || 'unknown_table';
                        const badgeText = edge.cardinality === 'one_to_many' ? '1:N' : edge.cardinality === 'many_to_one' ? 'N:1' : '1:1';

                        return (
                          <div
                            key={edge.id}
                            onClick={() => {
                              onSelectEdge(edge);
                              onSelectNode(null);
                            }}
                            style={{
                              padding: '8px 10px',
                              borderRadius: '6px',
                              background: '#F8FAFC',
                              border: '1px solid #E2E8F0',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              transition: 'all 0.12s ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#C7D2FE')}
                            onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#E2E8F0')}
                          >
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px' }}>
                                <span style={{ color: '#4F46E5', fontWeight: 600 }}>
                                  {direction === 'outgoing' ? '→' : '←'}
                                </span>
                                <span style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 700, color: '#0F172A' }}>
                                  {targetTableName}
                                </span>
                              </div>
                              <div style={{ fontSize: '10.5px', color: '#64748B', marginTop: '2px' }}>
                                {edge.source_column_name} = {edge.target_column_name}
                              </div>
                            </div>

                            <span
                              style={{
                                fontSize: '10px',
                                fontFamily: 'ui-monospace, monospace',
                                fontWeight: 700,
                                background: '#FFFFFF',
                                border: '1px solid #CBD5E1',
                                color: '#4F46E5',
                                padding: '2px 6px',
                                borderRadius: '4px',
                              }}
                            >
                              {badgeText}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Inspect Full Table Details & Profiling */}
                {onInspectTableFull && (
                  <button
                    onClick={() => onInspectTableFull(selectedNode.table_id)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      background: '#FFFFFF',
                      border: '1px solid #E2E8F0',
                      color: '#4F46E5',
                      fontWeight: 600,
                      fontSize: '12px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#EEF2FF')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '#FFFFFF')}
                  >
                    <span>Inspect Full Profiling & Stats</span>
                    <ExternalLink size={13} />
                  </button>
                )}
              </div>
            )}

            {/* ------------------------------------------------------------------- */}
            {/* VIEW B: RELATIONSHIP DETAILS (When an Edge is Clicked) */}
            {/* ------------------------------------------------------------------- */}
            {selectedEdge && (
              <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
                {/* Header: Title + Close */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div>
                    <div
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        color: '#64748B',
                      }}
                    >
                      RELATIONSHIP DETAILS
                    </div>
                    <div
                      style={{
                        fontSize: '15px',
                        fontWeight: 800,
                        color: '#0F172A',
                        fontFamily: 'ui-monospace, monospace',
                        marginTop: '2px',
                      }}
                    >
                      {nodesMap.get(selectedEdge.source_table_id)?.table_name} →{' '}
                      {nodesMap.get(selectedEdge.target_table_id)?.table_name}
                    </div>
                  </div>

                  <button
                    onClick={() => onSelectEdge(null)}
                    title="Close details"
                    style={{
                      background: '#F8FAFC',
                      border: '1px solid #E2E8F0',
                      borderRadius: '6px',
                      width: '28px',
                      height: '28px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      color: '#64748B',
                    }}
                  >
                    <X size={15} />
                  </button>
                </div>

                {/* Status & Confidence Badge */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: selectedEdge.status === 'approved' ? '#ECFDF5' : '#FFFBEB',
                    border: `1px solid ${selectedEdge.status === 'approved' ? '#A7F3D0' : '#FDE68A'}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {selectedEdge.status === 'approved' ? (
                      <CheckCircle2 size={15} style={{ color: '#059669' }} />
                    ) : (
                      <Sparkles size={15} style={{ color: '#D97706' }} />
                    )}
                    <span
                      style={{
                        fontSize: '11.5px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        color: selectedEdge.status === 'approved' ? '#065F46' : '#92400E',
                      }}
                    >
                      {selectedEdge.status || 'inferred'}
                    </span>
                  </div>
                  <span style={{ fontSize: '11.5px', fontWeight: 600, color: '#475569' }}>
                    {Math.round((selectedEdge.confidence || 1) * 100)}% Confidence
                  </span>
                </div>

                {/* Flow Mapping Card */}
                <div
                  style={{
                    background: '#F8FAFC',
                    border: '1px solid #E2E8F0',
                    borderRadius: '8px',
                    padding: '14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#64748B' }}>SOURCE TABLE & COLUMN</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#0F172A', fontFamily: 'monospace', marginTop: '2px' }}>
                      {nodesMap.get(selectedEdge.source_table_id)?.table_name}.{selectedEdge.source_column_name}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ height: '1px', flex: 1, background: '#CBD5E1' }} />
                    <span
                      style={{
                        fontSize: '10px',
                        fontFamily: 'monospace',
                        fontWeight: 700,
                        background: '#EEF2FF',
                        color: '#4F46E5',
                        padding: '2px 6px',
                        borderRadius: '4px',
                      }}
                    >
                      {selectedEdge.cardinality || '1:N'}
                    </span>
                    <div style={{ height: '1px', flex: 1, background: '#CBD5E1' }} />
                  </div>

                  <div>
                    <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#64748B' }}>TARGET TABLE & COLUMN</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#0F172A', fontFamily: 'monospace', marginTop: '2px' }}>
                      {nodesMap.get(selectedEdge.target_table_id)?.table_name}.{selectedEdge.target_column_name}
                    </div>
                  </div>
                </div>

                {/* Review Action Buttons (if review callback provided) */}
                {onReviewRelationship && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: 'auto' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748B' }}>Cardinality:</label>
                      <select
                        value={reviewCardinality}
                        onChange={(e) => setReviewCardinality(e.target.value)}
                        style={{
                          flex: 1,
                          fontSize: '11.5px',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          border: '1px solid #E2E8F0',
                        }}
                      >
                        <option value="one_to_many">One to Many (1:N)</option>
                        <option value="many_to_one">Many to One (N:1)</option>
                        <option value="one_to_one">One to One (1:1)</option>
                        <option value="many_to_many">Many to Many (N:N)</option>
                      </select>
                    </div>

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        disabled={isReviewing}
                        onClick={() =>
                          onReviewRelationship(selectedEdge.relationship_id, 'approve', reviewCardinality)
                        }
                        style={{
                          flex: 1,
                          padding: '8px 12px',
                          borderRadius: '6px',
                          background: '#10B981',
                          color: '#FFFFFF',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: '12px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                        }}
                      >
                        <CheckCircle2 size={14} />
                        <span>Approve</span>
                      </button>

                      <button
                        disabled={isReviewing}
                        onClick={() => onReviewRelationship(selectedEdge.relationship_id, 'reject')}
                        style={{
                          padding: '8px 12px',
                          borderRadius: '6px',
                          background: '#EF4444',
                          color: '#FFFFFF',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: '12px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                        }}
                      >
                        <XCircle size={14} />
                        <span>Reject</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
