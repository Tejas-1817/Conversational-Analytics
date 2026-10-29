import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import * as echarts from 'echarts';
import ReactECharts from 'echarts-for-react';
import {
  Search,
  Filter,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Sliders,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Database,
  Link as LinkIcon,
  Layers,
  Network,
  Eye,
  EyeOff,
  CornerDownRight,
  Zap,
  Target,
  Compass,
  ArrowRight,
  X,
} from 'lucide-react';
import { fetchApi } from '../../services/api';
import type {
  DomainGraphResponse,
  DomainGraphNode,
  DomainGraphEdge,
  GraphVisualizationMode,
  TableFilterMode,
  ConnectedScope,
} from './types';
import { RelationshipDrawer } from './RelationshipDrawer';
import { ErdRelationshipCanvas } from './ErdRelationshipCanvas';
import { getFocalNeighborhood } from './helpers/graphAlgorithms';
import { getConnectedTableIds } from './helpers/graphTraversal';
import { PathFinderModal } from './widgets/PathFinderModal';
import { FocalBreadcrumbs } from './widgets/FocalBreadcrumbs';
import { GraphMinimap, type CameraViewState } from './widgets/GraphMinimap';
import {
  computeDeterministicRadialPositions,
  formatInsideNodeLabel,
  calculateDensityAwareForceParams,
} from './helpers/topologyLayout';

interface RelationshipGraphProps {
  domainId: string;
  sourceId?: string | null;
  onInspectTableFull?: (tableId: string) => void;
}

// Harmonious category colors for data sources
const SOURCE_PALETTE = [
  '#4F46E5', // Indigo
  '#059669', // Emerald
  '#D97706', // Amber
  '#0284C7', // Sky
  '#7C3AED', // Violet
  '#DB2777', // Pink
  '#EA580C', // Orange
  '#0D9488', // Teal
];

const CARDINALITY_BADGES: Record<string, string> = {
  many_to_one: 'N:1',
  one_to_many: '1:N',
  one_to_one: '1:1',
  many_to_many: 'N:N',
};

export const RelationshipGraph: React.FC<RelationshipGraphProps> = ({
  domainId,
  sourceId,
  onInspectTableFull,
}) => {
  const chartRef = useRef<any>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  // Layout & Camera coordinate synchronization state for Minimap & Fit to View
  const [nodeCoordinates, setNodeCoordinates] = useState<Map<string, [number, number]>>(new Map());
  const [cameraView, setCameraView] = useState<CameraViewState | null>(null);

  // Data state
  const [data, setData] = useState<DomainGraphResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'approved' | 'draft'>('all');
  const [minConfidence, setMinConfidence] = useState<number>(0);
  const [tableFilterMode, setTableFilterMode] = useState<TableFilterMode>('all');
  const [connectedScope, setConnectedScope] = useState<ConnectedScope>('all');
  const [isSearchFocused, setIsSearchFocused] = useState<boolean>(false);

  // Derived flag for backward compatibility
  const hideIsolated = tableFilterMode === 'related';

  // Camera Zoom Level
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  // Phase 3: Focal / Ego-Graph mode
  const [focalTableId, setFocalTableId] = useState<string | null>(null);
  const [focalHops, setFocalHops] = useState<1 | 2>(1);

  // Phase 4: Shortest Join Path Finder
  const [isPathFinderOpen, setIsPathFinderOpen] = useState<boolean>(false);
  const [pathFinderSourceId, setPathFinderSourceId] = useState<string | null>(null);
  const [highlightedPathTableIds, setHighlightedPathTableIds] = useState<string[]>([]);
  const [highlightedPathEdgeIds, setHighlightedPathEdgeIds] = useState<string[]>([]);

  // Visualization Mode: 'erd' (for databases) vs 'neo4j_circle' (for git repos)
  const [viewMode, setViewMode] = useState<GraphVisualizationMode>('erd');

  // Auto-detect default view mode when graph data loads
  useEffect(() => {
    if (data?.nodes && data.nodes.length > 0) {
      const isGitRepo = data.nodes.some(
        (n) => n.source_type === 'github' || n.source_type === 'git_repo' || n.source_type === 'code_repo'
      );
      setViewMode(isGitRepo ? 'neo4j_circle' : 'erd');
    }
  }, [data]);

  // Inspector Drawer state
  const [selectedNode, setSelectedNode] = useState<DomainGraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<DomainGraphEdge | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [isReviewing, setIsReviewing] = useState<boolean>(false);

  // Fetch graph data from backend
  const loadGraph = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const url = sourceId
        ? `/domains/${domainId}/graph?source_id=${sourceId}`
        : `/domains/${domainId}/graph`;
      const res = await fetchApi(url);
      setData(res);
    } catch (err: any) {
      console.error('Failed to load relationship graph:', err);
      setError(err?.message || 'Failed to load domain relationship graph.');
    } finally {
      setLoading(false);
    }
  }, [domainId, sourceId]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Map of unique sources and assigned colors
  const sourcesMap = useMemo(() => {
    if (!data?.nodes) return new Map<string, { name: string; color: string }>();
    const map = new Map<string, { name: string; color: string }>();
    let colorIdx = 0;
    data.nodes.forEach((n) => {
      if (!map.has(n.source_id)) {
        map.set(n.source_id, {
          name: n.source_name || 'Unknown',
          color: SOURCE_PALETTE[colorIdx % SOURCE_PALETTE.length],
        });
        colorIdx++;
      }
    });
    return map;
  }, [data]);

  // Quick lookup table_id -> DomainGraphNode
  const nodesMap = useMemo(() => {
    const map = new Map<string, DomainGraphNode>();
    if (data?.nodes) {
      data.nodes.forEach((n) => map.set(n.id, n));
    }
    return map;
  }, [data]);

  // Node degree map (number of relationships connected to each table)
  const nodeDegreeMap = useMemo(() => {
    const map = new Map<string, number>();
    if (!data?.edges) return map;
    data.edges.forEach((e) => {
      map.set(e.source_table_id, (map.get(e.source_table_id) || 0) + 1);
      map.set(e.target_table_id, (map.get(e.target_table_id) || 0) + 1);
    });
    return map;
  }, [data]);

  // Count how many nodes have degree <= 1 (standalone / leaf tables)
  const isolatedCount = useMemo(() => {
    if (!data?.nodes) return 0;
    return data.nodes.filter((n) => (nodeDegreeMap.get(n.id) || 0) <= 1).length;
  }, [data, nodeDegreeMap]);

  // Search matches for quick suggestions dropdown & auto-pan
  const searchMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || !data?.nodes) return [];
    return data.nodes
      .filter(
        (n) =>
          n.table_name.toLowerCase().includes(q) ||
          (n.business_name || '').toLowerCase().includes(q) ||
          n.columns.some((c) => c.column_name.toLowerCase().includes(q))
      )
      .slice(0, 6);
  }, [searchQuery, data]);

  // Focal neighborhood computation (Phase 3)
  const focalInfo = useMemo(() => {
    if (!focalTableId || !data?.edges) return null;
    return getFocalNeighborhood(data.edges, focalTableId, focalHops);
  }, [focalTableId, focalHops, data]);

  const focalNode = useMemo(() => {
    if (!focalTableId || !data?.nodes) return null;
    return data.nodes.find((n) => n.id === focalTableId) || null;
  }, [focalTableId, data]);

  // BFS Connected Component traversal for selected table (O(V+E) memoized computation)
  const connectedTableIds = useMemo(() => {
    if (tableFilterMode !== 'connected' || !selectedNode || !data?.edges) {
      return null;
    }
    const maxHops = connectedScope === 'direct' ? 1 : undefined;
    return getConnectedTableIds(selectedNode.id, data.edges, maxHops);
  }, [tableFilterMode, selectedNode?.id, data?.edges, connectedScope]);

  // Semantic Zoom Macro check
  const isMacroView = zoomLevel < 0.55;

  // Filtered nodes and edges
  const { filteredNodes, filteredEdges } = useMemo(() => {
    if (!data) return { filteredNodes: [], filteredEdges: [] };

    // 1. Determine base candidate nodes by TableFilterMode
    let baseNodes: DomainGraphNode[] = [];

    if (tableFilterMode === 'all') {
      // Mode A: Show all authorized tables (including isolated)
      baseNodes = data.nodes;
    } else if (tableFilterMode === 'related') {
      // Mode B: Related tables only (degree > 0 in incoming or outgoing direction)
      baseNodes = data.nodes.filter((node) => (nodeDegreeMap.get(node.id) || 0) > 0);
    } else if (tableFilterMode === 'connected') {
      // Mode C: Connected to selected table
      if (!selectedNode || !connectedTableIds) {
        // Explicit empty state: no tables visible until a table is selected
        baseNodes = [];
      } else {
        baseNodes = data.nodes.filter((node) => connectedTableIds.has(node.id));
      }
    }

    // 2. Filter Nodes with focal mode & search query
    const q = searchQuery.trim().toLowerCase();
    const nodes = baseNodes.filter((node) => {
      // Focal Mode filter (Phase 3)
      if (focalInfo && !focalInfo.visibleNodeIds.has(node.id)) {
        return false;
      }

      // Search filter
      if (q) {
        const matchesName = node.table_name.toLowerCase().includes(q);
        const matchesBiz = (node.business_name || '').toLowerCase().includes(q);
        const matchesCol = node.columns.some((c) => c.column_name.toLowerCase().includes(q));
        if (!matchesName && !matchesBiz && !matchesCol) {
          return false;
        }
      }
      return true;
    });

    const visibleNodeIds = new Set(nodes.map((n) => n.id));

    // 3. Filter Edges (strictly drop orphan edges)
    const edges = data.edges.filter((edge) => {
      if (!visibleNodeIds.has(edge.source_table_id) || !visibleNodeIds.has(edge.target_table_id)) {
        return false;
      }
      if (statusFilter !== 'all' && edge.status !== statusFilter) {
        return false;
      }
      if (edge.confidence < minConfidence) {
        return false;
      }
      return true;
    });

    return { filteredNodes: nodes, filteredEdges: edges };
  }, [
    data,
    tableFilterMode,
    connectedScope,
    selectedNode,
    connectedTableIds,
    searchQuery,
    statusFilter,
    minConfidence,
    nodeDegreeMap,
    focalInfo,
  ]);

  // Review relationship handler (Approve / Reject)
  const handleReviewRelationship = async (
    relationshipId: string,
    action: 'approve' | 'reject',
    cardinality?: string
  ) => {
    try {
      setIsReviewing(true);
      await fetchApi(`/metadata/relationships/${relationshipId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, cardinality }),
      });

      // Optimistically update local graph state
      setData((prev) => {
        if (!prev) return prev;
        let newEdges = [...prev.edges];
        if (action === 'reject') {
          newEdges = newEdges.filter((e) => e.relationship_id !== relationshipId);
        } else {
          newEdges = newEdges.map((e) => {
            if (e.relationship_id === relationshipId) {
              return {
                ...e,
                status: 'approved',
                cardinality: cardinality || e.cardinality,
              };
            }
            return e;
          });
        }
        return {
          ...prev,
          edges: newEdges,
          total_edges: newEdges.length,
        };
      });

      // Update currently inspected edge if still selected
      if (selectedEdge && selectedEdge.relationship_id === relationshipId) {
        if (action === 'reject') {
          setIsDrawerOpen(false);
          setSelectedEdge(null);
        } else {
          setSelectedEdge((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'approved',
                  cardinality: cardinality || prev.cardinality,
                }
              : null
          );
        }
      }
    } catch (err: any) {
      console.error('Failed to review relationship:', err);
      alert(err?.message || 'Failed to submit review for this relationship.');
    } finally {
      setIsReviewing(false);
    }
  };

  // Search auto-pan & highlight handler
  const handleSelectTableFromSearch = (node: DomainGraphNode) => {
    if (tableFilterMode === 'related' && (nodeDegreeMap.get(node.id) || 0) <= 0) {
      setTableFilterMode('all');
    }
    setSearchQuery(node.table_name);
    setSelectedNode(node);
    setSelectedEdge(null);
    setIsDrawerOpen(true);
    setIsSearchFocused(false);

    setTimeout(() => {
      if (chartRef.current) {
        const instance = chartRef.current.getEchartsInstance();
        const nodeIndex = filteredNodes.findIndex((n) => n.id === node.id);
        if (nodeIndex !== -1) {
          instance.dispatchAction({
            type: 'focusNodeAdjacency',
            seriesIndex: 0,
            dataIndex: nodeIndex,
          });
        }
      }
    }, 60);
  };

  // Build ECharts option
  const chartOption = useMemo(() => {
    if (!data) return {};

    const isErd = viewMode === 'erd';
    const isPathActive = highlightedPathTableIds.length > 0;
    const isFocalActive = Boolean(focalTableId && focalInfo);

    // Compute deterministic radial positions if in focal mode
    const radialPositions = isFocalActive
      ? computeDeterministicRadialPositions(focalTableId!, filteredNodes, filteredEdges, focalHops)
      : null;

    // Density-aware force layout parameters for global overview
    const forceParams = calculateDensityAwareForceParams(filteredNodes.length, filteredEdges.length);

    // 1. Transform nodes according to viewMode
    const echartsNodes = filteredNodes.map((n) => {
      const srcMeta = sourcesMap.get(n.source_id);
      const color = srcMeta?.color || '#4F46E5';
      const isPathNode = highlightedPathTableIds.includes(n.id);
      const isFocalRoot = n.id === focalTableId;
      const unrevealedJoins = focalInfo?.unrevealedCounts.get(n.id) || 0;

      if (isErd) {
        // =========================================================================
        // ERD TABLE CARD NODE (for Relational Databases)
        // Supports Phase 2 Semantic Zoom LOD: Macro Pills vs Micro ERD Cards
        // =========================================================================
        const tableNameDisplay =
          n.table_name.length > 20 ? `${n.table_name.slice(0, 18)}…` : n.table_name;
        const rowCountDisplay = `${(n.row_count || 0).toLocaleString()} rows`;

        if (isMacroView) {
          // -----------------------------------------------------------------------
          // TIER 1: MACRO VIEW (Compact Pill 160px × 36px)
          // -----------------------------------------------------------------------
          return {
            id: n.id,
            name: n.id,
            value: n.row_count || 0,
            symbol: 'roundRect',
            symbolSize: [160, 36],
            itemStyle: {
              color: isFocalRoot ? '#312E81' : isPathNode ? '#064E3B' : '#1E293B',
              borderColor: isFocalRoot ? '#F59E0B' : isPathNode ? '#10B981' : color,
              borderWidth: isFocalRoot || isPathNode ? 3 : 2,
              borderRadius: 6,
              shadowBlur: isFocalRoot || isPathNode ? 18 : 10,
              shadowColor: isFocalRoot
                ? 'rgba(245, 158, 11, 0.5)'
                : isPathNode
                ? 'rgba(16, 185, 129, 0.5)'
                : 'rgba(0, 0, 0, 0.15)',
              opacity: isPathActive && !isPathNode ? 0.2 : 1,
            },
            label: {
              show: true,
              position: 'inside',
              formatter: `{hdrTitle| ${tableNameDisplay}} {hdrCount|${rowCountDisplay}}`,
              rich: {
                hdrTitle: {
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: '#FFFFFF',
                  width: 90,
                  align: 'left',
                },
                hdrCount: {
                  fontSize: 8,
                  color: 'rgba(255, 255, 255, 0.7)',
                  width: 50,
                  align: 'right',
                },
              },
            },
            tooltip: {
              formatter: () => `
                <div style="font-family: var(--font-sans); padding: 4px; font-size: 12px;">
                  <div style="font-weight: 700; color: #1E293B;"> ${n.table_name}</div>
                  <div style="color: #64748B; font-size: 11px;">Schema: ${n.schema_name} • ${n.source_name}</div>
                  <div style="color: #64748B; font-size: 11px;">Columns: ${n.column_count} • Rows: ${(n.row_count || 0).toLocaleString()}</div>
                </div>
              `,
            },
            nodeData: n,
          };
        }

        // -----------------------------------------------------------------------
        // TIER 2: MICRO VIEW (Detailed ERD Card with columns & keys)
        // -----------------------------------------------------------------------
        const sortedCols = [...n.columns].sort((a, b) => {
          if (a.is_primary_key && !b.is_primary_key) return -1;
          if (!a.is_primary_key && b.is_primary_key) return 1;
          if (a.is_foreign_key && !b.is_foreign_key) return -1;
          if (!a.is_foreign_key && b.is_foreign_key) return 1;
          return 0;
        });

        const visibleCols = sortedCols.slice(0, 5);
        const hasMore = n.column_count > 5;
        const cardHeight = Math.max(80, 40 + visibleCols.length * 19 + (hasMore || unrevealedJoins > 0 ? 20 : 0) + 14);
        const cardWidth = 220;

        // Format column lines
        const colLines = visibleCols.map((c) => {
          const badgeKey = c.is_primary_key ? 'pk' : c.is_foreign_key ? 'fk' : 'colDot';
          const badgeText = c.is_primary_key ? 'PK' : c.is_foreign_key ? 'FK' : '•';
          const colName =
            c.column_name.length > 15 ? `${c.column_name.slice(0, 14)}…` : c.column_name;
          const dataType = (c.data_type || '').toLowerCase();
          const typeShort = dataType.length > 9 ? `${dataType.slice(0, 8)}…` : dataType;
          return `{${badgeKey}|${badgeText}} {colName|${colName}} {colType|${typeShort}}`;
        });

        if (unrevealedJoins > 0) {
          colLines.push(`{focalBadge|+ ${unrevealedJoins} more joins available}`);
        } else if (hasMore) {
          colLines.push(`{more|+ ${n.column_count - 5} more columns...}`);
        }

        const cardContent = [
          `{hdrTitle| ${tableNameDisplay}} {hdrCount|${rowCountDisplay}}`,
          `{hr|}`,
          colLines.join('\n'),
        ].join('\n');

        return {
          id: n.id,
          name: n.id,
          value: n.row_count || 0,
          symbol: 'roundRect',
          symbolSize: [cardWidth, cardHeight],
          itemStyle: {
            color: isFocalRoot ? '#1E1B4B' : isPathNode ? '#064E3B' : '#1E293B',
            borderColor: isFocalRoot ? '#F59E0B' : isPathNode ? '#10B981' : color,
            borderWidth: isFocalRoot || isPathNode ? 3 : 2,
            borderRadius: 8,
            shadowBlur: isFocalRoot || isPathNode ? 18 : 10,
            shadowColor: isFocalRoot
              ? 'rgba(245, 158, 11, 0.45)'
              : isPathNode
              ? 'rgba(16, 185, 129, 0.5)'
              : 'rgba(0, 0, 0, 0.15)',
            opacity: isPathActive && !isPathNode ? 0.15 : 1,
          },
          label: {
            show: true,
            position: 'inside',
            formatter: cardContent,
            rich: {
              hdrTitle: {
                fontSize: 11,
                fontWeight: 700,
                color: isFocalRoot ? '#FDE68A' : isPathNode ? '#A7F3D0' : '#FFFFFF',
                width: 125,
                align: 'left',
              },
              hdrCount: {
                fontSize: 8.5,
                color: 'rgba(255, 255, 255, 0.7)',
                width: 65,
                align: 'right',
              },
              hr: {
                borderColor: 'rgba(255, 255, 255, 0.18)',
                width: '100%',
                borderWidth: 1,
                height: 0,
                margin: [3, 0],
              },
              pk: {
                backgroundColor: '#FEF3C7',
                color: '#B45309',
                borderRadius: 3,
                padding: [1, 3],
                fontSize: 8,
                fontWeight: 800,
                align: 'center',
              },
              fk: {
                backgroundColor: '#DBEAFE',
                color: '#1D4ED8',
                borderRadius: 3,
                padding: [1, 3],
                fontSize: 8,
                fontWeight: 800,
                align: 'center',
              },
              colDot: {
                color: 'rgba(255, 255, 255, 0.35)',
                fontSize: 9,
                padding: [0, 2],
                align: 'center',
              },
              colName: {
                fontSize: 9.5,
                color: '#F1F5F9',
                fontWeight: 600,
                width: 105,
                align: 'left',
              },
              colType: {
                fontSize: 8.5,
                color: '#94A3B8',
                fontFamily: 'monospace',
                width: 55,
                align: 'right',
              },
              focalBadge: {
                backgroundColor: '#3730A3',
                color: '#E0E7FF',
                borderRadius: 3,
                padding: [1, 5],
                fontSize: 8.5,
                fontWeight: 700,
                align: 'center',
              },
              more: {
                fontSize: 8.5,
                color: '#94A3B8',
                fontStyle: 'italic',
                align: 'center',
                padding: [2, 0, 0, 0],
              },
            },
          },
          tooltip: {
            formatter: () => `
              <div style="font-family: var(--font-sans); padding: 4px; font-size: 12px;">
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 2px;">${n.table_name}</div>
                <div style="color: #64748B; font-size: 11px;">Schema: ${n.schema_name}</div>
                <div style="color: #64748B; font-size: 11px;">Source: ${n.source_name}</div>
                <div style="color: #64748B; font-size: 11px;">Total Columns: ${n.column_count}</div>
                <div style="color: #64748B; font-size: 11px;">Total Rows: ${(n.row_count || 0).toLocaleString()}</div>
                ${isFocalRoot ? '<div style="color: #F59E0B; font-weight: 700; margin-top: 4px;">🎯 Focal Table (Root)</div>' : ''}
                ${isPathNode ? '<div style="color: #10B981; font-weight: 700; margin-top: 4px;">⚡ On Shortest Join Path</div>' : ''}
              </div>
            `,
          },
          nodeData: n,
        };
      } else {
        // =========================================================================
        // NEO4J CIRCULAR NODE (for Git Repos / Topology View)
        // Degree-aware sizing (34-48px), inside centered labels, zoom LOD
        // =========================================================================
        const deg = nodeDegreeMap.get(n.id) || 0;
        const circleSize = isFocalRoot
          ? 52
          : Math.min(48, Math.max(34, Math.round(34 + Math.log2(deg + 1) * 3.5)));
        const insideLabel = formatInsideNodeLabel(n.table_name, circleSize);

        const nodeItem: any = {
          id: n.id,
          name: n.id,
          value: Math.max(1, deg),
          symbol: 'circle',
          symbolSize: circleSize,
          itemStyle: {
            color: isFocalRoot ? '#F59E0B' : isPathNode ? '#10B981' : color,
            borderColor: '#FFFFFF',
            borderWidth: isFocalRoot || isPathNode ? 3 : 2,
            shadowBlur: isFocalRoot || isPathNode ? 14 : 6,
            shadowColor: isFocalRoot
              ? 'rgba(245, 158, 11, 0.5)'
              : isPathNode
              ? 'rgba(16, 185, 129, 0.5)'
              : 'rgba(0, 0, 0, 0.16)',
            opacity: isPathActive && !isPathNode ? 0.2 : 1,
          },
          label: {
            show: true,
            position: 'inside',
            align: 'center',
            verticalAlign: 'middle',
            formatter: insideLabel,
            fontSize: circleSize >= 48 ? 10.5 : circleSize >= 38 ? 9.5 : 8.5,
            fontWeight: 600,
            color: '#FFFFFF',
            textShadowColor: 'rgba(0, 0, 0, 0.75)',
            textShadowBlur: 3,
            overflow: 'truncate',
            ellipsis: '…',
          },
          labelLayout: {
            hideOverlap: true,
            moveOverlap: 'shiftY',
          },
          tooltip: {
            formatter: () => `
              <div style="font-family: var(--font-sans); padding: 4px; font-size: 12px;">
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 2px;">${n.table_name}</div>
                <div style="color: #64748B; font-size: 11px;">Schema: ${n.schema_name}</div>
                <div style="color: #64748B; font-size: 11px;">Source: ${n.source_name}</div>
                <div style="color: #64748B; font-size: 11px;">Degree: ${deg} connections</div>
                <div style="color: #64748B; font-size: 11px;">Columns: ${n.column_count}</div>
                <div style="color: #64748B; font-size: 11px;">Rows: ${(n.row_count || 0).toLocaleString()}</div>
                ${isFocalRoot ? '<div style="color: #F59E0B; font-weight: 700; margin-top: 4px;">🎯 Focal Table (Center)</div>' : ''}
                ${isPathNode ? '<div style="color: #10B981; font-weight: 700; margin-top: 4px;">⚡ On Shortest Join Path</div>' : ''}
              </div>
            `,
          },
          nodeData: n,
        };

        // If in deterministic radial focal layout, set exact x and y
        if (isFocalActive && radialPositions && radialPositions.has(n.id)) {
          const pt = radialPositions.get(n.id)!;
          nodeItem.x = pt[0];
          nodeItem.y = pt[1];
          nodeItem.fixed = true;
        }

        return nodeItem;
      }
    });

    // 2. Transform links according to viewMode & parallel edge fanout
    const echartsLinks = filteredEdges.map((e) => {
      const isDraft = e.status === 'draft';
      const badge = CARDINALITY_BADGES[e.cardinality] || e.cardinality;
      const strokeColor = isDraft ? '#F59E0B' : '#4F46E5';
      const isPathEdge = highlightedPathEdgeIds.includes(e.id);
      const isSelfLoop = e.source_table_id === e.target_table_id;

      return {
        id: e.id,
        source: e.source_table_id,
        target: e.target_table_id,
        cardinalityBadge: badge,
        ignoreForceLayout: isSelfLoop ? true : undefined,
        lineStyle: {
          color: isPathActive ? (isPathEdge ? '#10B981' : strokeColor) : strokeColor,
          width: isPathActive && isPathEdge ? 4 : Math.max(1.5, Math.min(3, (e.confidence || 0.8) * 2.2)),
          type: isPathActive && isPathEdge ? 'solid' : isDraft ? 'dashed' : 'solid',
          // Explicit curveness for self-loops; omit curveness on regular links so autoCurveness fans parallels
          curveness: isSelfLoop ? 0.65 : undefined,
          opacity: isPathActive ? (isPathEdge ? 1 : 0.08) : 0.8,
        },
        edgeLabel: {
          show: !isMacroView,
          formatter: badge,
          fontSize: 9,
          fontWeight: 700,
          color: isPathActive && isPathEdge ? '#065F46' : strokeColor,
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          padding: [1.5, 4],
          borderRadius: 6,
          borderColor: isPathActive && isPathEdge ? '#10B981' : isDraft ? '#FDE68A' : '#BFDBFE',
          borderWidth: 1,
        },
        tooltip: {
          formatter: () => `
            <div style="font-family: var(--font-sans); padding: 4px; font-size: 12px;">
              <div style="font-weight: 700; color: #1E293B;">
                ${e.source_column_name} &rarr; ${e.target_column_name}
              </div>
              <div style="color: #64748B; font-size: 11px; margin-top: 2px;">
                Cardinality: <b>${badge}</b>
              </div>
              <div style="color: #64748B; font-size: 11px;">
                Status: <span style="text-transform: capitalize; color: ${isDraft ? '#D97706' : '#16A34A'}; font-weight: 600;">${e.status}</span>
              </div>
              <div style="color: #64748B; font-size: 11px;">
                Confidence: ${(e.confidence * 100).toFixed(0)}%
              </div>
              <div style="color: #64748B; font-size: 11px;">
                Method: ${e.relationship_source}
              </div>
              ${isSelfLoop ? '<div style="color: #8B5CF6; font-weight: 700; margin-top: 4px;">🔄 Self-Referencing Foreign Key</div>' : ''}
              ${isPathEdge ? '<div style="color: #10B981; font-weight: 700; margin-top: 4px;">⚡ Active Shortest Join Hop</div>' : ''}
            </div>
          `,
        },
        edgeData: e,
      };
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255, 255, 255, 0.98)',
        borderColor: '#E2E8F0',
        borderWidth: 1,
        shadowBlur: 10,
        shadowColor: 'rgba(0, 0, 0, 0.08)',
        textStyle: { color: '#1E293B' },
      },
      series: [
        {
          type: 'graph',
          layout: isFocalActive ? 'none' : 'force',
          data: echartsNodes,
          links: echartsLinks,
          center: isFocalActive ? [0, 0] : ['50%', '50%'],
          zoom: 1,
          roam: true,
          draggable: true,
          focusNodeAdjacency: true,
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: 8,
          animation: false,
          autoCurveness: [0, 0.22, -0.22, 0.40, -0.40],
          force: {
            initLayout: 'circular',
            repulsion: isErd ? 2600 : forceParams.repulsion,
            edgeLength: isErd ? [180, 280] : forceParams.edgeLength,
            gravity: isErd ? 0.02 : forceParams.gravity,
            friction: 0.5,
            layoutAnimation: false,
          },
          labelLayout: {
            hideOverlap: true,
            moveOverlap: 'shiftY',
          },
          emphasis: {
            focus: 'adjacency',
            blurScope: 'coordinateSystem',
            lineStyle: {
              width: 4,
            },
            itemStyle: {
              shadowBlur: 14,
              shadowColor: 'rgba(79, 70, 229, 0.4)',
            },
          },
          blur: {
            itemStyle: {
              opacity: 0.12,
            },
            lineStyle: {
              opacity: 0.05,
            },
            label: {
              opacity: 0.18,
            },
            edgeLabel: {
              opacity: 0,
            },
          },
        },
      ],
    };
  }, [
    filteredNodes,
    filteredEdges,
    sourcesMap,
    viewMode,
    isMacroView,
    highlightedPathTableIds,
    highlightedPathEdgeIds,
    focalTableId,
    focalHops,
    focalInfo,
    nodeDegreeMap,
  ]);

  // Click on chart elements (Nodes or Edges)
  const onChartClick = (params: any) => {
    if (params.dataType === 'node' && params.data?.nodeData) {
      setSelectedNode(params.data.nodeData);
      setSelectedEdge(null);
      setIsDrawerOpen(true);
      if (chartRef.current) {
        chartRef.current.getEchartsInstance()?.dispatchAction({
          type: 'focusNodeAdjacency',
          seriesIndex: 0,
          dataIndex: params.dataIndex,
        });
      }
    } else if (params.dataType === 'edge' && params.data?.edgeData) {
      setSelectedEdge(params.data.edgeData);
      setSelectedNode(null);
      setIsDrawerOpen(true);
    }
  };

  // Synchronize ECharts layout coordinates & camera view for Minimap & Fit-to-View
  const syncGraphState = useCallback(() => {
    if (!chartRef.current) return;
    const instance = chartRef.current.getEchartsInstance?.();
    if (!instance) return;

    try {
      const seriesModel = instance.getModel?.()?.getSeriesByIndex?.(0);
      if (!seriesModel) return;

      const data = seriesModel.getData?.();
      if (!data) return;

      const coords = new Map<string, [number, number]>();
      const count = data.count();
      for (let i = 0; i < count; i++) {
        const layout = data.getItemLayout(i);
        const raw = data.getRawDataItem(i);
        const id = raw?.id || raw?.name;
        if (id && layout && !isNaN(layout[0]) && !isNaN(layout[1])) {
          coords.set(id, [layout[0], layout[1]]);
        }
      }

      if (coords.size > 0) {
        setNodeCoordinates((prev) => {
          if (prev.size === coords.size && prev.size > 0) {
            let changed = false;
            for (const [id, pt] of coords.entries()) {
              const oldPt = prev.get(id);
              if (!oldPt || Math.hypot(oldPt[0] - pt[0], oldPt[1] - pt[1]) > 3) {
                changed = true;
                break;
              }
            }
            if (!changed) return prev;
          }
          return coords;
        });
      }

      const coordSys = seriesModel.coordinateSystem;
      const dom = instance.getDom();
      const viewportWidth = dom?.clientWidth || 800;
      const viewportHeight = dom?.clientHeight || 600;

      let zoom = 1;
      let centerX = viewportWidth / 2;
      let centerY = viewportHeight / 2;

      if (coordSys) {
        if (typeof coordSys.getZoom === 'function') {
          zoom = coordSys.getZoom();
        }
        if (typeof coordSys.getCenter === 'function') {
          const c = coordSys.getCenter();
          if (c && !isNaN(c[0]) && !isNaN(c[1])) {
            centerX = c[0];
            centerY = c[1];
          }
        }
      } else {
        const opt = instance.getOption();
        zoom = opt?.series?.[0]?.zoom || 1;
        const c = opt?.series?.[0]?.center;
        if (Array.isArray(c) && !isNaN(c[0]) && !isNaN(c[1])) {
          centerX = c[0];
          centerY = c[1];
        }
      }

      setCameraView((prev) => {
        if (
          prev &&
          Math.abs(prev.centerX - centerX) < 1.5 &&
          Math.abs(prev.centerY - centerY) < 1.5 &&
          Math.abs(prev.zoom - zoom) < 0.02 &&
          prev.viewportWidth === viewportWidth &&
          prev.viewportHeight === viewportHeight
        ) {
          return prev;
        }
        return { centerX, centerY, zoom, viewportWidth, viewportHeight };
      });

      setZoomLevel((prev) => (Math.abs(prev - zoom) > 0.05 ? zoom : prev));
    } catch {
      // Internal ECharts transition safeguard
    }
  }, []);

  // Zoom roaming listener (Phase 2 Semantic Zoom LOD & Minimap frustum sync)
  const onGraphRoam = (params: any) => {
    syncGraphState();
  };

  // Zoom helpers
  const handleZoomIn = () => {
    if (chartRef.current) {
      const instance = chartRef.current.getEchartsInstance();
      const option = instance.getOption();
      const currentZoom = option.series?.[0]?.zoom || 1;
      const nextZoom = currentZoom * 1.25;
      instance.setOption({ series: [{ zoom: nextZoom }] });
      setZoomLevel(nextZoom);
      setTimeout(syncGraphState, 30);
    }
  };

  const handleZoomOut = () => {
    if (chartRef.current) {
      const instance = chartRef.current.getEchartsInstance();
      const option = instance.getOption();
      const currentZoom = option.series?.[0]?.zoom || 1;
      const nextZoom = Math.max(0.2, currentZoom * 0.8);
      instance.setOption({ series: [{ zoom: nextZoom }] });
      setZoomLevel(nextZoom);
      setTimeout(syncGraphState, 30);
    }
  };

  // Mathematically robust Fit to View based on actual node bounding box
  const calculateGraphFit = useCallback(() => {
    if (!chartRef.current) return;
    const instance = chartRef.current.getEchartsInstance?.();
    if (!instance) return;

    const dom = instance.getDom();
    const width = dom?.clientWidth || canvasContainerRef.current?.clientWidth || 800;
    const height = dom?.clientHeight || canvasContainerRef.current?.clientHeight || 600;

    if (filteredNodes.length === 0) {
      instance.setOption({
        series: [{ center: [width / 2, height / 2], zoom: 1 }],
      });
      setZoomLevel(1);
      return;
    }

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    let count = 0;

    const seriesModel = instance.getModel?.()?.getSeriesByIndex?.(0);
    const data = seriesModel?.getData?.();

    if (data) {
      const dataCount = data.count();
      for (let i = 0; i < dataCount; i++) {
        const layout = data.getItemLayout(i);
        if (layout && !isNaN(layout[0]) && !isNaN(layout[1])) {
          minX = Math.min(minX, layout[0]);
          maxX = Math.max(maxX, layout[0]);
          minY = Math.min(minY, layout[1]);
          maxY = Math.max(maxY, layout[1]);
          count++;
        }
      }
    }

    if (count === 0 || !isFinite(minX)) {
      const defaultZoom = Math.max(0.4, Math.min(1.0, 18 / Math.sqrt(filteredNodes.length || 1)));
      instance.setOption({
        series: [{ center: ['50%', '50%'], zoom: defaultZoom }],
      });
      setZoomLevel(defaultZoom);
      return;
    }

    const graphWidth = maxX - minX;
    const graphHeight = maxY - minY;
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const padding = 60;
    const availableWidth = Math.max(100, width - padding * 2);
    const availableHeight = Math.max(100, height - padding * 2);

    const scaleX = availableWidth / Math.max(80, graphWidth);
    const scaleY = availableHeight / Math.max(80, graphHeight);
    // Cap between 0.2 and 1.0 so small graphs don't over-inflate to giant circles
    const fitZoom = Math.max(0.2, Math.min(1.0, Math.min(scaleX, scaleY)));

    instance.setOption({
      series: [
        {
          center: [centerX, centerY],
          zoom: fitZoom,
        },
      ],
    });
    setZoomLevel(fitZoom);
    setTimeout(syncGraphState, 40);
  }, [filteredNodes.length, syncGraphState]);

  const handleResetView = () => {
    calculateGraphFit();
  };

  // Interactive Minimap pan-to handler
  const handleMinimapPanTo = useCallback((targetX: number, targetY: number) => {
    if (!chartRef.current) return;
    const instance = chartRef.current.getEchartsInstance?.();
    if (!instance) return;

    const currentOption = instance.getOption?.();
    const currentZoom = currentOption?.series?.[0]?.zoom || zoomLevel || 1;

    instance.setOption({
      series: [
        {
          center: [targetX, targetY],
          zoom: currentZoom,
        },
      ],
    });
    setTimeout(syncGraphState, 30);
  }, [zoomLevel, syncGraphState]);

  // Window & container resize observer
  useEffect(() => {
    if (!canvasContainerRef.current) return;
    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chartRef.current.getEchartsInstance?.()?.resize?.();
        syncGraphState();
      }
    });
    resizeObserver.observe(canvasContainerRef.current);
    return () => resizeObserver.disconnect();
  }, [syncGraphState]);

  // Auto-fit view when switching focalTableId or entering topology view
  useEffect(() => {
    if (viewMode === 'neo4j_circle') {
      const timer = setTimeout(() => {
        calculateGraphFit();
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [viewMode, focalTableId, focalHops, calculateGraphFit]);

  // If in ERD mode (for databases), render the pixel-perfect Light-Mode Orthogonal ERD canvas!
  if (viewMode === 'erd') {
    if (loading) {
      return (
        <div
          style={{
            height: '740px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#FFFFFF',
            borderRadius: '12px',
            border: '1px solid var(--border-color, #E2E8F0)',
            gap: '12px',
          }}
        >
          <RefreshCw size={28} className="spin" style={{ color: 'var(--primary, #4F46E5)' }} />
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main, #0F172A)' }}>
            Loading Interactive Relationship Map...
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <div
          style={{
            height: '740px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#FFFFFF',
            borderRadius: '12px',
            border: '1px solid var(--border-color, #E2E8F0)',
            gap: '12px',
            padding: '24px',
            textAlign: 'center',
          }}
        >
          <AlertCircle size={32} style={{ color: 'var(--danger, #EF4444)' }} />
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--danger, #EF4444)' }}>
            {error}
          </div>
          <button
            onClick={loadGraph}
            style={{
              padding: '6px 14px',
              background: 'var(--primary, #4F46E5)',
              color: '#FFFFFF',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '12px',
            }}
          >
            Retry
          </button>
        </div>
      );
    }

    return (
      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          height: '740px',
        }}
      >
        <ErdRelationshipCanvas
          nodes={filteredNodes}
          edges={filteredEdges}
          allNodes={data?.nodes || []}
          selectedNodeId={selectedNode?.id || null}
          selectedEdgeId={selectedEdge?.id || null}
          onSelectNode={(node) => {
            setSelectedNode(node);
            if (node) {
              setSelectedEdge(null);
            }
          }}
          onSelectEdge={(edge) => {
            setSelectedEdge(edge);
            if (edge) {
              setSelectedNode(null);
            }
          }}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          filterMode={tableFilterMode}
          onChangeFilterMode={setTableFilterMode}
          connectedScope={connectedScope}
          onChangeConnectedScope={setConnectedScope}
          relatedOnly={tableFilterMode === 'related'}
          onToggleRelatedOnly={() =>
            setTableFilterMode((prev) => (prev === 'related' ? 'all' : 'related'))
          }
          viewMode={viewMode}
          onToggleViewMode={setViewMode}
          onRefresh={loadGraph}
          onFocusTable={(tableId) => {
            setFocalTableId(tableId);
          }}
          onFindPathFromTable={(tableId) => {
            setPathFinderSourceId(tableId);
            setIsPathFinderOpen(true);
          }}
          onInspectTableFull={onInspectTableFull}
          onReviewRelationship={handleReviewRelationship}
          isReviewing={isReviewing}
          workspaceName={data?.domain_name || 'Database Schema'}
        />

        {/* Shortest Join Path Finder Modal */}
        <PathFinderModal
          isOpen={isPathFinderOpen}
          onClose={() => setIsPathFinderOpen(false)}
          nodes={data?.nodes || []}
          edges={data?.edges || []}
          onHighlightPath={(pathNodes, pathEdges) => {
            setHighlightedPathTableIds(pathNodes);
            setHighlightedPathEdgeIds(pathEdges);
          }}
          onClearHighlight={() => {
            setHighlightedPathTableIds([]);
            setHighlightedPathEdgeIds([]);
          }}
          initialSourceId={pathFinderSourceId}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        height: '740px',
        background: '#FFFFFF',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: '0 2px 6px rgba(0, 0, 0, 0.04)',
      }}
    >
      {/* ========================================================================= */}
      {/* TOOLBAR CONTROLS */}
      {/* ========================================================================= */}
      <div
        style={{
          padding: '12px 18px',
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--bg-dark)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          flexWrap: 'wrap',
          zIndex: 10,
        }}
      >
        {/* Left side: Search & Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', width: '220px' }}>
            <Search
              size={14}
              style={{
                position: 'absolute',
                left: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-faint)',
              }}
            />
            <input
              type="text"
              placeholder="Search tables & columns..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setTimeout(() => setIsSearchFocused(false), 200)}
              style={{
                width: '100%',
                padding: '6px 10px 6px 30px',
                fontSize: '12px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
                outline: 'none',
              }}
            />
            {/* Search Suggestions Dropdown */}
            {isSearchFocused && searchMatches.length > 0 && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: '4px',
                  background: '#FFFFFF',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  boxShadow: '0 4px 14px rgba(0, 0, 0, 0.1)',
                  zIndex: 50,
                  overflow: 'hidden',
                  maxHeight: '220px',
                  overflowY: 'auto',
                }}
              >
                {searchMatches.map((node) => (
                  <button
                    key={node.id}
                    onMouseDown={() => handleSelectTableFromSearch(node)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '8px 10px',
                      background: 'none',
                      border: 'none',
                      borderBottom: '1px solid #F1F5F9',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: '12px',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#F8FAFC')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                      <CornerDownRight size={12} style={{ color: 'var(--primary)', flexShrink: 0 }} />
                      <span
                        style={{
                          fontWeight: 600,
                          color: 'var(--text-main)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {node.table_name}
                      </span>
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)', flexShrink: 0, marginLeft: '6px' }}>
                      {nodeDegreeMap.get(node.id) || 0} links
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Data Source Badge (Read-Only) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 10px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              fontSize: '12px',
              fontWeight: 500,
              color: 'var(--text-main)',
            }}
            title="Domain Data Source"
          >
            <Database size={14} style={{ color: 'var(--primary)' }} />
            <span>{Array.from(sourcesMap.values())[0]?.name || 'Data Source'}</span>
          </div>

          {/* Status Filter Toggle */}
          <div
            style={{
              display: 'flex',
              background: '#E2E8F0',
              borderRadius: '6px',
              padding: '2px',
            }}
          >
            {(['all', 'approved', 'draft'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setStatusFilter(mode)}
                style={{
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'capitalize',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: statusFilter === mode ? '#4F46E5' : 'transparent',
                  color: statusFilter === mode ? '#FFFFFF' : 'var(--text-muted)',
                  transition: 'all 0.15s ease',
                }}
              >
                {mode === 'all' ? 'All Links' : mode}
              </button>
            ))}
          </div>

          {/* Confidence Slider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>Min Conf:</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              style={{
                width: '76px',
                height: '6px',
                cursor: 'pointer',
                appearance: 'none',
                WebkitAppearance: 'none',
                background: `linear-gradient(to right, #4F46E5 0%, #4F46E5 ${Math.round(minConfidence * 100)}%, #E2E8F0 ${Math.round(minConfidence * 100)}%, #E2E8F0 100%)`,
                borderRadius: '9999px',
                outline: 'none',
                border: 'none',
                padding: 0,
                margin: 0,
              }}
              title={`Minimum Confidence: ${Math.round(minConfidence * 100)}%`}
            />
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-main)', minWidth: '30px' }}>
              {Math.round(minConfidence * 100)}%
            </span>
          </div>

          {/* Hide Isolated Tables Toggle */}
          <button
            onClick={() => setTableFilterMode((prev) => (prev === 'related' ? 'all' : 'related'))}
            title={
              hideIsolated
                ? 'Show all tables (including leaf/isolated tables)'
                : `Hide ${isolatedCount} leaf/standalone tables (degree <= 1)`
            }
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 600,
              borderRadius: '6px',
              border: hideIsolated ? '1px solid var(--primary)' : '1px solid var(--border-color)',
              background: hideIsolated ? 'var(--primary-light, #EEF2FF)' : 'var(--bg-card)',
              color: hideIsolated ? 'var(--primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {hideIsolated ? <EyeOff size={13} /> : <Eye size={13} />}
            <span>Hide Isolated</span>
            {isolatedCount > 0 && (
              <span
                style={{
                  fontSize: '10px',
                  padding: '1px 5px',
                  borderRadius: '10px',
                  background: hideIsolated ? 'var(--primary)' : '#E2E8F0',
                  color: hideIsolated ? '#FFFFFF' : 'var(--text-muted)',
                  fontWeight: 700,
                }}
              >
                {isolatedCount}
              </span>
            )}
          </button>

          {/* Phase 4: Shortest Join Path Finder */}
          <button
            onClick={() => setIsPathFinderOpen(true)}
            title="Find shortest join sequence between any two tables using BFS"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 600,
              borderRadius: '6px',
              border: highlightedPathTableIds.length > 0 ? '1px solid #10B981' : '1px solid var(--border-color)',
              background: highlightedPathTableIds.length > 0 ? '#ECFDF5' : 'var(--bg-card)',
              color: highlightedPathTableIds.length > 0 ? '#047857' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Zap size={13} style={{ color: highlightedPathTableIds.length > 0 ? '#10B981' : '#EAB308' }} />
            <span>Join Path</span>
            {highlightedPathTableIds.length > 0 && (
              <span
                style={{
                  fontSize: '9.5px',
                  padding: '1px 5px',
                  borderRadius: '8px',
                  background: '#10B981',
                  color: '#FFFFFF',
                  fontWeight: 700,
                }}
              >
                {highlightedPathTableIds.length}
              </span>
            )}
          </button>
        </div>

        {/* Right side: Graph Actions & Stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Stats Badge */}
          <div
            style={{
              fontSize: '12px',
              color: 'var(--text-muted)',
              padding: '4px 10px',
              borderRadius: '16px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              fontWeight: 500,
            }}
          >
            <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{filteredNodes.length}</span>{' '}
            tables •{' '}
            <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{filteredEdges.length}</span>{' '}
            relationships
          </div>

          {/* Toggle Physics */}
          {/*<button
            onClick={() => setIsPhysicsActive((prev) => !prev)}
            title={isPhysicsActive ? 'Freeze physics positions' : 'Resume layout simulation'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '5px 8px',
              background: isPhysicsActive ? 'var(--primary-light)' : 'var(--bg-card)',
              color: isPhysicsActive ? 'var(--primary)' : 'var(--text-muted)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            {isPhysicsActive ? <Pause size={13} /> : <Play size={13} />}
            <span>{isPhysicsActive ? 'Float' : 'Freeze'}</span>
          </button>*/}

          {/* Zoom In */}
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            style={{
              padding: '5px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <ZoomIn size={15} />
          </button>

          {/* Zoom Out */}
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            style={{
              padding: '5px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <ZoomOut size={15} />
          </button>

          {/* Reset View */}
          <button
            onClick={handleResetView}
            title="Fit to Screen"
            style={{
              padding: '5px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <Maximize2 size={15} />
          </button>

          {/* Refresh Graph */}
          <button
            onClick={loadGraph}
            title="Refresh Graph Data"
            style={{
              padding: '5px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
          </button>

          {/* View Mode Toggle: ERD vs Topology (Matching ERD Page styling) */}
          <div
            style={{
              display: 'flex',
              background: '#F1F5F9',
              borderRadius: '9999px',
              padding: '3px',
              border: '1px solid #E2E8F0',
              marginLeft: '6px',
            }}
          >
            <button
              onClick={() => setViewMode('erd')}
              title="Entity-Relationship Diagram View"
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
              onClick={() => setViewMode('neo4j_circle')}
              title="Neo4j Circular Topology View"
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
        </div>
      </div>

      {/* ========================================================================= */}
      {/* CANVAS CONTAINER */}
      {/* ========================================================================= */}
      <div ref={canvasContainerRef} style={{ flex: 1, position: 'relative', width: '100%', height: '100%' }}>
        {loading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255, 255, 255, 0.85)',
              zIndex: 20,
              gap: '12px',
            }}
          >
            <RefreshCw size={28} className="spin" style={{ color: 'var(--primary)' }} />
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
              Loading Interactive Relationship Graph...
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 20,
              gap: '12px',
              padding: '24px',
              textAlign: 'center',
            }}
          >
            <AlertCircle size={32} style={{ color: 'var(--danger)' }} />
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--danger)' }}>
              {error}
            </div>
            <button
              onClick={loadGraph}
              style={{
                padding: '6px 14px',
                background: 'var(--primary)',
                color: '#FFFFFF',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
              }}
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && filteredNodes.length === 0 && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              color: 'var(--text-muted)',
              fontSize: '13px',
            }}
          >
            <Layers size={32} style={{ color: 'var(--text-faint)' }} />
            <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>No matching tables found</div>
            <div>Try adjusting your search query or filters above.</div>
          </div>
        )}

        {/* Active Shortest Path Clear Banner */}
        {highlightedPathTableIds.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: '12px',
              left: '16px',
              zIndex: 25,
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 12px',
              borderRadius: '20px',
              background: 'rgba(16, 185, 129, 0.95)',
              color: '#FFFFFF',
              boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
              fontSize: '11.5px',
              fontWeight: 600,
            }}
          >
            <Zap size={13} />
            <span>Active Join Route: {highlightedPathTableIds.length} tables highlighted</span>
            <button
              onClick={() => {
                setHighlightedPathTableIds([]);
                setHighlightedPathEdgeIds([]);
              }}
              style={{
                background: 'rgba(255, 255, 255, 0.25)',
                border: 'none',
                borderRadius: '10px',
                color: '#FFFFFF',
                padding: '2px 7px',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 700,
              }}
            >
              Clear
            </button>
          </div>
        )}

        {/* Phase 3: Focal Mode Breadcrumbs Header */}
        <FocalBreadcrumbs
          focalNode={focalNode}
          focalHops={focalHops}
          onChangeHops={setFocalHops}
          onExitFocalMode={() => setFocalTableId(null)}
          visibleTableCount={filteredNodes.length}
          totalTableCount={data?.nodes?.length || 0}
        />

        {/* ECharts Canvas */}
        {!loading && !error && (
          <ReactECharts
            ref={chartRef}
            option={chartOption}
            style={{ width: '100%', height: '100%' }}
            onEvents={{
              click: onChartClick,
              graphroam: onGraphRoam,
              finished: syncGraphState,
            }}
            opts={{ renderer: 'canvas' }}
          />
        )}

        {/* Phase 5: Floating Minimap Radar */}
        {!loading && !error && filteredNodes.length > 0 && (
          <GraphMinimap
            nodes={filteredNodes}
            sourcesMap={sourcesMap}
            focalTableId={focalTableId}
            onSelectNode={handleSelectTableFromSearch}
            nodeCoordinates={nodeCoordinates}
            cameraView={cameraView}
            onPanTo={handleMinimapPanTo}
          />
        )}

        {/* Legend Overlay at bottom-left */}
        <div
          style={{
            position: 'absolute',
            bottom: '16px',
            left: '16px',
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(4px)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '10px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            fontSize: '11px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
            pointerEvents: 'none',
            zIndex: 15,
          }}
        >
          <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>Graph Legend</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '16px',
                  height: '2px',
                  background: '#4F46E5',
                  display: 'inline-block',
                }}
              />
              <span style={{ color: 'var(--text-muted)' }}>Approved (Solid)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '16px',
                  height: '0',
                  borderTop: '2px dashed #F59E0B',
                  display: 'inline-block',
                }}
              />
              <span style={{ color: 'var(--text-muted)' }}>Draft / Inferred (Dashed)</span>
            </div>
            {viewMode === 'erd' && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span
                    style={{
                      backgroundColor: '#FEF3C7',
                      color: '#B45309',
                      borderRadius: '3px',
                      padding: '1px 3px',
                      fontSize: '9px',
                      fontWeight: 800,
                    }}
                  >
                    PK
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>Primary Key</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span
                    style={{
                      backgroundColor: '#DBEAFE',
                      color: '#1D4ED8',
                      borderRadius: '3px',
                      padding: '1px 3px',
                      fontSize: '9px',
                      fontWeight: 800,
                    }}
                  >
                    FK
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>Foreign Key</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* INSPECTION SIDE DRAWER */}
      {/* ========================================================================= */}
      <RelationshipDrawer
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setSelectedNode(null);
          setSelectedEdge(null);
          if (chartRef.current) {
            chartRef.current.getEchartsInstance()?.dispatchAction({
              type: 'unfocusNodeAdjacency',
              seriesIndex: 0,
            });
          }
        }}
        selectedNode={selectedNode}
        selectedEdge={selectedEdge}
        nodesMap={nodesMap}
        onReviewRelationship={handleReviewRelationship}
        onInspectTableFull={onInspectTableFull}
        onFocusTable={(tableId) => {
          setFocalTableId(tableId);
          setIsDrawerOpen(false);
        }}
        onFindPathFromTable={(tableId) => {
          setPathFinderSourceId(tableId);
          setIsPathFinderOpen(true);
        }}
        isReviewing={isReviewing}
      />

      {/* Phase 4: Shortest Join Path Finder Modal */}
      <PathFinderModal
        isOpen={isPathFinderOpen}
        onClose={() => setIsPathFinderOpen(false)}
        nodes={data?.nodes || []}
        edges={data?.edges || []}
        onHighlightPath={(pathNodes, pathEdges) => {
          setHighlightedPathTableIds(pathNodes);
          setHighlightedPathEdgeIds(pathEdges);
        }}
        onClearHighlight={() => {
          setHighlightedPathTableIds([]);
          setHighlightedPathEdgeIds([]);
        }}
        initialSourceId={pathFinderSourceId}
      />
    </div>
  );
};
