import React, { useState, useMemo } from 'react';
import {
  X,
  Zap,
  ArrowRight,
  ArrowLeftRight,
  Copy,
  Check,
  Search,
  Database,
  Link2,
  Sparkles,
  AlertCircle,
} from 'lucide-react';
import type { DomainGraphNode, DomainGraphEdge } from '../types';
import { findShortestJoinPath, type ShortestPathResult } from '../helpers/graphAlgorithms';

interface PathFinderModalProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: DomainGraphNode[];
  edges: DomainGraphEdge[];
  onHighlightPath: (pathTableIds: string[], pathEdgeIds: string[]) => void;
  onClearHighlight: () => void;
  initialSourceId?: string | null;
}

export const PathFinderModal: React.FC<PathFinderModalProps> = ({
  isOpen,
  onClose,
  nodes,
  edges,
  onHighlightPath,
  onClearHighlight,
  initialSourceId,
}) => {
  const [sourceId, setSourceId] = useState<string>(initialSourceId || (nodes[0]?.id ?? ''));
  const [targetId, setTargetId] = useState<string>(nodes[1]?.id ?? (nodes[0]?.id ?? ''));
  const [copied, setCopied] = useState<boolean>(false);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  // Sync initialSourceId when opened
  React.useEffect(() => {
    if (initialSourceId && nodes.some((n) => n.id === initialSourceId)) {
      setSourceId(initialSourceId);
    }
  }, [initialSourceId, nodes]);

  // Sorted list of nodes by table name
  const sortedNodes = useMemo(() => {
    return [...nodes].sort((a, b) => a.table_name.localeCompare(b.table_name));
  }, [nodes]);

  // Compute shortest join route
  const pathResult: ShortestPathResult | null = useMemo(() => {
    if (!sourceId || !targetId || !hasSearched) return null;
    return findShortestJoinPath(nodes, edges, sourceId, targetId);
  }, [sourceId, targetId, nodes, edges, hasSearched]);

  if (!isOpen) return null;

  const handleSwap = () => {
    setSourceId(targetId);
    setTargetId(sourceId);
  };

  const handleCopySql = () => {
    if (!pathResult?.sqlJoinSnippet) return;
    navigator.clipboard.writeText(pathResult.sqlJoinSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleApplyHighlight = () => {
    if (pathResult?.found) {
      onHighlightPath(pathResult.pathTableIds, pathResult.pathEdgeIds);
      onClose();
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(15, 23, 42, 0.45)',
          backdropFilter: 'blur(3px)',
          zIndex: 110,
        }}
      />

      {/* Modal Dialog */}
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '680px',
          maxWidth: '92vw',
          maxHeight: '88vh',
          background: '#FFFFFF',
          borderRadius: '12px',
          boxShadow: '0 20px 45px rgba(0, 0, 0, 0.2)',
          zIndex: 120,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-dark, #F8FAFC)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #4F46E5, #7C3AED)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF',
              }}
            >
              <Zap size={18} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-main)' }}>
                Shortest Join Path Finder
              </div>
              <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                Find the fastest join sequence connecting any two database tables using BFS
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Selectors Row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: '#F1F5F9',
              padding: '14px',
              borderRadius: '8px',
            }}
          >
            {/* Source Table Selector */}
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
                FROM TABLE (START)
              </label>
              <select
                value={sourceId}
                onChange={(e) => {
                  setSourceId(e.target.value);
                  setHasSearched(true);
                }}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  background: '#FFFFFF',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  color: '#1E293B',
                  outline: 'none',
                }}
              >
                {sortedNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.table_name} ({n.schema_name})
                  </option>
                ))}
              </select>
            </div>

            {/* Swap Button */}
            <button
              onClick={handleSwap}
              title="Swap Start and Target tables"
              style={{
                marginTop: '18px',
                padding: '8px',
                background: '#FFFFFF',
                border: '1px solid #CBD5E1',
                borderRadius: '6px',
                cursor: 'pointer',
                color: '#4F46E5',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              <ArrowLeftRight size={16} />
            </button>

            {/* Target Table Selector */}
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
                TO TABLE (TARGET)
              </label>
              <select
                value={targetId}
                onChange={(e) => {
                  setTargetId(e.target.value);
                  setHasSearched(true);
                }}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  background: '#FFFFFF',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  color: '#1E293B',
                  outline: 'none',
                }}
              >
                {sortedNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.table_name} ({n.schema_name})
                  </option>
                ))}
              </select>
            </div>

            {/* Run Button */}
            <div style={{ alignSelf: 'flex-end' }}>
              <button
                onClick={() => setHasSearched(true)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  background: 'var(--primary, #4F46E5)',
                  color: '#FFFFFF',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '12.5px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Zap size={14} />
                <span>Find Route</span>
              </button>
            </div>
          </div>

          {/* Path Results */}
          {hasSearched && pathResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {pathResult.found ? (
                <>
                  {/* Summary Bar */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: '#EEF2FF',
                      border: '1px solid #C7D2FE',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#3730A3', fontWeight: 600 }}>
                      <Sparkles size={16} />
                      <span>
                        Route Found: <b>{pathResult.steps.length}</b> Join Hop{pathResult.steps.length !== 1 ? 's' : ''} across{' '}
                        <b>{pathResult.pathTableIds.length}</b> tables
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button
                        onClick={handleApplyHighlight}
                        style={{
                          padding: '5px 12px',
                          borderRadius: '6px',
                          background: '#4F46E5',
                          color: '#FFFFFF',
                          border: 'none',
                          fontWeight: 600,
                          fontSize: '11.5px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                        }}
                      >
                        <span>Focus Path on Canvas</span>
                        <ArrowRight size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Visual Breadcrumb Steps */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      flexWrap: 'wrap',
                      padding: '12px',
                      background: '#F8FAFC',
                      borderRadius: '8px',
                      border: '1px solid #E2E8F0',
                    }}
                  >
                    {pathResult.steps.map((step, idx) => (
                      <React.Fragment key={idx}>
                        {idx === 0 && (
                          <div
                            style={{
                              padding: '5px 10px',
                              borderRadius: '6px',
                              background: '#312E81',
                              color: '#FFFFFF',
                              fontWeight: 700,
                              fontSize: '11.5px',
                            }}
                          >
                            {step.fromTableName}
                          </div>
                        )}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748B' }}>
                          <span style={{ fontSize: '10px', fontWeight: 700, color: '#4F46E5' }}>
                            ({step.fromColumnName} = {step.toColumnName})
                          </span>
                          <ArrowRight size={14} style={{ color: '#4F46E5' }} />
                        </div>
                        <div
                          style={{
                            padding: '5px 10px',
                            borderRadius: '6px',
                            background: idx === pathResult.steps.length - 1 ? '#065F46' : '#1E293B',
                            color: '#FFFFFF',
                            fontWeight: 700,
                            fontSize: '11.5px',
                          }}
                        >
                          {step.toTableName}
                        </div>
                      </React.Fragment>
                    ))}
                  </div>

                  {/* Generated SQL JOIN Snippet */}
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '6px',
                      }}
                    >
                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                        COPYABLE SQL JOIN STATEMENT
                      </span>
                      <button
                        onClick={handleCopySql}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '4px 10px',
                          fontSize: '11px',
                          fontWeight: 600,
                          borderRadius: '5px',
                          border: '1px solid var(--border-color)',
                          background: '#FFFFFF',
                          color: copied ? '#059669' : 'var(--text-main)',
                          cursor: 'pointer',
                        }}
                      >
                        {copied ? <Check size={12} /> : <Copy size={12} />}
                        <span>{copied ? 'Copied to Clipboard!' : 'Copy SQL'}</span>
                      </button>
                    </div>

                    <pre
                      style={{
                        margin: 0,
                        padding: '12px 14px',
                        background: '#0F172A',
                        color: '#E2E8F0',
                        borderRadius: '8px',
                        fontSize: '12px',
                        fontFamily: 'Consolas, monospace',
                        lineHeight: 1.5,
                        overflowX: 'auto',
                      }}
                    >
                      <code>{pathResult.sqlJoinSnippet}</code>
                    </pre>
                  </div>
                </>
              ) : (
                <div
                  style={{
                    padding: '24px',
                    textAlign: 'center',
                    background: '#FEF2F2',
                    border: '1px solid #FECACA',
                    borderRadius: '8px',
                    color: '#991B1B',
                  }}
                >
                  <AlertCircle size={24} style={{ margin: '0 auto 8px' }} />
                  <div style={{ fontWeight: 700, fontSize: '13px' }}>No Join Path Found</div>
                  <div style={{ fontSize: '12px', marginTop: '4px', color: '#B91C1C' }}>
                    {pathResult.errorMessage || 'These two tables belong to disconnected subgraphs.'}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--border-color)',
            background: 'var(--bg-dark, #F8FAFC)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '10px',
          }}
        >
          <button
            onClick={() => {
              onClearHighlight();
              onClose();
            }}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              background: '#FFFFFF',
              color: 'var(--text-muted)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Clear Highlights & Close
          </button>
        </div>
      </div>
    </>
  );
};
