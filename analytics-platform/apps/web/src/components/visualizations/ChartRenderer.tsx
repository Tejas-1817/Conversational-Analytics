import React from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';

interface ChartProps {
  data: any;
  chartType: string;
}

const COLORS = ['#4F46E5', '#8B5CF6', '#22C55E', '#F59E0B', '#EF4444', '#06B6D4'];

export const ChartRenderer: React.FC<ChartProps> = ({ data, chartType }) => {
  if (!data || !data.rows || data.rows.length === 0) return (
    <div className="flex items-center justify-center h-full text-muted" style={{ minHeight: '100px' }}>
      No data available
    </div>
  );

  const { columns, rows } = data;
  
  // Basic heuristic: First column is usually X-axis (dimension/time), rest are Y-axis (metrics)
  const xAxisKey = columns[0];
  const yAxisKeys = columns.slice(1);

  if (chartType === 'kpi_card') {
    const value = rows[0][columns[0]];
    return (
      <div className="flex flex-col items-center justify-center h-full" style={{ padding: '1rem', textAlign: 'center' }}>
        <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
          {columns[0]}
        </div>
        <div style={{ fontSize: '3rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.05em' }}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
      </div>
    );
  }

  if (chartType === 'table') {
    return (
      <div className="table-container" style={{ height: '100%', border: 'none', borderRadius: 0 }}>
        <table>
          <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
            <tr>{columns.map((c: string) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r: any, idx: number) => (
              <tr key={idx}>
                {columns.map((c: string) => (
                  <td key={c} style={{ fontFamily: typeof r[c] === 'number' ? 'monospace' : 'inherit' }}>
                    {typeof r[c] === 'number' ? r[c].toLocaleString() : String(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const renderTooltip = (props: any) => {
    const { active, payload, label } = props;
    if (active && payload && payload.length) {
      return (
        <div className="card" style={{ padding: '0.75rem', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-lg)', zIndex: 100 }}>
          <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600, color: 'var(--text-main)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.25rem' }}>{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', marginTop: '0.25rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: entry.color }} />
              <span style={{ color: 'var(--text-muted)' }}>{entry.name}:</span>
              <span style={{ color: 'var(--text-main)', fontWeight: 500, fontFamily: 'monospace' }}>{entry.value?.toLocaleString()}</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-wrapper" style={{ width: '100%', height: '100%', minHeight: '200px', position: 'relative' }}>
      <ResponsiveContainer width="100%" height="100%">
        {chartType === 'line_chart' ? (
          <AreaChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              {yAxisKeys.map((key: string, idx: number) => (
                <linearGradient key={`color-${key}`} id={`color-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS[idx % COLORS.length]} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={COLORS[idx % COLORS.length]} stopOpacity={0}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} dy={10} />
            <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} dx={-10} tickFormatter={(value) => value.toLocaleString()} />
            <Tooltip content={renderTooltip} cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            {yAxisKeys.map((key: string, idx: number) => (
              <Area 
                type="monotone" 
                key={key} 
                dataKey={key} 
                stroke={COLORS[idx % COLORS.length]} 
                fillOpacity={1} 
                fill={`url(#color-${key})`} 
                strokeWidth={2} 
                activeDot={{ r: 6, strokeWidth: 0 }} 
              />
            ))}
          </AreaChart>
        ) : chartType === 'pie_chart' ? (
          <PieChart>
            <Tooltip content={renderTooltip} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            <Pie data={rows} dataKey={yAxisKeys[0]} nameKey={xAxisKey} cx="50%" cy="50%" innerRadius={60} outerRadius={80} stroke="var(--bg-card)" strokeWidth={2}>
              {rows.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} dy={10} />
            <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} dx={-10} tickFormatter={(value) => value.toLocaleString()} />
            <Tooltip content={renderTooltip} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            {yAxisKeys.map((key: string, idx: number) => (
              <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[4, 4, 0, 0]} maxBarSize={60} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
      <button 
        onClick={(e) => {
          const svg = (e.target as HTMLElement).closest('.chart-wrapper')?.querySelector('svg');
          if (svg) {
            const svgData = new XMLSerializer().serializeToString(svg);
            const blob = new Blob([svgData], {type: "image/svg+xml;charset=utf-8"});
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "chart.svg";
            a.click();
          }
        }}
        className="btn-ghost"
        style={{ position: 'absolute', bottom: '1rem', right: '1rem', padding: '0.25rem', opacity: 0.3, zIndex: 50 }}
        title="Download SVG"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
      </button>
    </div>
  );
};
