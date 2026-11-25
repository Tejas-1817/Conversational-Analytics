import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Search,
  Filter,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  EyeOff,
  X,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';

export interface InstantFilterTableProps {
  data: any[];
  columns?: string[];
  columnTypes?: Record<string, string>;
  truncated?: boolean;
  title?: string;
  maxDisplayRows?: number;
}

export const InstantFilterTable: React.FC<InstantFilterTableProps> = ({
  data = [],
  columns: propColumns,
  columnTypes: _columnTypes = {},
  truncated = false,
  title,
}) => {
  // Infer columns from data if not provided
  const columns = useMemo(() => {
    if (propColumns && propColumns.length > 0) return propColumns;
    if (data.length > 0 && typeof data[0] === 'object' && data[0] !== null) {
      return Object.keys(data[0]);
    }
    return [];
  }, [propColumns, data]);

  // Filter & View State
  const [activeFilters, setActiveFilters] = useState<Record<string, Set<string>>>({});
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [globalSearch, setGlobalSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Column Menu state
  const [openMenuCol, setOpenMenuCol] = useState<string | null>(null);
  const [colSearchQuery, setColSearchQuery] = useState('');
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Close column menu on outside click or ESC
  useEffect(() => {
    if (!openMenuCol) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenMenuCol(null);
        setColSearchQuery('');
      }
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuCol(null);
        setColSearchQuery('');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [openMenuCol]);

  // Compute distinct values and frequency counts for each column
  const columnStats = useMemo(() => {
    const stats: Record<string, { value: string; count: number }[]> = {};
    columns.forEach((col) => {
      const counts = new Map<string, number>();
      data.forEach((row) => {
        const val = row[col];
        const key = val === null || val === undefined || val === '' ? '(Blank)' : String(val);
        counts.set(key, (counts.get(key) || 0) + 1);
      });
      const sorted = Array.from(counts.entries())
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => {
          if (a.value === '(Blank)') return 1;
          if (b.value === '(Blank)') return -1;
          return a.value.localeCompare(b.value, undefined, { numeric: true });
        });
      stats[col] = sorted;
    });
    return stats;
  }, [data, columns]);

  // Visible columns
  const visibleColumns = useMemo(
    () => columns.filter((c) => !hiddenColumns.has(c)),
    [columns, hiddenColumns]
  );

  // Filtered rows
  const filteredRows = useMemo(() => {
    return data.filter((row) => {
      // Global search across visible columns
      if (globalSearch.trim()) {
        const q = globalSearch.toLowerCase();
        const matchesGlobal = visibleColumns.some((col) =>
          String(row[col] ?? '').toLowerCase().includes(q)
        );
        if (!matchesGlobal) return false;
      }

      // Column-specific checklist filters
      for (const [col, allowedSet] of Object.entries(activeFilters)) {
        if (!allowedSet || allowedSet.size === 0) continue;
        const rawVal = row[col];
        const key = rawVal === null || rawVal === undefined || rawVal === '' ? '(Blank)' : String(rawVal);
        if (!allowedSet.has(key)) {
          return false;
        }
      }

      return true;
    });
  }, [data, globalSearch, visibleColumns, activeFilters]);

  // Sorted rows
  const sortedRows = useMemo(() => {
    if (!sortColumn) return filteredRows;
    return [...filteredRows].sort((a, b) => {
      const valA = a[sortColumn];
      const valB = b[sortColumn];
      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortDirection === 'asc' ? valA - valB : valB - valA;
      }
      return sortDirection === 'asc'
        ? String(valA).localeCompare(String(valB), undefined, { numeric: true })
        : String(valB).localeCompare(String(valA), undefined, { numeric: true });
    });
  }, [filteredRows, sortColumn, sortDirection]);

  // Pagination
  const totalPages = Math.ceil(sortedRows.length / pageSize) || 1;
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, currentPage, pageSize]);

  // Helper actions
  const handleSort = (col: string) => {
    if (sortColumn === col) {
      if (sortDirection === 'asc') setSortDirection('desc');
      else {
        setSortColumn(null);
        setSortDirection('asc');
      }
    } else {
      setSortColumn(col);
      setSortDirection('asc');
    }
  };

  const handleToggleValue = (col: string, val: string) => {
    setActiveFilters((prev) => {
      const allVals = columnStats[col]?.map((item) => item.value) || [];
      const current = prev[col] ? new Set(prev[col]) : new Set(allVals);

      if (current.has(val)) {
        current.delete(val);
      } else {
        current.add(val);
      }

      const next = { ...prev };
      // If all values are selected, no filter is needed
      if (current.size === allVals.length) {
        delete next[col];
      } else {
        next[col] = current;
      }
      return next;
    });
    setCurrentPage(1);
  };

  const handleSelectAll = (col: string) => {
    setActiveFilters((prev) => {
      const next = { ...prev };
      delete next[col];
      return next;
    });
    setCurrentPage(1);
  };

  const handleSelectNone = (col: string) => {
    setActiveFilters((prev) => ({
      ...prev,
      [col]: new Set<string>(),
    }));
    setCurrentPage(1);
  };

  const handleResetAllFilters = () => {
    setActiveFilters({});
    setHiddenColumns(new Set());
    setGlobalSearch('');
    setSortColumn(null);
    setCurrentPage(1);
  };

  const handleToggleHideColumn = (col: string) => {
    if (!hiddenColumns.has(col) && visibleColumns.length <= 1) {
      return; // Protect at least one visible column
    }
    setHiddenColumns((prev) => {
      const next = new Set(prev);
      if (next.has(col)) next.delete(col);
      else next.add(col);
      return next;
    });
    setOpenMenuCol(null);
  };

  const activeFilterCount = Object.keys(activeFilters).length;
  const isFiltered = activeFilterCount > 0 || hiddenColumns.size > 0 || Boolean(globalSearch.trim());

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border-color)',
        fontSize: '0.85rem',
      }}
      role="region"
      aria-label={title || 'Data Table with Instant Filters'}
    >
      {/* Truncation Notice */}
      {(truncated || data.length >= 10000) && (
        <div
          style={{
            padding: '0.4rem 0.85rem',
            background: 'rgba(245, 158, 11, 0.1)',
            borderBottom: '1px solid rgba(245, 158, 11, 0.25)',
            color: '#b45309',
            fontSize: '0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
          role="status"
        >
          <AlertTriangle size={14} style={{ flexShrink: 0 }} />
          <span>
            <strong>Result capped at 10,000 rows.</strong> Instant filters apply only to the rows loaded in your browser.
          </span>
        </div>
      )}

      {/* Table Toolbar */}
      <div
        style={{
          padding: '0.65rem 0.85rem',
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--bg-main)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1, minWidth: '220px' }}>
          <div style={{ position: 'relative', width: '220px', maxWidth: '100%' }}>
            <Search
              size={13}
              style={{
                position: 'absolute',
                left: '0.6rem',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
              }}
            />
            <input
              type="text"
              placeholder="Search loaded rows..."
              value={globalSearch}
              onChange={(e) => {
                setGlobalSearch(e.target.value);
                setCurrentPage(1);
              }}
              style={{
                width: '100%',
                padding: '0.35rem 0.5rem 0.35rem 1.85rem',
                fontSize: '0.8rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
              }}
              aria-label="Search loaded table rows"
            />
          </div>

          {/* Hidden Columns summary badge */}
          {hiddenColumns.size > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '99px',
                  background: 'rgba(99, 102, 241, 0.1)',
                  color: 'var(--primary)',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <EyeOff size={11} /> {hiddenColumns.size} hidden
              </span>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setHiddenColumns(new Set())}
                style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem', color: 'var(--primary)' }}
                title="Unhide all columns"
              >
                Unhide all
              </button>
            </div>
          )}
        </div>

        {/* Filter Summary & Reset Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Showing <strong>{filteredRows.length}</strong> of {data.length} records
          </span>

          {isFiltered && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleResetAllFilters}
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.75rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                color: 'var(--text-main)',
                borderRadius: 'var(--radius-sm)',
              }}
              title="Reset all filters and sorting"
            >
              <RotateCcw size={12} /> Reset filters
            </button>
          )}
        </div>
      </div>

      {/* Main Table Area */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0, position: 'relative' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            textAlign: 'left',
            fontSize: '0.825rem',
          }}
        >
          <thead
            style={{
              position: 'sticky',
              top: 0,
              zIndex: 10,
              background: 'var(--bg-main)',
              borderBottom: '1px solid var(--border-color)',
            }}
          >
            <tr>
              {visibleColumns.map((col) => {
                const isColFiltered = Boolean(activeFilters[col]);
                const isColSorted = sortColumn === col;
                const stats = columnStats[col] || [];

                return (
                  <th
                    key={col}
                    style={{
                      padding: '0.55rem 0.75rem',
                      fontWeight: 600,
                      color: isColFiltered ? 'var(--primary)' : 'var(--text-main)',
                      borderRight: '1px solid var(--border-color)',
                      whiteSpace: 'nowrap',
                      userSelect: 'none',
                      position: 'relative',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <div
                        onClick={() => handleSort(col)}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', flex: 1 }}
                        title={`Sort by ${col}`}
                      >
                        <span>{col.replace(/_/g, ' ')}</span>
                        {isColSorted ? (
                          sortDirection === 'asc' ? (
                            <ArrowUp size={12} style={{ color: 'var(--primary)' }} />
                          ) : (
                            <ArrowDown size={12} style={{ color: 'var(--primary)' }} />
                          )
                        ) : (
                          <ArrowUpDown size={11} style={{ opacity: 0.3 }} />
                        )}
                      </div>

                      {/* Filter trigger button */}
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuCol(openMenuCol === col ? null : col);
                          setColSearchQuery('');
                        }}
                        style={{
                          padding: '0.2rem',
                          borderRadius: '4px',
                          color: isColFiltered ? 'var(--primary)' : 'var(--text-muted)',
                          background: isColFiltered ? 'rgba(99, 102, 241, 0.12)' : 'transparent',
                        }}
                        aria-label={`Filter ${col}`}
                        title={`Filter ${col} values`}
                      >
                        <Filter
                          size={13}
                          style={{
                            fill: isColFiltered ? 'var(--primary)' : 'none',
                          }}
                        />
                      </button>
                    </div>

                    {/* Column Filter Dropdown Menu */}
                    {openMenuCol === col && (
                      <div
                        ref={menuRef}
                        style={{
                          position: 'absolute',
                          top: '100%',
                          right: '4px',
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius)',
                          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
                          padding: '0.6rem',
                          minWidth: '230px',
                          maxWidth: '280px',
                          zIndex: 100,
                          fontWeight: 'normal',
                          textAlign: 'left',
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.45rem', color: 'var(--text-main)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>Filter: {col.replace(/_/g, ' ')}</span>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => setOpenMenuCol(null)}
                            style={{ padding: '0.1rem' }}
                          >
                            <X size={13} />
                          </button>
                        </div>

                        {/* Search in values list */}
                        {stats.length > 5 && (
                          <div style={{ marginBottom: '0.5rem' }}>
                            <input
                              type="text"
                              placeholder="Search values..."
                              value={colSearchQuery}
                              onChange={(e) => setColSearchQuery(e.target.value)}
                              style={{
                                width: '100%',
                                padding: '0.3rem 0.5rem',
                                fontSize: '0.75rem',
                                borderRadius: '4px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--bg-main)',
                                color: 'var(--text-main)',
                              }}
                            />
                          </div>
                        )}

                        {/* Select All / Select None Controls */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.4rem', marginBottom: '0.4rem', borderBottom: '1px solid var(--border-color)', fontSize: '0.75rem' }}>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => handleSelectAll(col)}
                            style={{ padding: '0.15rem 0.35rem', fontSize: '0.75rem', color: 'var(--primary)' }}
                          >
                            Select all
                          </button>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => handleSelectNone(col)}
                            style={{ padding: '0.15rem 0.35rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}
                          >
                            Select none
                          </button>
                        </div>

                        {/* Values checklist */}
                        <div style={{ maxHeight: '160px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.2rem', marginBottom: '0.5rem' }}>
                          {stats
                            .filter((item) =>
                              item.value.toLowerCase().includes(colSearchQuery.toLowerCase().trim())
                            )
                            .map((item) => {
                              const allowedSet = activeFilters[col];
                              const isChecked = !allowedSet || allowedSet.has(item.value);

                              return (
                                <label
                                  key={item.value}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '0.25rem 0.35rem',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.78rem',
                                    background: isChecked ? 'transparent' : 'rgba(0,0,0,0.02)',
                                  }}
                                  className="hover-bg-light"
                                >
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', overflow: 'hidden', minWidth: 0 }}>
                                    <input
                                      type="checkbox"
                                      checked={isChecked}
                                      onChange={() => handleToggleValue(col, item.value)}
                                      style={{ cursor: 'pointer' }}
                                    />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-main)' }}>
                                      {item.value}
                                    </span>
                                  </div>
                                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '0.5rem', flexShrink: 0 }}>
                                    {item.count}
                                  </span>
                                </label>
                              );
                            })}
                        </div>

                        {/* Hide column option */}
                        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.4rem' }}>
                          <button
                            type="button"
                            className="btn-ghost"
                            disabled={visibleColumns.length <= 1}
                            onClick={() => handleToggleHideColumn(col)}
                            style={{
                              width: '100%',
                              justifyContent: 'flex-start',
                              padding: '0.25rem 0.4rem',
                              fontSize: '0.75rem',
                              color: visibleColumns.length <= 1 ? 'var(--text-muted)' : 'var(--text-main)',
                              opacity: visibleColumns.length <= 1 ? 0.5 : 1,
                            }}
                            title={visibleColumns.length <= 1 ? 'At least one column must remain visible' : 'Hide this column'}
                          >
                            <EyeOff size={12} style={{ marginRight: '0.4rem' }} /> Hide column
                          </button>
                        </div>
                      </div>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.length === 0 ? (
              <tr>
                <td
                  colSpan={visibleColumns.length}
                  style={{
                    padding: '2.5rem 1rem',
                    textAlign: 'center',
                    color: 'var(--text-muted)',
                  }}
                >
                  No matching records found.
                  {isFiltered && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={handleResetAllFilters}
                        style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                      >
                        Clear filters
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ) : (
              paginatedRows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  style={{
                    borderBottom: '1px solid var(--border-color)',
                    background: rIdx % 2 === 0 ? 'transparent' : 'rgba(148, 163, 184, 0.03)',
                  }}
                  className="hover-bg-light"
                >
                  {visibleColumns.map((col) => {
                    const rawVal = row[col];
                    const isBlank = rawVal === null || rawVal === undefined || rawVal === '';
                    return (
                      <td
                        key={col}
                        style={{
                          padding: '0.55rem 0.75rem',
                          borderRight: '1px solid var(--border-color)',
                          color: isBlank ? 'var(--text-muted)' : 'var(--text-main)',
                          fontStyle: isBlank ? 'italic' : 'normal',
                          whiteSpace: 'nowrap',
                          maxWidth: '240px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                        title={isBlank ? '(Blank)' : String(rawVal)}
                      >
                        {isBlank ? '(Blank)' : typeof rawVal === 'number' ? rawVal.toLocaleString() : String(rawVal)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div
        style={{
          padding: '0.5rem 0.85rem',
          borderTop: '1px solid var(--border-color)',
          background: 'var(--bg-main)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span>
            Page <strong>{currentPage}</strong> of {totalPages}
          </span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            style={{
              padding: '0.2rem 0.4rem',
              fontSize: '0.75rem',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              color: 'var(--text-main)',
            }}
            aria-label="Rows per page"
          >
            <option value={10}>10 rows</option>
            <option value={25}>25 rows</option>
            <option value={50}>50 rows</option>
            <option value={100}>100 rows</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <button
            type="button"
            className="btn-secondary"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            style={{ padding: '0.25rem 0.5rem', opacity: currentPage <= 1 ? 0.5 : 1 }}
            aria-label="Previous page"
          >
            <ChevronLeft size={13} />
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            style={{ padding: '0.25rem 0.5rem', opacity: currentPage >= totalPages ? 0.5 : 1 }}
            aria-label="Next page"
          >
            <ChevronRight size={13} />
          </button>
        </div>
      </div>
    </div>
  );
};
