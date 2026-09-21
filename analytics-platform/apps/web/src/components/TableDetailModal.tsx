import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Table as TableIcon,
  ChevronDown,
  ChevronUp,
  Database,
  Search,
  Check,
  Columns,
  Layers,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { fetchApi } from '../services/api';

export interface TableItem {
  id: string;
  table_name: string;
  display_name?: string;
  description?: string;
  schema_name?: string;
  row_count?: number;
  column_count?: number;
  derived_columns_count?: number;
  rag_columns_count?: number;
  included?: boolean;
  columns?: any[];
}

interface TableDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  tables: TableItem[];
  currentTableIndex: number;
  onSelectTableIndex: (index: number) => void;
  domainName: string;
  sourceName: string;
  sourceId?: string | null;
}

export const TableDetailModal: React.FC<TableDetailModalProps> = ({
  isOpen,
  onClose,
  tables,
  currentTableIndex,
  onSelectTableIndex,
  domainName,
  sourceName,
  sourceId,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [tableSearch, setTableSearch] = useState('');
  const [sampleRows, setSampleRows] = useState<any[]>([]);
  const [columnsList, setColumnsList] = useState<any[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  const safeIndex = Math.max(0, Math.min(currentTableIndex, tables.length - 1));
  const currentTable = tables[safeIndex] || null;

  // Format table name into Title Case for display if needed
  const formatTitle = (name: string) => {
    if (!name) return '';
    return name
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isDropdownOpen]);

  // Handle keybindings (ArrowUp / ArrowDown / Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        if (isDropdownOpen) {
          setIsDropdownOpen(false);
        } else {
          onClose();
        }
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        if (safeIndex > 0) {
          onSelectTableIndex(safeIndex - 1);
        }
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        if (safeIndex < tables.length - 1) {
          onSelectTableIndex(safeIndex + 1);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isDropdownOpen, safeIndex, tables.length, onClose, onSelectTableIndex]);

  // Fetch table metadata / sample preview when table changes
  useEffect(() => {
    if (!isOpen || !currentTable) return;

    if (currentTable.columns && currentTable.columns.length > 0) {
      setColumnsList(currentTable.columns);
      setLoadingData(false);
      return;
    }

    setLoadingData(true);
    const loadTableDetails = async () => {
      try {
        if (currentTable.id && !currentTable.id.startsWith('sample-')) {
          const cols = await fetchApi(`/metadata/tables/${currentTable.id}/columns`);
          if (Array.isArray(cols) && cols.length > 0) {
            setColumnsList(cols);
          } else {
            setColumnsList(currentTable.columns || []);
          }
        } else {
          setColumnsList(currentTable.columns || []);
        }
      } catch {
        setColumnsList(currentTable.columns || []);
      } finally {
        setLoadingData(false);
      }
    };

    loadTableDetails();
  }, [isOpen, currentTable, sourceId]);

  if (!isOpen || !currentTable) return null;

  const filteredTables = tables.filter((t) =>
    t.table_name.toLowerCase().includes(tableSearch.toLowerCase()) ||
    (t.display_name && t.display_name.toLowerCase().includes(tableSearch.toLowerCase()))
  );

  const displayName = currentTable.display_name || formatTitle(currentTable.table_name);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(2px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        animation: 'fadeIn 0.15s ease-out',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '860px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
        }}
      >
        {/* ========================================================================= */}
        {/* 1. HEADER */}
        {/* ========================================================================= */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            padding: '20px 24px 16px',
            borderBottom: '1px solid #F1F5F9',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                background: '#F8FAFC',
                border: '1px solid #E2E8F0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#475569',
                flexShrink: 0,
                marginTop: '2px',
              }}
            >
              <TableIcon size={20} />
            </div>

            <div>
              <h2
                style={{
                  fontSize: '1.25rem',
                  fontWeight: 600,
                  color: '#1E293B',
                  margin: '0 0 4px 0',
                  letterSpacing: '-0.01em',
                }}
              >
                {displayName}
              </h2>
              <div
                style={{
                  fontSize: '13px',
                  color: '#64748B',
                  fontFamily: 'monospace',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  flexWrap: 'wrap',
                }}
              >
                <span>Part of the Domain: <strong style={{ color: '#1E293B' }}>"{domainName}"</strong></span>
                <span>Data Source: <strong style={{ color: '#1E293B' }}>"{sourceName}"</strong></span>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#94A3B8',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#1E293B';
              e.currentTarget.style.backgroundColor = '#F1F5F9';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#94A3B8';
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* ========================================================================= */}
        {/* 2. TOOLBAR: Table Dropdown Selector + Previous / Next */}
        {/* ========================================================================= */}
        <div
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid #F1F5F9',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            background: '#FFFFFF',
          }}
        >
          {/* Table Selector Dropdown */}
          <div ref={dropdownRef} style={{ position: 'relative', width: '260px' }}>
            <div
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              style={{
                position: 'relative',
                width: '100%',
                padding: '10px 14px',
                fontSize: '13px',
                borderRadius: '8px',
                border: isDropdownOpen ? '1.5px solid #6366F1' : '1px solid #CBD5E1',
                background: '#FFFFFF',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                boxSizing: 'border-box',
                userSelect: 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {/* Floating Label */}
              <span
                style={{
                  position: 'absolute',
                  top: '-8px',
                  left: '10px',
                  background: '#FFFFFF',
                  padding: '0 4px',
                  fontSize: '10.5px',
                  fontWeight: 500,
                  color: isDropdownOpen ? '#6366F1' : '#64748B',
                }}
              >
                Select from {tables.length} tables
              </span>

              <span
                style={{
                  color: '#1E293B',
                  fontWeight: 500,
                  fontFamily: 'monospace',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {displayName}
              </span>

              {isDropdownOpen ? (
                <ChevronUp size={15} style={{ color: '#64748B', flexShrink: 0 }} />
              ) : (
                <ChevronDown size={15} style={{ color: '#64748B', flexShrink: 0 }} />
              )}
            </div>

            {/* Dropdown Menu */}
            {isDropdownOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  left: 0,
                  width: '320px',
                  background: '#FFFFFF',
                  border: '1px solid #E2E8F0',
                  borderRadius: '8px',
                  boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
                  zIndex: 1000,
                  padding: '6px',
                  maxHeight: '260px',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {/* Search input in dropdown */}
                <div style={{ position: 'relative', marginBottom: '6px' }}>
                  <Search
                    size={13}
                    style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }}
                  />
                  <input
                    type="text"
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    placeholder="Search tables..."
                    autoFocus
                    style={{
                      width: '100%',
                      padding: '6px 10px 6px 26px',
                      fontSize: '12px',
                      borderRadius: '4px',
                      border: '1px solid #CBD5E1',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>

                {/* Table options list */}
                <div style={{ overflowY: 'auto', flex: 1 }}>
                  {filteredTables.map((tbl) => {
                    const originalIndex = tables.findIndex((t) => t.id === tbl.id);
                    const isSelected = originalIndex === safeIndex;
                    return (
                      <div
                        key={tbl.id}
                        onClick={() => {
                          onSelectTableIndex(originalIndex);
                          setIsDropdownOpen(false);
                          setTableSearch('');
                        }}
                        style={{
                          padding: '7px 10px',
                          fontSize: '12.5px',
                          fontFamily: 'monospace',
                          color: isSelected ? '#4F46E5' : '#334155',
                          fontWeight: isSelected ? 600 : 400,
                          background: isSelected ? '#EEF2FF' : 'transparent',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC';
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                        }}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {tbl.display_name || tbl.table_name}
                        </span>
                        {isSelected && <Check size={14} style={{ color: '#4F46E5', flexShrink: 0 }} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Previous Button */}
          <button
            onClick={() => onSelectTableIndex(Math.max(0, safeIndex - 1))}
            disabled={safeIndex === 0}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              fontSize: '13px',
              fontWeight: 500,
              color: safeIndex === 0 ? '#CBD5E1' : '#334155',
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              cursor: safeIndex === 0 ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (safeIndex > 0) e.currentTarget.style.backgroundColor = '#F8FAFC';
            }}
            onMouseLeave={(e) => {
              if (safeIndex > 0) e.currentTarget.style.backgroundColor = '#FFFFFF';
            }}
          >
            <ChevronUp size={15} />
            <span>Previous</span>
          </button>

          {/* Next Button */}
          <button
            onClick={() => onSelectTableIndex(Math.min(tables.length - 1, safeIndex + 1))}
            disabled={safeIndex >= tables.length - 1}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              fontSize: '13px',
              fontWeight: 500,
              color: safeIndex >= tables.length - 1 ? '#CBD5E1' : '#334155',
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              cursor: safeIndex >= tables.length - 1 ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (safeIndex < tables.length - 1) e.currentTarget.style.backgroundColor = '#F8FAFC';
            }}
            onMouseLeave={(e) => {
              if (safeIndex < tables.length - 1) e.currentTarget.style.backgroundColor = '#FFFFFF';
            }}
          >
            <ChevronDown size={15} />
            <span>Next</span>
          </button>
        </div>

        {/* ========================================================================= */}
        {/* 3. CONTENT BODY (Displays Columns / Schema / Preview or No Data Found) */}
        {/* ========================================================================= */}
        <div
          style={{
            padding: '48px 24px',
            minHeight: '220px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748B',
            fontSize: '14px',
            textAlign: 'center',
          }}
        >
          {loadingData ? (
            <div style={{ color: '#94A3B8' }}>Loading table details...</div>
          ) : columnsList.length > 0 ? (
            <div style={{ width: '100%', textAlign: 'left' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '8px' }}>
                COLUMNS ({columnsList.length})
              </div>
              <div
                style={{
                  border: '1px solid #E2E8F0',
                  borderRadius: '8px',
                  overflow: 'hidden',
                  maxHeight: '260px',
                  overflowY: 'auto',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.5px' }}>
                  <thead>
                    <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B' }}>
                      <th style={{ padding: '8px 12px', fontWeight: 500 }}>Column Name</th>
                      <th style={{ padding: '8px 12px', fontWeight: 500 }}>Data Type</th>
                      <th style={{ padding: '8px 12px', fontWeight: 500 }}>Key</th>
                      <th style={{ padding: '8px 12px', fontWeight: 500 }}>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {columnsList.map((c, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #F1F5F9' }}>
                        <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontWeight: 500, color: '#1E293B' }}>
                          {c.column_name || c.name || `col_${i}`}
                        </td>
                        <td style={{ padding: '8px 12px', color: '#64748B' }}>
                          {c.data_type || c.type || 'VARCHAR'}
                        </td>
                        <td style={{ padding: '8px 12px', color: '#64748B' }}>
                          {c.is_primary_key ? 'PRIMARY KEY' : c.is_foreign_key ? 'FOREIGN KEY' : '—'}
                        </td>
                        <td style={{ padding: '8px 12px', color: '#64748B' }}>
                          {c.description || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ color: '#64748B', fontWeight: 400 }}>No data found</div>
          )}
        </div>
      </div>
    </div>
  );
};
