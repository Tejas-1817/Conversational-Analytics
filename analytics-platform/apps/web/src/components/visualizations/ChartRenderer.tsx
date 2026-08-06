import React, { useState, useMemo } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';
import {
  TrendingUp, Users, Award, Table as TableIcon, Download, Search, ArrowUpDown, ChevronLeft, ChevronRight, AlertCircle, Layers
} from 'lucide-react';

interface ChartProps {
  data: any;
  chartType: string;
  title?: string;
  columns?: string[];
}

const COLORS = ['#4F46E5', '#8B5CF6', '#22C55E', '#F59E0B', '#EF4444', '#06B6D4', '#EC4899', '#3B82F6'];

export const ChartRenderer: React.FC<ChartProps> = ({ data, chartType, title, columns: customColumns }) => {
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

    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.75rem 1.5rem',
        borderRadius: '16px',
        background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.08) 0%, rgba(139, 92, 246, 0.03) 100%)',
        border: '1px solid rgba(79, 70, 229, 0.2)',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.2)',
        textAlign: 'center',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{
          width: '48px',
          height: '48px',
          borderRadius: '12px',
          background: 'rgba(79, 70, 229, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#6366F1',
          marginBottom: '0.75rem'
        }}>
          <Users size={24} />
        </div>
        <div style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--text-muted, #94a3b8)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          marginBottom: '0.5rem'
        }}>
          {cardTitle}
        </div>
        <div style={{
          fontSize: '3.25rem',
          fontWeight: 800,
          color: 'var(--text-main, #f8fafc)',
          letterSpacing: '-0.03em',
          lineHeight: 1
        }}>
          {displayVal}
        </div>
        <div style={{
          marginTop: '0.75rem',
          fontSize: '0.75rem',
          color: '#22C55E',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: '0.25rem'
        }}>
        </div>
      </div>
    );
  }

  // Multi KPI Cards (rows == 1 AND multiple numeric columns)
  if (chartType === 'multi_kpi' || (rows.length === 1 && columns.every(col => typeof rows[0][col] === 'number'))) {
    const mainRecord = rows[0];
    return (
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
        width: '100%'
      }}>
        {columns.map((col, idx) => (
          <div key={col} style={{
            padding: '1.25rem 1rem',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.06) 0%, rgba(139, 92, 246, 0.02) 100%)',
            border: '1px solid rgba(79, 70, 229, 0.15)',
            boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {col.replace(/_/g, ' ')}
            </div>
            <div style={{ fontSize: '2.25rem', fontWeight: 800, color: COLORS[idx % COLORS.length], marginTop: '0.35rem', letterSpacing: '-0.02em' }}>
              {formatVal(mainRecord[col])}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Horizontal Leaderboard Bar Chart (top-N queries or horizontal_bar)
  if (chartType === 'horizontal_bar' || chartType === 'leaderboard') {
    const valCol = secondCol;
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

  // Recharts Y-Axis keys (all numeric columns starting from index 1)
  const xAxisKey = firstCol;
  const yAxisKeys = columns.slice(1).filter(col =>
    rows.some(r => typeof r[col] === 'number' || (typeof r[col] === 'string' && !isNaN(Number(r[col]))))
  );

  const activeYKeys = yAxisKeys.length > 0 ? yAxisKeys : [secondCol];

  const renderTooltip = (props: any) => {
    const { active, payload, label } = props;
    if (active && payload && payload.length) {
      return (
        <div style={{
          padding: '0.75rem 1rem',
          borderRadius: '10px',
          backgroundColor: '#1e1e2d',
          border: '1px solid #2b2b40',
          boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
          zIndex: 100
        }}>
          <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600, color: '#f8fafc', borderBottom: '1px solid #2b2b40', paddingBottom: '0.25rem' }}>
            {label}
          </p>
          {payload.map((entry: any, index: number) => (
            <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', marginTop: '0.25rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: entry.color }} />
              <span style={{ color: '#94a3b8' }}>{entry.name}:</span>
              <span style={{ color: '#f8fafc', fontWeight: 600, fontFamily: 'monospace' }}>
                {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '260px', position: 'relative', display: 'flex', flexDirection: 'column' }}>
      <ResponsiveContainer width="100%" height="100%">
        {chartType === 'line_chart' ? (
          <AreaChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
            <defs>
              {activeYKeys.map((key: string, idx: number) => (
                <linearGradient key={`color-${key}`} id={`color-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS[idx % COLORS.length]} stopOpacity={0.4}/>
                  <stop offset="95%" stopColor={COLORS[idx % COLORS.length]} stopOpacity={0}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} dy={10} />
            <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={v => typeof v === 'number' ? v.toLocaleString() : v} />
            <Tooltip content={renderTooltip} cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            {activeYKeys.map((key: string, idx: number) => (
              <Area
                type="monotone"
                key={key}
                dataKey={key}
                stroke={COLORS[idx % COLORS.length]}
                fillOpacity={1}
                fill={`url(#color-${key})`}
                strokeWidth={3}
                activeDot={{ r: 6, strokeWidth: 0 }}
              />
            ))}
          </AreaChart>
        ) : chartType === 'pie_chart' ? (
          <PieChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
            <Tooltip content={renderTooltip} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            <Pie
              data={rows}
              dataKey={activeYKeys[0]}
              nameKey={xAxisKey}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={85}
              paddingAngle={4}
              stroke="#1a1a24"
              strokeWidth={2}
              label={({ name, percent }: any) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
            >
              {rows.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} dy={10} />
            <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={v => typeof v === 'number' ? v.toLocaleString() : v} />
            <Tooltip content={renderTooltip} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            {activeYKeys.map((key: string, idx: number) => (
              <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[6, 6, 0, 0]} maxBarSize={55} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
};
