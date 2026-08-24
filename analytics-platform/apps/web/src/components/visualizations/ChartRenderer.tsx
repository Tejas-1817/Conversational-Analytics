import React, { useState, useMemo } from 'react';
import * as echarts from 'echarts/core';
import ReactECharts from 'echarts-for-react';
import {
  TrendingUp, Users, Award, Table as TableIcon, Download, Search, ArrowUpDown, ChevronLeft, ChevronRight, AlertCircle, Layers
} from 'lucide-react';

function useThemeTokens() {
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
    return {
      textMuted: read('--text-muted', '#94a3b8'),
      textMain: read('--text-main', '#e2e8f0'),
      border: read('--border-color', 'rgba(255,255,255,0.08)'),
      cardBg: read('--bg-card', '#111827'),
    };
  }, []);
}

interface ChartProps {
  data: any;
  chartType: string;
  title?: string;
  columns?: string[];
  columnTypes?: Record<string, string>; // e.g. { revenue: 'NUMERIC', month: 'TIME_SERIES' }
}

export const vividSaasTheme = {
  categorical: ['#4ea8f2', '#e46a6f', '#f2ab65', '#eb5f89', '#859297', '#3d3d3d'],
  sequential: ['#F3E8FF', '#C4B5FD', '#8B5CF6', '#6D28D9', '#4C1D95'],
  semantic: { positive: '#10B981', negative: '#EF4444', neutral: '#9CA3AF' },
  background: '#FAFAFA',
  text: '#111827',
  grid: '#F0F0F0',
};

const COLORS = vividSaasTheme.categorical;

export const ChartRenderer: React.FC<ChartProps> = ({ data, chartType, title, columns: customColumns, columnTypes = {} }) => {
  const tokens = useThemeTokens();
  // Normalize input data into columns & rows format
  let rows: any[] = [];
  let columns: string[] = [];

  if (Array.isArray(data)) {
    rows = data;
    if (rows.length > 0 && typeof rows[0] === 'object' && rows[0] !== null) {
      columns = customColumns && customColumns.length > 0 ? customColumns : Object.keys(rows[0]);
    }
  } else if (data && typeof data === 'object') {
    if (Array.isArray(data.rows)) {
      rows = data.rows;
      columns = data.columns || (rows.length > 0 && typeof rows[0] === 'object' ? Object.keys(rows[0]) : []);
    } else if (Array.isArray(data.data)) {
      rows = data.data;
      columns = rows.length > 0 && typeof rows[0] === 'object' ? Object.keys(rows[0]) : [];
    }
  }

  // State for Table Pagination, Sorting & Filtering
  const [searchTerm, setSearchTerm] = useState('');
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Rule 7: Zero Rows -> Display "No matching records found."
  if (!rows || rows.length === 0 || columns.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        borderRadius: '12px',
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        border: '1px border-dashed var(--border-color, #2b2b40)',
        minHeight: '160px',
        textAlign: 'center'
      }}>
        <AlertCircle size={32} style={{ color: 'var(--text-muted, #94a3b8)', marginBottom: '0.75rem' }} />
        <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-main, #f8fafc)' }}>
          No matching records found.
        </h4>
        <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted, #94a3b8)' }}>
          The query executed successfully but returned 0 data rows.
        </p>
      </div>
    );
  }

  const firstCol = columns[0];
  const secondCol = columns[1] || columns[0];
  const cardTitle = title || firstCol.replace(/_/g, ' ').toUpperCase();

  // Helper for Currency / Number formatting
  const formatVal = (val: any) => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      if (val >= 1000) return val.toLocaleString();
      return val.toString();
    }
    return String(val);
  };

  // Rule 1: KPI Card (rows == 1 AND columns == 1)
  if (chartType === 'kpi_card' || (rows.length === 1 && columns.length === 1)) {
    const rawVal = rows[0][firstCol];
    const displayVal = formatVal(rawVal);
    // Derive a short punchy label from column name
    const shortLabel = firstCol
      .replace(/_/g, ' ')
      .replace(/\b(count|total|number|num|sum)\b/gi, '')
      .trim()
      .replace(/\b\w/g, l => l.toUpperCase()) || 'Total';

    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        justifyContent: 'center',
        padding: '1.25rem 1.5rem',
        borderRadius: '16px',
        background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.07) 0%, rgba(139, 92, 246, 0.02) 100%)',
        border: '1px solid rgba(79, 70, 229, 0.18)',
        boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.12)',
        position: 'relative',
        overflow: 'hidden',
        width: '100%',
        height: '100%',
        boxSizing: 'border-box'
      }}>
        {/* Decorative glow */}
        <div style={{
          position: 'absolute', top: '-30px', right: '-30px',
          width: '100px', height: '100px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)',
          pointerEvents: 'none'
        }} />

        {/* Label */}
        <div style={{
          fontSize: '0.75rem',
          fontWeight: 700,
          color: 'var(--text-muted, #9CA3AF)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          marginBottom: '0.5rem'
        }}>
          {shortLabel}
        </div>

        {/* Main Metric */}
        <div style={{
          fontSize: '3.5rem',
          fontWeight: 900,
          color: 'var(--text-main, #111827)',
          letterSpacing: '-0.04em',
          lineHeight: 1,
          marginBottom: '0.75rem'
        }}>
          {displayVal}
        </div>

        {/* Trend chip */}
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.3rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          color: '#059669',
          background: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: '99px',
          padding: '0.2rem 0.6rem',
        }}>
          <TrendingUp size={11} /> Live data
        </div>
      </div>
    );
  }

  // Multi KPI Cards (rows == 1 AND multiple numeric columns)
  if (chartType === 'multi_kpi' || (rows.length === 1 && columns.every(col => typeof rows[0][col] === 'number'))) {
    const mainRecord = rows[0];
    const numericCols = columns.filter(col => {
      // Prefer columnTypes if available, fall back to typeof check
      if (columnTypes[col]) return columnTypes[col] === 'NUMERIC' || columnTypes[col] === 'PERCENTAGE';
      return typeof mainRecord[col] === 'number' || !isNaN(Number(mainRecord[col]));
    });
    const primaryCols = numericCols.slice(0, 3);
    const secondaryCols = numericCols.slice(3);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
        {/* Primary metrics row */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${Math.min(primaryCols.length, 3)}, 1fr)`,
          gap: '0.75rem',
          width: '100%'
        }}>
          {primaryCols.map((col, idx) => {
            const shortLabel = col.replace(/_/g, ' ').replace(/\b(count|total|number|num|sum)\b/gi, '').trim().replace(/\b\w/g, l => l.toUpperCase()) || col;
            return (
              <div key={col} style={{
                padding: '1rem 1.25rem',
                borderRadius: '14px',
                background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.06) 0%, rgba(139, 92, 246, 0.02) 100%)',
                border: `1px solid ${COLORS[idx % COLORS.length]}30`,
                boxShadow: '0 4px 15px rgba(0,0,0,0.06)',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted, #9CA3AF)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.35rem' }}>
                  {shortLabel}
                </div>
                <div style={{ fontSize: '2.5rem', fontWeight: 900, color: COLORS[idx % COLORS.length], letterSpacing: '-0.03em', lineHeight: 1 }}>
                  {formatVal(mainRecord[col])}
                </div>
                <div style={{
                  position: 'absolute', bottom: 0, right: 0,
                  width: '60px', height: '60px', borderRadius: '50%',
                  background: `radial-gradient(circle, ${COLORS[idx % COLORS.length]}18 0%, transparent 70%)`,
                  transform: 'translate(20px, 20px)'
                }} />
              </div>
            );
          })}
        </div>
        {/* Secondary metrics as a compact horizontal strip */}
        {secondaryCols.length > 0 && (
          <div style={{
            display: 'flex', gap: '1.5rem', flexWrap: 'wrap',
            padding: '0.75rem 1rem',
            background: 'rgba(0,0,0,0.02)',
            borderRadius: '10px',
            border: '1px solid var(--border-color, rgba(0,0,0,0.06))'
          }}>
            {secondaryCols.map((col, idx) => (
              <div key={col} style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted, #9CA3AF)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {col.replace(/_/g, ' ')}
                </span>
                <span style={{ fontSize: '1.1rem', fontWeight: 700, color: COLORS[(idx + 3) % COLORS.length] }}>
                  {formatVal(mainRecord[col])}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Horizontal Leaderboard Bar Chart (top-N queries or horizontal_bar)
  if (chartType === 'horizontal_bar' || chartType === 'leaderboard') {
    // Phase 1 fix + Phase 2 columnTypes: detect the actual numeric value column
    const numericCols = columns.slice(1).filter(col => {
      // Prefer columnTypes if available, fall back to typeof check
      if (columnTypes[col]) return columnTypes[col] === 'NUMERIC' || columnTypes[col] === 'PERCENTAGE';
      return rows.some(r => typeof r[col] === 'number' || (typeof r[col] === 'string' && !isNaN(Number(r[col]))));
    });
    const valCol = numericCols[numericCols.length - 1] || secondCol;
    const nameCol = firstCol;
    const maxVal = Math.max(...rows.map(r => Number(r[valCol]) || 1));

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%', padding: '0.5rem 0' }}>
        {rows.map((row, idx) => {
          const val = Number(row[valCol]) || 0;
          const pct = Math.min(100, Math.max(5, (val / maxVal) * 100));

          return (
            <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-main, #f8fafc)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: idx === 0 ? '#F59E0B' : (idx === 1 ? '#94A3B8' : (idx === 2 ? '#B45309' : 'rgba(255,255,255,0.1)')),
                    color: idx <= 2 ? '#000' : 'var(--text-muted)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {idx + 1}
                  </span>
                  {String(row[nameCol] ?? '')}
                </span>
                <span style={{ fontWeight: 700, fontFamily: 'monospace', color: COLORS[idx % COLORS.length] }}>
                  {formatVal(val)}
                </span>
              </div>
              <div style={{ width: '100%', height: '10px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
                <div style={{
                  width: `${pct}%`,
                  height: '100%',
                  backgroundColor: COLORS[idx % COLORS.length],
                  borderRadius: '6px',
                  transition: 'width 0.5s ease-out'
                }} />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Rule 2: Detail Card (rows == 1 AND columns > 1)
  if (chartType === 'detail_card' || (rows.length === 1 && columns.length > 1)) {
    const mainRecord = rows[0];
    const primaryTitle = title || (mainRecord[firstCol] ? String(mainRecord[firstCol]) : 'Record Detail');

    return (
      <div style={{
        padding: '1.5rem',
        borderRadius: '16px',
        background: 'var(--bg-dark, #13131a)',
        border: '1px solid var(--border-color, #2b2b40)',
        boxShadow: '0 8px 20px rgba(0,0,0,0.15)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'rgba(34, 197, 94, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#22C55E'
          }}>
            <Award size={20} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main, #f8fafc)' }}>
              {primaryTitle}
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #94a3b8)' }}>Entity Detail Card</span>
          </div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
          marginTop: '1rem'
        }}>
          {columns.map((col, idx) => (
            <div key={col} style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              backgroundColor: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.05)'
            }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {col.replace(/_/g, ' ')}
              </div>
              <div style={{
                fontSize: idx === 0 ? '1.2rem' : '1.1rem',
                fontWeight: 700,
                color: idx === 0 ? '#6366F1' : 'var(--text-main, #f8fafc)',
                marginTop: '0.25rem',
                fontFamily: typeof mainRecord[col] === 'number' ? 'monospace' : 'inherit'
              }}>
                {formatVal(mainRecord[col])}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Data Table Component (Rule 6: rows > 20 OR explicit table chartType)
  if (chartType === 'table' || rows.length > 20) {
    // Filter rows
    const filteredRows = rows.filter(r =>
      columns.some(col => String(r[col] ?? '').toLowerCase().includes(searchTerm.toLowerCase()))
    );

    // Sort rows
    const sortedRows = [...filteredRows].sort((a, b) => {
      if (!sortColumn) return 0;
      const valA = a[sortColumn];
      const valB = b[sortColumn];
      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortDirection === 'asc' ? valA - valB : valB - valA;
      }
      return sortDirection === 'asc'
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    });

    // Paginate rows
    const totalPages = Math.ceil(sortedRows.length / pageSize) || 1;
    const paginatedRows = sortedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    const handleSort = (col: string) => {
      if (sortColumn === col) {
        setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
      } else {
        setSortColumn(col);
        setSortDirection('asc');
      }
    };

    const handleCSVExport = () => {
      const csvLines = [
        columns.join(','),
        ...rows.map(r => columns.map(col => JSON.stringify(r[col] ?? '')).join(','))
      ];
      const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `dataset_export_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '0.75rem' }}>
        {/* Table Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', width: '240px' }}>
            <Search size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search table rows..."
              value={searchTerm}
              onChange={e => { setSearchTerm(e.target.value); setCurrentPage(1); }}
              style={{
                width: '100%',
                padding: '0.4rem 0.5rem 0.4rem 2.25rem',
                fontSize: '0.8rem',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-input, #1e1e2d)',
                border: '1px solid var(--border-color, #2b2b40)',
                color: 'var(--text-main, #f8fafc)'
              }}
            />
          </div>
          <button
            onClick={handleCSVExport}
            className="btn-secondary"
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <Download size={14} /> Export CSV ({rows.length} rows)
          </button>
        </div>

        {/* Data Table */}
        <div className="table-container" style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--border-color, #2b2b40)', borderRadius: '8px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-card, #1a1a24)', zIndex: 10 }}>
              <tr>
                {columns.map(col => (
                  <th
                    key={col}
                    onClick={() => handleSort(col)}
                    style={{
                      padding: '0.6rem 0.85rem',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: 'var(--text-muted, #94a3b8)',
                      borderBottom: '1px solid var(--border-color, #2b2b40)',
                      cursor: 'pointer',
                      userSelect: 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      {col.replace(/_/g, ' ')}
                      <ArrowUpDown size={12} style={{ opacity: sortColumn === col ? 1 : 0.4 }} />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedRows.map((r, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  {columns.map(col => (
                    <td key={col} style={{ padding: '0.55rem 0.85rem', color: 'var(--text-main, #f8fafc)', fontFamily: typeof r[col] === 'number' ? 'monospace' : 'inherit' }}>
                      {formatVal(r[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted, #94a3b8)' }}>
          <span>Showing {paginatedRows.length} of {filteredRows.length} records</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              className="btn-secondary"
              style={{ padding: '0.25rem 0.5rem', opacity: currentPage === 1 ? 0.5 : 1 }}
            >
              <ChevronLeft size={14} />
            </button>
            <span>Page {currentPage} of {totalPages}</span>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              className="btn-secondary"
              style={{ padding: '0.25rem 0.5rem', opacity: currentPage === totalPages ? 0.5 : 1 }}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ECharts axis key resolution — prefer columnTypes when available, fall back to position/typeof
  const hasColumnTypes = Object.keys(columnTypes).length > 0;

  // xAxisKey: prefer first CATEGORICAL or TIME_SERIES column; fall back to columns[0]
  const xAxisKey = hasColumnTypes
    ? (columns.find(col => columnTypes[col] === 'CATEGORICAL' || columnTypes[col] === 'TIME_SERIES') || firstCol)
    : firstCol;

  // yAxisKeys: prefer NUMERIC/PERCENTAGE columns; fall back to typeof-based detection
  const yAxisKeys = hasColumnTypes
    ? columns.filter(col => col !== xAxisKey && (columnTypes[col] === 'NUMERIC' || columnTypes[col] === 'PERCENTAGE'))
    : columns.slice(1).filter(col =>
        rows.some(r => typeof r[col] === 'number' || (typeof r[col] === 'string' && !isNaN(Number(r[col]))))
      );

  const activeYKeys = yAxisKeys.length > 0 ? yAxisKeys : [secondCol];

  const formatTitle = (str: string) => str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  const commonTheme = {
    color: COLORS,
    ...(title ? { title: { text: title, left: 'center', top: 0, textStyle: { fontSize: 16, fontWeight: 600, color: vividSaasTheme.text } } } : {}),
    textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: vividSaasTheme.text },
    tooltip: { 
      trigger: 'axis', 
      backgroundColor: 'rgba(255, 255, 255, 0.95)', 
      borderColor: 'rgba(255, 255, 255, 0.95)', 
      textStyle: { color: vividSaasTheme.text, fontSize: 13 },
      padding: [12, 16],
      extraCssText: 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08); border-radius: 8px; backdrop-filter: blur(4px);',
      axisPointer: { type: 'line', lineStyle: { color: vividSaasTheme.grid, type: 'dashed' } }
    },
    legend: { 
      show: activeYKeys.length > 1,
      textStyle: { color: vividSaasTheme.semantic.neutral, fontSize: 13, fontWeight: 500 }, 
      top: title ? 32 : 0,
      icon: 'circle'
    },
    grid: { left: 96, right: 32, top: title ? 64 : 40, bottom: 48, containLabel: true },
    toolbox: {
      show: true,
      right: 0,
      top: 0,
      feature: { saveAsImage: { title: 'Download', backgroundColor: vividSaasTheme.background, pixelRatio: 2 } },
      iconStyle: { borderColor: vividSaasTheme.semantic.neutral, opacity: 0.4 },
    }
  };

  const commonXAxis = { 
    type: 'category', 
    name: formatTitle(xAxisKey),
    nameLocation: 'middle',
    nameGap: 36,
    nameTextStyle: { color: vividSaasTheme.text, fontWeight: 500, fontSize: 13 },
    data: rows.map(r => r[xAxisKey]), 
    axisLine: { lineStyle: { color: vividSaasTheme.grid } }, 
    axisLabel: { 
      color: vividSaasTheme.semantic.neutral, 
      fontSize: 12,
      interval: 'auto',
      hideOverlap: true,
      align: 'center',
      width: 90,
      overflow: 'truncate'
    } 
  };
  const commonYAxis = { 
    type: 'value', 
    min: 0,
    name: activeYKeys.map(k => formatTitle(k)).join(', '),
    nameLocation: 'middle',
    nameGap: 85,
    nameTextStyle: { color: vividSaasTheme.text, fontWeight: 500, fontSize: 13 },
    splitLine: { lineStyle: { color: vividSaasTheme.grid } }, 
    axisLabel: { color: vividSaasTheme.semantic.neutral, fontSize: 12 } 
  };

  const barOption = {
    ...commonTheme,
    xAxis: { ...commonXAxis, axisTick: { show: false } },
    yAxis: { ...commonYAxis, splitLine: { lineStyle: { color: '#D1D5DB', type: 'solid', width: 1 } } },
    series: activeYKeys.map((key, idx) => ({
      name: key,
      type: 'bar',
      data: rows.map(r => r[key]),
      colorBy: activeYKeys.length === 1 ? 'data' : 'series',
      itemStyle: { 
        ...(activeYKeys.length > 1 ? { color: COLORS[idx % COLORS.length] } : {}), 
        borderRadius: [6, 6, 0, 0] 
      },
      label: {
        show: true,
        position: 'top',
        color: vividSaasTheme.semantic.neutral,
        fontSize: 11,
        formatter: (params: any) => typeof params.value === 'number' ? params.value.toLocaleString() : params.value
      },
      barMaxWidth: 48,
    })),
  };

  const lineOption = {
    ...commonTheme,
    xAxis: { ...commonXAxis, boundaryGap: false, axisTick: { show: false } },
    yAxis: { ...commonYAxis, splitLine: { lineStyle: { color: vividSaasTheme.grid, type: 'dashed' } } },
    series: activeYKeys.map((key, idx) => {
      const color = COLORS[idx % COLORS.length];
      return {
        name: key,
        type: 'line',
        smooth: 0.4,
        symbol: 'circle',
        symbolSize: 8,
        showSymbol: false,
        data: rows.map(r => r[key]),
        lineStyle: { 
          width: 3, 
          color,
          shadowColor: 'rgba(0, 0, 0, 0.15)',
          shadowBlur: 10,
          shadowOffsetY: 5
        },
        itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${color}4D` }, // 30% opacity
            { offset: 1, color: `${color}00` }, // 0% opacity
          ]),
        },
      };
    }),
  };

  const pieOption = {
    ...commonTheme,
    tooltip: { ...commonTheme.tooltip, trigger: 'item' },
    legend: { ...commonTheme.legend, bottom: 0, top: 'auto' },
    grid: undefined,
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      itemStyle: { 
        borderColor: vividSaasTheme.background, 
        borderWidth: 3,
        borderRadius: 8
      },
      label: { 
        color: vividSaasTheme.semantic.neutral, 
        fontSize: 13,
        formatter: '{b}\n{d}%'
      },
      data: rows.map(r => ({ name: r[xAxisKey], value: r[activeYKeys[0]] })),
    }],
  };

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '260px', position: 'relative', display: 'flex', flexDirection: 'column' }}>
      <ReactECharts
        option={chartType === 'line_chart' ? lineOption : chartType === 'pie_chart' ? pieOption : barOption}
        style={{ width: '100%', height: '100%' }}
        opts={{ renderer: 'svg' }}
        notMerge={true}
        lazyUpdate={true}
      />
    </div>
  );
};
