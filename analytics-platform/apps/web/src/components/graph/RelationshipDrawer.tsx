import React, { useState } from 'react';
import {
  X,
  Table as TableIcon,
  Database,
  Key,
  Link2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  Sliders,
  Layers,
  Target,
  Zap,
} from 'lucide-react';
import type { DomainGraphNode, DomainGraphEdge } from './types';
import { SourceLogo } from '../SourceLogos';

interface RelationshipDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  selectedNode: DomainGraphNode | null;
  selectedEdge: DomainGraphEdge | null;
  nodesMap: Map<string, DomainGraphNode>;
  onReviewRelationship: (
    relationshipId: string,
    action: 'approve' | 'reject',
    cardinality?: string
  ) => Promise<void>;
  onInspectTableFull?: (tableId: string) => void;
  onFocusTable?: (tableId: string) => void;
  onFindPathFromTable?: (tableId: string) => void;
  isReviewing?: boolean;
}

const CARDINALITY_OPTIONS = [
  { value: 'many_to_one', label: 'Many to One (N:1)', badge: 'N:1' },
  { value: 'one_to_many', label: 'One to Many (1:N)', badge: '1:N' },
  { value: 'one_to_one', label: 'One to One (1:1)', badge: '1:1' },
  { value: 'many_to_many', label: 'Many to Many (N:N)', badge: 'N:N' },
];

export const RelationshipDrawer: React.FC<RelationshipDrawerProps> = ({
  isOpen,
  onClose,
  selectedNode,
  selectedEdge,
  nodesMap,
  onReviewRelationship,
  onInspectTableFull,
  onFocusTable,
  onFindPathFromTable,
  isReviewing = false,
}) => {
  const [selectedCardinality, setSelectedCardinality] = useState<string>(
    selectedEdge?.cardinality || 'many_to_one'
  );
  const [columnFilter, setColumnFilter] = useState('');

  // Sync state when selected edge changes
  React.useEffect(() => {
    if (selectedEdge) {
      setSelectedCardinality(selectedEdge.cardinality || 'many_to_one');
    }
  }, [selectedEdge]);

  if (!isOpen || (!selectedNode && !selectedEdge)) {
    return null;
  }

  // Edge mode details
  const fromTable = selectedEdge ? nodesMap.get(selectedEdge.source_table_id) : null;
  const toTable = selectedEdge ? nodesMap.get(selectedEdge.target_table_id) : null;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(15, 23, 42, 0.15)',
          backdropFilter: 'blur(1px)',
          zIndex: 99,
        }}
      />
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '440px',
          maxWidth: '90vw',
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border-color)',
          boxShadow: '-8px 0 30px rgba(0, 0, 0, 0.12)',
          zIndex: 100,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
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
          background: 'var(--bg-dark)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {selectedNode ? (
            <>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '6px',
                  background: 'var(--primary-light)',
                  color: 'var(--primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <TableIcon size={17} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)' }}>
                  Table Schema
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {selectedNode.schema_name} • {selectedNode.source_name}
                </div>
              </div>
            </>
          ) : (
            <>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '6px',
                  background:
                    selectedEdge?.status === 'approved' ? 'var(--success-light)' : 'var(--warning-light)',
                  color: selectedEdge?.status === 'approved' ? 'var(--success)' : 'var(--warning)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Link2 size={17} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)' }}>
                  Relationship Inspector
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {selectedEdge?.relationship_source === 'foreign_key'
                    ? 'Declared Foreign Key'
                    : 'Inferred Association'}
                </div>
              </div>
            </>
          )}
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Close drawer"
        >
          <X size={18} />
        </button>
      </div>

      {/* Body Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {/* ========================================================================= */}
        {/* MODE 1: TABLE NODE INSPECTION */}
        {/* ========================================================================= */}
        {selectedNode && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Table Identity Card */}
            <div
              style={{
                background: 'var(--bg-page)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    fontSize: '15px',
                    color: 'var(--text-main)',
                  }}
                >
                  {selectedNode.table_name}
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: 'var(--primary-light)',
                    color: 'var(--primary)',
                    fontWeight: 600,
                  }}
                >
                  {selectedNode.row_count !== null && selectedNode.row_count !== undefined
                    ? `${selectedNode.row_count.toLocaleString()} rows`
                    : 'Unknown rows'}
                </span>
              </div>

              {selectedNode.business_name && (
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  {selectedNode.business_name}
                </div>
              )}

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  fontSize: '12px',
                  color: 'var(--text-muted)',
                  marginTop: '10px',
                  paddingTop: '10px',
                  borderTop: '1px solid var(--border-color)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Database size={13} />
                  <span>{selectedNode.source_name}</span>
                </div>
                <div>•</div>
                <div>{selectedNode.column_count} columns</div>
              </div>
            </div>

            {/* Action Buttons Row */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                {onFocusTable && (
                  <button
                    onClick={() => onFocusTable(selectedNode.id)}
                    style={{
                      flex: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      background: '#EEF2FF',
                      border: '1px solid #C7D2FE',
                      color: '#4338CA',
                      fontWeight: 600,
                      fontSize: '12px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#E0E7FF')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '#EEF2FF')}
                    title="Filter canvas to only this table and its direct connections"
                  >
                    <Target size={14} />
                    <span>Focus Table</span>
                  </button>
                )}

                {onFindPathFromTable && (
                  <button
                    onClick={() => onFindPathFromTable(selectedNode.id)}
                    style={{
                      flex: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      background: '#F0FDF4',
                      border: '1px solid #BBF7D0',
                      color: '#15803D',
                      fontWeight: 600,
                      fontSize: '12px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#DCFCE7')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '#F0FDF4')}
                    title="Find join path from this table to any other table"
                  >
                    <Zap size={14} />
                    <span>Find Join Path</span>
                  </button>
                )}
              </div>

              {/* Quick action: Inspect in Full Modal */}
              {onInspectTableFull && (
                <button
                  onClick={() => onInspectTableFull(selectedNode.table_id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'var(--bg-page)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--primary)',
                    fontWeight: 600,
                    fontSize: '12px',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--primary-light)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-page)')}
                >
                  <span>Inspect Full Details & Profiling</span>
                  <ExternalLink size={13} />
                </button>
              )}
            </div>

            {/* Column Schema Breakdown */}
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '10px',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-main)' }}>
                  Columns ({selectedNode.columns.length})
                </div>
                <input
                  type="text"
                  placeholder="Filter columns..."
                  value={columnFilter}
                  onChange={(e) => setColumnFilter(e.target.value)}
                  style={{
                    fontSize: '11px',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-page)',
                    color: 'var(--text-main)',
                    width: '140px',
                  }}
                />
              </div>

              <div
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  overflow: 'hidden',
                  background: 'var(--bg-card)',
                }}
              >
                {selectedNode.columns
                  .filter((c) =>
                    columnFilter
                      ? c.column_name.toLowerCase().includes(columnFilter.toLowerCase()) ||
                        c.data_type.toLowerCase().includes(columnFilter.toLowerCase())
                      : true
                  )
                  .map((col, idx) => (
                    <div
                      key={col.id}
                      style={{
                        padding: '8px 12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderBottom:
                          idx === selectedNode.columns.length - 1
                            ? 'none'
                            : '1px solid var(--border-color)',
                        fontSize: '12px',
                        background: col.is_primary_key
                          ? 'rgba(79, 70, 229, 0.03)'
                          : col.is_foreign_key
                          ? 'rgba(217, 119, 6, 0.03)'
                          : 'transparent',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                        {col.is_primary_key && (
                          <span
                            title="Primary Key"
                            style={{
                              color: '#D97706',
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                          >
                            <Key size={13} />
                          </span>
                        )}
                        {col.is_foreign_key && (
                          <span
                            title="Foreign Key"
                            style={{
                              color: 'var(--primary)',
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                          >
                            <Link2 size={13} />
                          </span>
                        )}
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontWeight: col.is_primary_key ? 600 : 400,
                            color: 'var(--text-main)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {col.column_name}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                        <span
                          style={{
                            fontSize: '10px',
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--text-muted)',
                            background: 'var(--bg-dark)',
                            padding: '2px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          {col.data_type}
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* MODE 2: RELATIONSHIP EDGE INSPECTION & REVIEW */}
        {/* ========================================================================= */}
        {selectedEdge && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Status & Confidence Banner */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 14px',
                borderRadius: '8px',
                background:
                  selectedEdge.status === 'approved'
                    ? 'var(--success-light)'
                    : selectedEdge.status === 'rejected'
                    ? 'var(--danger-light)'
                    : 'var(--warning-light)',
                border: `1px solid ${
                  selectedEdge.status === 'approved'
                    ? '#BBF7D0'
                    : selectedEdge.status === 'rejected'
                    ? '#FECACA'
                    : '#FDE68A'
                }`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {selectedEdge.status === 'approved' ? (
                  <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />
                ) : selectedEdge.status === 'rejected' ? (
                  <XCircle size={16} style={{ color: 'var(--danger)' }} />
                ) : (
                  <Sparkles size={16} style={{ color: 'var(--warning)' }} />
                )}
                <span
                  style={{
                    fontWeight: 600,
                    fontSize: '12.5px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    color:
                      selectedEdge.status === 'approved'
                        ? 'var(--success)'
                        : selectedEdge.status === 'rejected'
                        ? 'var(--danger)'
                        : 'var(--warning)',
                  }}
                >
                  {selectedEdge.status}
                </span>
              </div>

              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
                {Math.round(selectedEdge.confidence * 100)}% Confidence
              </div>
            </div>

            {/* Visual Join Path Diagram */}
            <div
              style={{
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '16px',
                background: 'var(--bg-page)',
              }}
            >
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  marginBottom: '12px',
                  letterSpacing: '0.5px',
                }}
              >
                Join Mapping
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Source Column */}
                <div
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    padding: '10px 12px',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>
                    Origin (Foreign Key)
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-main)' }}>
                      {fromTable?.table_name || 'Source Table'}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>.</span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12.5px',
                        color: 'var(--primary)',
                        fontWeight: 600,
                      }}
                    >
                      {selectedEdge.source_column_name}
                    </span>
                  </div>
                </div>

                {/* Arrow Connector with Cardinality */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  <div style={{ height: '1px', flex: 1, background: 'var(--border-color)' }} />
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '12px',
                      background: 'var(--primary-light)',
                      color: 'var(--primary)',
                      border: '1px solid #BFDBFE',
                    }}
                  >
                    {CARDINALITY_OPTIONS.find((c) => c.value === selectedEdge.cardinality)?.badge ||
                      selectedEdge.cardinality}
                  </span>
                  <div style={{ height: '1px', flex: 1, background: 'var(--border-color)' }} />
                </div>

                {/* Target Column */}
                <div
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    padding: '10px 12px',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>
                    Target (Primary Key)
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-main)' }}>
                      {toTable?.table_name || 'Target Table'}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>.</span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12.5px',
                        color: '#D97706',
                        fontWeight: 600,
                      }}
                    >
                      {selectedEdge.target_column_name}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Cardinality Selector */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--text-main)',
                  marginBottom: '6px',
                }}
              >
                Relationship Cardinality
              </label>
              <select
                value={selectedCardinality}
                onChange={(e) => setSelectedCardinality(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-card)',
                  color: 'var(--text-main)',
                  fontSize: '13px',
                }}
              >
                {CARDINALITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Inference Metadata & Evidence */}
            <div
              style={{
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '14px',
                background: 'var(--bg-dark)',
              }}
            >
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  marginBottom: '8px',
                }}
              >
                Detection Evidence
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-main)', marginBottom: '6px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Detection Method: </span>
                <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                  {selectedEdge.relationship_source.replace(/_/g, ' ')}
                </span>
              </div>
              {selectedEdge.evidence && Object.keys(selectedEdge.evidence).length > 0 && (
                <pre
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    padding: '8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    color: 'var(--text-muted)',
                    overflowX: 'auto',
                    margin: 0,
                  }}
                >
                  {JSON.stringify(selectedEdge.evidence, null, 2)}
                </pre>
              )}
            </div>

            {/* Action Buttons for Review */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                marginTop: '10px',
              }}
            >
              <button
                disabled={isReviewing}
                onClick={() =>
                  onReviewRelationship(selectedEdge.relationship_id, 'approve', selectedCardinality)
                }
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '10px 16px',
                  borderRadius: '6px',
                  background: '#16A34A',
                  color: '#FFFFFF',
                  fontWeight: 600,
                  fontSize: '13px',
                  border: 'none',
                  cursor: isReviewing ? 'not-allowed' : 'pointer',
                  opacity: isReviewing ? 0.7 : 1,
                  boxShadow: '0 1px 3px rgba(22, 163, 74, 0.25)',
                  transition: 'background 0.15s ease',
                }}
              >
                <CheckCircle2 size={16} />
                <span>{isReviewing ? 'Saving Review...' : 'Approve Relationship'}</span>
              </button>

              <button
                disabled={isReviewing}
                onClick={() =>
                  onReviewRelationship(selectedEdge.relationship_id, 'reject', selectedCardinality)
                }
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '9px 16px',
                  borderRadius: '6px',
                  background: 'transparent',
                  color: 'var(--danger)',
                  fontWeight: 600,
                  fontSize: '13px',
                  border: '1px solid #FECACA',
                  cursor: isReviewing ? 'not-allowed' : 'pointer',
                  opacity: isReviewing ? 0.7 : 1,
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--danger-light)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <XCircle size={16} />
                <span>Reject / Dismiss</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  );
};
