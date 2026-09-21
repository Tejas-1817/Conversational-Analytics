import React, { useState, useMemo, useRef, useEffect } from 'react';
import * as echarts from 'echarts/core';
import ReactECharts from 'echarts-for-react';
import {
  TrendingUp,
  Award,
  Table as TableIcon,
  Search,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Layers,
  BarChart2,
  PieChart,
  FileSpreadsheet,
  Image as ImageIcon,
  Sparkles
} from 'lucide-react';

export interface ChartProps {
  data: any;
  chartType: string;
  title?: string;
  columns?: string[];
  columnTypes?: Record<string, string>; // e.g. { revenue: 'NUMERIC', month: 'TIME_SERIES' }
  onPointClick?: (point: { category: string; value: any; seriesName?: string }) => void;
  hideToolbar?: boolean;
}

// Wisdom.ai Signature Vibrant SaaS Palette & Gradients
export const wisdomSaasTheme = {
  palette: [
    '#6366F1', // Indigo
    '#06B6D4', // Cyan
    '#8B5CF6', // Violet
    '#10B981', // Emerald
    '#F59E0B', // Amber
    '#F43F5E', // Rose
    '#3B82F6', // Blue
    '#EC4899', // Pink
    '#14B8A6', // Teal
  ],
  gradients: [
    ['#6366F1', '#4F46E5'],
    ['#06B6D4', '#0891B2'],
    ['#8B5CF6', '#7C3AED'],
    ['#10B981', '#059669'],
    ['#F59E0B', '#D97706'],
    ['#F43F5E', '#E11D48'],
    ['#3B82F6', '#2563EB'],
  ],
  semantic: {
    positive: '#10B981',
    negative: '#EF4444',
    neutral: '#64748B',
  },
};

// Backwards-compatible export for existing tests/references
export const vividSaasTheme = {
  categorical: wisdomSaasTheme.palette,
  sequential: ['#F3E8FF', '#C4B5FD', '#8B5CF6', '#6D28D9', '#4C1D95'],
  semantic: wisdomSaasTheme.semantic,
  background: '#FAFAFA',
  text: '#111827',
  grid: '#F0F0F0',
};

const COLORS = wisdomSaasTheme.palette;

export const ChartRenderer: React.FC<ChartProps> = ({
  data,
  chartType,
  title,
  columns: customColumns,
  columnTypes = {},
  onPointClick,
  hideToolbar = false,
}) => {
  const echartsRef = useRef<any>(null);

  // Active chart type state with support for interactive switching
  const [activeType, setActiveType] = useState<string>(chartType);

  useEffect(() => {
    setActiveType(chartType);
  }, [chartType]);

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

  // Zero Rows State
  if (!rows || rows.length === 0 || columns.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        borderRadius: '14px',
        backgroundColor: 'rgba(148, 163, 184, 0.04)',
        border: '1px dashed var(--border-color, rgba(148, 163, 184, 0.25))',
        minHeight: '160px',
        textAlign: 'center'
      }}>
        <AlertCircle size={32} style={{ color: 'var(--text-muted, #94a3b8)', marginBottom: '0.75rem' }} />
        <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-main, #0F172A)' }}>
          No matching records found.
        </h4>
        <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted, #64748B)' }}>
          The query executed successfully but returned 0 data rows.
        </p>
      </div>
    );
  }

  const firstCol = columns[0];
  const secondCol = columns[1] || columns[0];

  // Helper for Currency / Number formatting
  const formatVal = (val: any) => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      if (Math.abs(val) >= 1_000_000) {
        return (val / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 }) + 'M';
      }
      if (Math.abs(val) >= 1_000) {
        return val.toLocaleString();
      }
      return val.toString();
    }
    return String(val);
  };

  // Helper for Exporting CSV
  const handleExportCSV = () => {
    if (!rows || rows.length === 0) return;
    const header = columns.join(',');
    const body = rows.map(r => columns.map(c => `"${String(r[c] ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const csvContent = 'data:text/csv;charset=utf-8,' + encodeURIComponent(`${header}\n${body}`);
    const link = document.createElement('a');
    link.setAttribute('href', csvContent);
    link.setAttribute('download', `${(title || 'analytics_export').toLowerCase().replace(/\s+/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Helper for Exporting PNG Image
  const handleExportPNG = () => {
    if (echartsRef.current) {
      const eInstance = echartsRef.current.getEchartsInstance?.();
      if (eInstance) {
        const url = eInstance.getDataURL({
          type: 'png',
          pixelRatio: 2,
          backgroundColor: '#FFFFFF',
        });
        const link = document.createElement('a');
        link.href = url;
        link.download = `${(title || 'chart_export').toLowerCase().replace(/\s+/g, '_')}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    }
  };

  // Rule 1: KPI Single Card (rows == 1 AND columns == 1)
  if (activeType === 'kpi_card' || (rows.length === 1 && columns.length === 1)) {
    const rawVal = rows[0][firstCol];
    const displayVal = formatVal(rawVal);
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
        background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(6, 182, 212, 0.04) 100%)',
        border: '1px solid rgba(99, 102, 241, 0.18)',
        boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.06)',
        position: 'relative',
        overflow: 'hidden',
        width: '100%',
        height: '100%',
        boxSizing: 'border-box'
      }}>
        <div style={{
          position: 'absolute', top: '-30px', right: '-30px',
          width: '120px', height: '120px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99, 102, 241, 0.2) 0%, transparent 70%)',
          pointerEvents: 'none'
        }} />

        <div style={{
          fontSize: '0.75rem',
          fontWeight: 700,
          color: 'var(--text-muted, #64748B)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          marginBottom: '0.5rem'
        }}>
          {shortLabel}
        </div>

        <div style={{
          fontSize: '3.25rem',
          fontWeight: 900,
          color: 'var(--text-main, #0F172A)',
          letterSpacing: '-0.04em',
          lineHeight: 1,
          marginBottom: '0.75rem'
        }}>
          {displayVal}
        </div>

        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.35rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          color: '#059669',
          background: 'rgba(16, 185, 129, 0.12)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          borderRadius: '99px',
          padding: '0.2rem 0.65rem',
        }}>
          <TrendingUp size={12} /> Live dataset
        </div>
      </div>
    );
  }

  // Multi KPI Cards (rows == 1 AND multiple numeric columns)
  if (activeType === 'multi_kpi' || (rows.length === 1 && columns.every(col => typeof rows[0][col] === 'number'))) {
    const mainRecord = rows[0];
    const numericCols = columns.filter(col => {
      if (columnTypes[col]) return columnTypes[col] === 'NUMERIC' || columnTypes[col] === 'PERCENTAGE';
      return typeof mainRecord[col] === 'number' || !isNaN(Number(mainRecord[col]));
    });
    const primaryCols = numericCols.slice(0, 3);
    const secondaryCols = numericCols.slice(3);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${Math.min(primaryCols.length, 3)}, 1fr)`,
          gap: '0.75rem',
          width: '100%'
        }}>
          {primaryCols.map((col, idx) => {
            const shortLabel = col.replace(/_/g, ' ').replace(/\b(count|total|number|num|sum)\b/gi, '').trim().replace(/\b\w/g, l => l.toUpperCase()) || col;
            const colColor = COLORS[idx % COLORS.length];
            return (
              <div key={col} style={{
                padding: '1rem 1.25rem',
                borderRadius: '14px',
                background: `linear-gradient(135deg, ${colColor}12 0%, rgba(255, 255, 255, 0.02) 100%)`,
                border: `1px solid ${colColor}35`,
                boxShadow: '0 4px 16px rgba(0,0,0,0.05)',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.35rem' }}>
                  {shortLabel}
                </div>
                <div style={{ fontSize: '2.4rem', fontWeight: 900, color: colColor, letterSpacing: '-0.03em', lineHeight: 1 }}>
                  {formatVal(mainRecord[col])}
                </div>
                <div style={{
                  position: 'absolute', bottom: 0, right: 0,
                  width: '60px', height: '60px', borderRadius: '50%',
                  background: `radial-gradient(circle, ${colColor}25 0%, transparent 70%)`,
                  transform: 'translate(20px, 20px)'
                }} />
              </div>
            );
          })}
        </div>
        {secondaryCols.length > 0 && (
          <div style={{
            display: 'flex', gap: '1.5rem', flexWrap: 'wrap',
            padding: '0.75rem 1rem',
            background: 'rgba(148, 163, 184, 0.06)',
            borderRadius: '10px',
            border: '1px solid var(--border-color, rgba(148, 163, 184, 0.18))'
          }}>
            {secondaryCols.map((col, idx) => (
              <div key={col} style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
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

  // Detail Card (rows == 1 AND columns > 1)
  if (activeType === 'detail_card' || (rows.length === 1 && columns.length > 1 && activeType !== 'table')) {
    const mainRecord = rows[0];
    const primaryTitle = title || (mainRecord[firstCol] ? String(mainRecord[firstCol]) : 'Record Detail');

    return (
      <div style={{
        padding: '1.5rem',
        borderRadius: '16px',
        background: 'var(--bg-card, #FFFFFF)',
        border: '1px solid var(--border-color, rgba(148, 163, 184, 0.2))',
        boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.08)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'rgba(99, 102, 241, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#6366F1'
            }}>
              <Sparkles size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main, #0F172A)' }}>
                {primaryTitle}
              </h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #64748B)' }}>Structured Record Profile</span>
            </div>
          </div>
          <button
            onClick={() => setActiveType('table')}
            className="btn-ghost"
            style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <TableIcon size={14} /> View Table
          </button>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
          marginTop: '0.5rem'
        }}>
          {columns.map((col, idx) => (
            <div key={col} style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              backgroundColor: 'rgba(148, 163, 184, 0.05)',
              border: '1px solid rgba(148, 163, 184, 0.12)'
            }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {col.replace(/_/g, ' ')}
              </div>
              <div style={{
                fontSize: idx === 0 ? '1.15rem' : '1.05rem',
                fontWeight: 700,
                color: idx === 0 ? '#6366F1' : 'var(--text-main, #0F172A)',
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

  // Interactive Table View
  if (activeType === 'table') {
    const filteredRows = rows.filter(r =>
      columns.some(col => String(r[col] ?? '').toLowerCase().includes(searchTerm.toLowerCase()))
    );

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

    const totalPages = Math.ceil(sortedRows.length / pageSize) || 1;
    const paginatedRows = sortedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        width: '100%',
        backgroundColor: 'var(--bg-card, #FFFFFF)',
        border: '1px solid var(--border-color, rgba(148, 163, 184, 0.2))',
        borderRadius: '14px',
        padding: '1rem',
        boxShadow: '0 4px 20px rgba(0,0,0,0.04)'
      }}>
        {/* Table Header & Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', width: '220px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search table..."
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
              style={{
                width: '100%',
                padding: '0.4rem 0.6rem 0.4rem 2rem',
                fontSize: '0.8rem',
                borderRadius: '8px',
                border: '1px solid var(--border-color, rgba(148, 163, 184, 0.25))',
                background: 'rgba(148, 163, 184, 0.05)',
                color: 'var(--text-main)'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {/* Chart Type Switcher Toolbar */}
            {!hideToolbar && rows.length > 0 && columns.length >= 2 && (
              <div style={{ display: 'flex', background: 'rgba(148, 163, 184, 0.1)', padding: '2px', borderRadius: '8px', gap: '2px' }}>
                <button
                  className="btn-ghost"
                  style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '0.75rem' }}
                  onClick={() => setActiveType('bar_chart')}
                  title="Switch to Bar Chart"
                >
                  <BarChart2 size={14} />
                </button>
                <button
                  className="btn-ghost"
                  style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '0.75rem' }}
                  onClick={() => setActiveType('line_chart')}
                  title="Switch to Line Chart"
                >
                  <TrendingUp size={14} />
                </button>
                <button
                  className="btn-ghost"
                  style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '0.75rem' }}
                  onClick={() => setActiveType('area_chart')}
                  title="Switch to Area Chart"
                >
                  <Layers size={14} />
                </button>
                <button
                  className="btn-ghost"
                  style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '0.75rem' }}
                  onClick={() => setActiveType('pie_chart')}
                  title="Switch to Donut Chart"
                >
                  <PieChart size={14} />
                </button>
              </div>
            )}
            <button
              onClick={handleExportCSV}
              className="btn-secondary"
              style={{ padding: '0.4rem 0.75rem', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              title="Export CSV"
            >
              <FileSpreadsheet size={13} /> Export CSV
            </button>
          </div>
        </div>

        {/* Scrollable Table */}
        <div style={{ overflowX: 'auto', maxHeight: '340px', border: '1px solid var(--border-color, rgba(148, 163, 184, 0.18))', borderRadius: '10px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(148, 163, 184, 0.08)', borderBottom: '1px solid var(--border-color, rgba(148, 163, 184, 0.2))' }}>
                {columns.map(col => (
                  <th
                    key={col}
                    onClick={() => {
                      if (sortColumn === col) {
                        setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
                      } else {
                        setSortColumn(col);
                        setSortDirection('asc');
                      }
                    }}
                    style={{
                      padding: '0.65rem 0.85rem',
                      fontWeight: 600,
                      color: 'var(--text-main, #0F172A)',
                      cursor: 'pointer',
                      userSelect: 'none',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      {col.replace(/_/g, ' ').toUpperCase()}
                      <ArrowUpDown size={12} style={{ opacity: sortColumn === col ? 1 : 0.3 }} />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedRows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  style={{
                    borderBottom: '1px solid var(--border-color, rgba(148, 163, 184, 0.1))',
                    backgroundColor: rIdx % 2 === 0 ? 'transparent' : 'rgba(148, 163, 184, 0.03)',
                    transition: 'background-color 0.15s'
                  }}
                  className="hover-bg-light"
                >
                  {columns.map(col => (
                    <td key={col} style={{ padding: '0.6rem 0.85rem', color: 'var(--text-main, #334155)', whiteSpace: 'nowrap' }}>
                      {formatVal(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted, #64748B)' }}>
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

  // ECharts axis key resolution
  const hasColumnTypes = Object.keys(columnTypes).length > 0;

  const xAxisKey = hasColumnTypes
    ? (columns.find(col => columnTypes[col] === 'CATEGORICAL' || columnTypes[col] === 'TIME_SERIES') || firstCol)
    : firstCol;

  const yAxisKeys = hasColumnTypes
    ? columns.filter(col => col !== xAxisKey && (columnTypes[col] === 'NUMERIC' || columnTypes[col] === 'PERCENTAGE'))
    : columns.slice(1).filter(col =>
      rows.some(r => typeof r[col] === 'number' || (typeof r[col] === 'string' && !isNaN(Number(r[col]))))
    );

  const activeYKeys = yAxisKeys.length > 0 ? yAxisKeys : [secondCol];

  const formatTitle = (str: string) => str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  // Wisdom.ai Theme and Tooltips
  const commonTheme = {
    color: COLORS,
    textStyle: { fontFamily: 'Inter, system-ui, -apple-system, sans-serif', color: '#334155' },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      borderWidth: 1,
      textStyle: { color: '#F8FAFC', fontSize: 12 },
      padding: [10, 14],
      extraCssText: 'box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28); border-radius: 10px; backdrop-filter: blur(8px);',
      axisPointer: {
        type: 'line',
        lineStyle: { color: 'rgba(99, 102, 241, 0.4)', type: 'dashed', width: 1.5 }
      },
      formatter: (params: any) => {
        if (!Array.isArray(params)) {
          return `<div style="font-weight:600;margin-bottom:4px;">${params.name}</div>
                  <div style="display:flex;align-items:center;gap:6px;">
                    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${params.color};"></span>
                    <span>${params.seriesName || formatTitle(xAxisKey)}:</span>
                    <b>${typeof params.value === 'number' ? params.value.toLocaleString() : params.value}</b>
                  </div>`;
        }
        let res = `<div style="font-weight:700;font-size:12px;color:#94A3B8;margin-bottom:6px;">${params[0]?.axisValueLabel || ''}</div>`;
        params.forEach((item: any) => {
          const valStr = typeof item.value === 'number' ? item.value.toLocaleString() : item.value;
          res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:3px;">
                    <div style="display:flex;align-items:center;gap:6px;">
                      <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color};"></span>
                      <span style="color:#E2E8F0;font-size:12px;">${formatTitle(item.seriesName)}:</span>
                    </div>
                    <b style="color:#38BDF8;font-size:12px;">${valStr}</b>
                  </div>`;
        });
        return res;
      }
    },
    legend: {
      show: activeYKeys.length > 1,
      textStyle: { color: '#64748B', fontSize: 12, fontWeight: 500 },
      top: 0,
      icon: 'circle'
    },
    grid: {
      left: 12,
      right: 16,
      top: activeYKeys.length > 1 ? 40 : 20,
      bottom: rows.length > 8 ? 44 : 20,
      containLabel: true
    },
  };

  const commonXAxis = {
    type: 'category',
    data: rows.map(r => r[xAxisKey]),
    axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.25)' } },
    axisTick: { show: false },
    axisLabel: {
      color: '#64748B',
      fontSize: 11,
      interval: 'auto',
      hideOverlap: true,
      align: 'center',
      width: 85,
      overflow: 'truncate'
    }
  };

  const commonYAxis = {
    type: 'value',
    min: 0,
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.12)', type: 'dashed' } },
    axisLabel: {
      color: '#64748B',
      fontSize: 11,
      formatter: (val: number) => formatVal(val)
    }
  };

  // DataZoom slider for large datasets
  const dataZoomConfig = rows.length > 8 ? [
    { type: 'inside', start: 0, end: 100 },
    {
      type: 'slider',
      show: true,
      bottom: 2,
      height: 14,
      borderColor: 'transparent',
      backgroundColor: 'rgba(148, 163, 184, 0.08)',
      fillerColor: 'rgba(99, 102, 241, 0.16)',
      handleSize: '100%',
      handleStyle: { color: '#6366F1', borderColor: '#818CF8' },
      textStyle: { fontSize: 10, color: '#94A3B8' }
    }
  ] : [];

  // 1. Bar Chart Option
  const barOption = {
    ...commonTheme,
    xAxis: commonXAxis,
    yAxis: commonYAxis,
    dataZoom: dataZoomConfig,
    series: activeYKeys.map((key, idx) => {
      const colColor = COLORS[idx % COLORS.length];
      const grad = wisdomSaasTheme.gradients[idx % wisdomSaasTheme.gradients.length];
      return {
        name: key,
        type: 'bar',
        data: rows.map(r => r[key]),
        barMaxWidth: 34,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: grad[0] },
            { offset: 1, color: grad[1] }
          ])
        },
        emphasis: {
          focus: 'series',
          itemStyle: {
            shadowBlur: 10,
            shadowColor: `${colColor}50`
          }
        },
        label: {
          show: rows.length <= 10,
          position: 'top',
          color: '#64748B',
          fontSize: 10,
          formatter: (params: any) => formatVal(params.value)
        }
      };
    }),
  };

  // 2. Line Chart Option
  const lineOption = {
    ...commonTheme,
    xAxis: { ...commonXAxis, boundaryGap: false },
    yAxis: commonYAxis,
    dataZoom: dataZoomConfig,
    series: activeYKeys.map((key, idx) => {
      const colColor = COLORS[idx % COLORS.length];
      return {
        name: key,
        type: 'line',
        smooth: 0.35,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: rows.length <= 15,
        data: rows.map(r => r[key]),
        lineStyle: {
          width: 3,
          color: colColor,
          shadowColor: `${colColor}40`,
          shadowBlur: 8,
          shadowOffsetY: 4
        },
        itemStyle: {
          color: colColor,
          borderColor: '#FFFFFF',
          borderWidth: 2
        },
        emphasis: {
          focus: 'series',
          scale: true,
          itemStyle: {
            shadowBlur: 12,
            shadowColor: colColor
          }
        }
      };
    }),
  };

  // 3. Area Chart Option (Smooth Gradient Area)
  const areaOption = {
    ...commonTheme,
    xAxis: { ...commonXAxis, boundaryGap: false },
    yAxis: commonYAxis,
    dataZoom: dataZoomConfig,
    series: activeYKeys.map((key, idx) => {
      const colColor = COLORS[idx % COLORS.length];
      return {
        name: key,
        type: 'line',
        smooth: 0.35,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: rows.length <= 15,
        data: rows.map(r => r[key]),
        lineStyle: {
          width: 2.5,
          color: colColor
        },
        itemStyle: {
          color: colColor,
          borderColor: '#FFFFFF',
          borderWidth: 2
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${colColor}55` }, // 35% opacity
            { offset: 1, color: `${colColor}02` }, // 1% opacity
          ]),
        },
        emphasis: {
          focus: 'series',
          scale: true
        }
      };
    }),
  };

  // 4. Donut / Pie Chart Option
  const pieOption = {
    ...commonTheme,
    tooltip: {
      ...commonTheme.tooltip,
      trigger: 'item',
      formatter: (params: any) => `
        <div style="font-weight:700;margin-bottom:4px;color:#94A3B8;">${params.seriesName || formatTitle(activeYKeys[0])}</div>
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${params.color};"></span>
          <span>${params.name}:</span>
          <b>${typeof params.value === 'number' ? params.value.toLocaleString() : params.value} (${params.percent}%)</b>
        </div>
      `
    },
    legend: {
      ...commonTheme.legend,
      bottom: 0,
      top: 'auto',
      type: 'scroll'
    },
    grid: undefined,
    series: [{
      name: formatTitle(activeYKeys[0]),
      type: 'pie',
      radius: ['52%', '78%'],
      padAngle: 3,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#FFFFFF',
        borderWidth: 2
      },
      label: {
        color: '#64748B',
        fontSize: 11,
        formatter: '{b}: {d}%'
      },
      emphasis: {
        scale: true,
        scaleSize: 8,
        itemStyle: {
          shadowBlur: 14,
          shadowColor: 'rgba(0, 0, 0, 0.2)'
        }
      },
      data: rows.map((r, i) => ({
        name: String(r[xAxisKey] ?? `Item ${i + 1}`),
        value: r[activeYKeys[0]],
        itemStyle: { color: COLORS[i % COLORS.length] }
      })),
    }],
  };

  // Resolve active chart option
  let selectedOption: any = barOption;
  if (activeType === 'line_chart') selectedOption = lineOption;
  else if (activeType === 'area_chart') selectedOption = areaOption;
  else if (activeType === 'pie_chart') selectedOption = pieOption;

  return (
    <div style={{
      width: '100%',
      height: '100%',
      minHeight: '260px',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: 'var(--bg-card, #FFFFFF)',
      borderRadius: '14px',
      border: '1px solid var(--border-color, rgba(148, 163, 184, 0.2))',
      padding: '0.85rem 1rem 0.5rem 1rem',
      boxShadow: '0 4px 20px rgba(0,0,0,0.03)',
      boxSizing: 'border-box'
    }}>
      {/* Top Interactive Toolbar */}
      {!hideToolbar && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.5rem',
          flexShrink: 0
        }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main, #0F172A)' }}>
            {title || formatTitle(activeYKeys[0] || 'Metric Overview')}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {/* Chart Type Selector Pills */}
            <div style={{
              display: 'flex',
              background: 'rgba(148, 163, 184, 0.1)',
              padding: '2px',
              borderRadius: '8px',
              gap: '2px'
            }}>
              <button
                className="btn-ghost"
                onClick={() => setActiveType('bar_chart')}
                title="Bar Chart"
                style={{
                  padding: '4px 6px',
                  borderRadius: '6px',
                  background: activeType === 'bar_chart' ? 'var(--bg-card, #FFFFFF)' : 'transparent',
                  color: activeType === 'bar_chart' ? 'var(--primary, #6366F1)' : 'var(--text-muted)',
                  boxShadow: activeType === 'bar_chart' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                <BarChart2 size={13} />
              </button>
              <button
                className="btn-ghost"
                onClick={() => setActiveType('line_chart')}
                title="Line Chart"
                style={{
                  padding: '4px 6px',
                  borderRadius: '6px',
                  background: activeType === 'line_chart' ? 'var(--bg-card, #FFFFFF)' : 'transparent',
                  color: activeType === 'line_chart' ? 'var(--primary, #6366F1)' : 'var(--text-muted)',
                  boxShadow: activeType === 'line_chart' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                <TrendingUp size={13} />
              </button>
              <button
                className="btn-ghost"
                onClick={() => setActiveType('area_chart')}
                title="Area Chart"
                style={{
                  padding: '4px 6px',
                  borderRadius: '6px',
                  background: activeType === 'area_chart' ? 'var(--bg-card, #FFFFFF)' : 'transparent',
                  color: activeType === 'area_chart' ? 'var(--primary, #6366F1)' : 'var(--text-muted)',
                  boxShadow: activeType === 'area_chart' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                <Layers size={13} />
              </button>
              <button
                className="btn-ghost"
                onClick={() => setActiveType('pie_chart')}
                title="Donut Chart"
                style={{
                  padding: '4px 6px',
                  borderRadius: '6px',
                  background: activeType === 'pie_chart' ? 'var(--bg-card, #FFFFFF)' : 'transparent',
                  color: activeType === 'pie_chart' ? 'var(--primary, #6366F1)' : 'var(--text-muted)',
                  boxShadow: activeType === 'pie_chart' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                <PieChart size={13} />
              </button>
              <button
                className="btn-ghost"
                onClick={() => setActiveType('table')}
                title="Data Table"
                style={{
                  padding: '4px 6px',
                  borderRadius: '6px',
                  background: activeType === 'table' ? 'var(--bg-card, #FFFFFF)' : 'transparent',
                  color: activeType === 'table' ? 'var(--primary, #6366F1)' : 'var(--text-muted)',
                  boxShadow: activeType === 'table' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                <TableIcon size={13} />
              </button>
            </div>

            {/* Export Actions */}
            <button
              className="btn-ghost"
              onClick={handleExportPNG}
              title="Download PNG Image"
              style={{ padding: '4px 6px', borderRadius: '6px', color: 'var(--text-muted)' }}
            >
              <ImageIcon size={13} />
            </button>
            <button
              className="btn-ghost"
              onClick={handleExportCSV}
              title="Export CSV"
              style={{ padding: '4px 6px', borderRadius: '6px', color: 'var(--text-muted)' }}
            >
              <FileSpreadsheet size={13} />
            </button>
          </div>
        </div>
      )}

      {/* Chart Canvas Area */}
      <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
        <ReactECharts
          ref={echartsRef}
          option={selectedOption}
          style={{ width: '100%', height: '100%' }}
          opts={{ renderer: 'svg' }}
          notMerge={true}
          lazyUpdate={true}
          onEvents={onPointClick ? {
            click: (params: any) => {
              onPointClick({
                category: params.name || params.axisValueLabel,
                value: params.value,
                seriesName: params.seriesName
              });
            }
          } : undefined}
        />
      </div>
    </div>
  );
};
