import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { LayoutDashboard, Plus, Bookmark, Settings, Maximize2, Minimize2, RefreshCw, Download, MoreVertical, LayoutGrid, AlertCircle, X, Trash2, FileJson, Table2 } from 'lucide-react';
import { ChartRenderer } from '../../components/visualizations/ChartRenderer';
// @ts-ignore
import { ResponsiveGridLayout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

export const Dashboards = () => {
  const [dashboards, setDashboards] = useState<any[]>([]);
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [newDashName, setNewDashName] = useState('');
  const [newDashDesc, setNewDashDesc] = useState('');
  const [activeDashboardId, setActiveDashboardId] = useState<string | null>(null);
  
  const [isEditMode, setIsEditMode] = useState(false);
  const [fullScreenWidgetId, setFullScreenWidgetId] = useState<string | null>(null);
  const [showMenuForWidget, setShowMenuForWidget] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [dRes, iRes] = await Promise.all([
        fetchApi('/dashboards'),
        fetchApi('/dashboards/insights')
      ]);
      setDashboards(dRes);
      setInsights(iRes);
      if (dRes.length > 0 && !activeDashboardId) {
        setActiveDashboardId(dRes[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateDashboard = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const widgets = insights.slice(0, 4).map((ins, i) => ({
        insight_id: ins.id,
        x: (i % 2) * 6,
        y: Math.floor(i / 2) * 4,
        w: 6,
        h: 4
      }));

      const res = await fetchApi('/dashboards', {
        method: 'POST',
        body: JSON.stringify({
          name: newDashName,
          description: newDashDesc,
          widgets
        })
      });
      setNewDashName('');
      setNewDashDesc('');
      await loadData();
      setActiveDashboardId(res.id);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleAddInsightToDashboard = async (insightId: string) => {
    if (!activeDashboard) return;
    try {
      const newWidget = { insight_id: insightId, x: 0, y: Infinity, w: 6, h: 4 };
      const updatedWidgets = [...activeDashboard.widgets, newWidget];
      await fetchApi(`/dashboards/${activeDashboard.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ widgets: updatedWidgets })
      });
      await loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleRemoveWidget = async (widgetId: string) => {
    if (!activeDashboard) return;
    try {
      const updatedWidgets = activeDashboard.widgets.filter((w: any) => w.id !== widgetId && w.insight_id !== widgetId);
      await fetchApi(`/dashboards/${activeDashboard.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ widgets: updatedWidgets })
      });
      await loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const exportToCSV = (data: any[], filename: string) => {
    if (!data || data.length === 0) return;
    const keys = Object.keys(data[0]);
    const csvContent = [
      keys.join(','),
      ...data.map(row => keys.map(k => JSON.stringify(row[k] || '')).join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', `${filename}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const activeDashboard = dashboards.find(d => d.id === activeDashboardId);

  const onLayoutChange = async (layout: any) => {
    if (!isEditMode || !activeDashboard) return;
    try {
      const updatedWidgets = activeDashboard.widgets.map((w: any) => {
        const item = layout.find((l: any) => l.i === (w.id || w.insight_id));
        if (item) {
          return { ...w, x: item.x, y: item.y, w: item.w, h: item.h };
        }
        return w;
      });
      await fetchApi(`/dashboards/${activeDashboard.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ widgets: updatedWidgets })
      });
      // Updating local state to avoid flicker before API fetch completes
      setDashboards(d => d.map(dash => dash.id === activeDashboard.id ? { ...dash, widgets: updatedWidgets } : dash));
    } catch (e) {
      console.error("Failed to save layout", e);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', height: '100%' }}>
      {/* Sidebar for Dashboards & Insights */}
      <div style={{ width: '280px', display: 'flex', flexDirection: 'column', gap: '1.5rem', flexShrink: 0 }}>
        <div>
          <h2 className="title" style={{ margin: 0, fontSize: '1.25rem' }}>
            <LayoutDashboard size={20} style={{ color: 'var(--primary)' }} /> Dashboards
          </h2>
        </div>

        <div className="card" style={{ padding: '1rem' }}>
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
            <Plus size={16} /> New Dashboard
          </h3>
          <form onSubmit={handleCreateDashboard}>
            <div className="form-group" style={{ marginBottom: '0.75rem' }}>
              <input value={newDashName} onChange={e => setNewDashName(e.target.value)} required placeholder="Dashboard Name" style={{ padding: '0.5rem', fontSize: '0.85rem' }} />
            </div>
            <div className="form-group" style={{ marginBottom: '0.75rem' }}>
              <input value={newDashDesc} onChange={e => setNewDashDesc(e.target.value)} placeholder="Description" style={{ padding: '0.5rem', fontSize: '0.85rem' }} />
            </div>
            <button type="submit" style={{ width: '100%', padding: '0.5rem', fontSize: '0.85rem' }}>Create</button>
          </form>
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', paddingRight: '0.5rem' }}>
          <div>
            <h3 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
              Your Dashboards
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {dashboards.map(d => (
                <div 
                  key={d.id} 
                  onClick={() => setActiveDashboardId(d.id)}
                  style={{ 
                    padding: '0.5rem 0.75rem', 
                    borderRadius: 'var(--radius-sm)', 
                    cursor: 'pointer',
                    background: activeDashboardId === d.id ? 'rgba(79, 70, 229, 0.1)' : 'transparent',
                    color: activeDashboardId === d.id ? 'var(--primary)' : 'var(--text-main)',
                    fontWeight: activeDashboardId === d.id ? 500 : 400,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    transition: 'all 0.2s'
                  }}
                  className="hover-bg-light"
                >
                  <LayoutGrid size={16} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</span>
                </div>
              ))}
              {dashboards.length === 0 && !loading && (
                <div className="text-muted text-sm text-center py-2">No dashboards yet.</div>
              )}
              {loading && dashboards.length === 0 && (
                <div className="skeleton" style={{ height: '36px', borderRadius: '4px' }} />
              )}
            </div>
          </div>

          <div>
            <h3 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
              Saved Insights Library
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {insights.map(i => (
                <div key={i.id} style={{ padding: '0.75rem', background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', position: 'relative' }} className="group">
                  <div style={{ fontWeight: 500, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Bookmark size={14} className="text-secondary" /> {i.name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {i.query}
                  </div>
                  {activeDashboard && isEditMode && (
                    <button 
                      onClick={() => handleAddInsightToDashboard(i.id)}
                      className="btn-ghost" 
                      style={{ position: 'absolute', right: '0.25rem', top: '0.25rem', padding: '0.25rem', opacity: 0.5 }}
                      title="Add to active dashboard"
                    >
                      <Plus size={14} />
                    </button>
                  )}
                </div>
              ))}
              {insights.length === 0 && !loading && <div className="text-muted text-center text-sm">No saved insights yet.</div>}
              {loading && insights.length === 0 && (
                <div className="skeleton" style={{ height: '60px', borderRadius: '4px' }} />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Dashboard Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}>
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted">
            <div className="skeleton" style={{ width: '100%', height: '100%', borderRadius: 'var(--radius)' }} />
          </div>
        ) : !activeDashboard ? (
          <div className="flex items-center justify-center h-full text-muted flex-col gap-4">
            <LayoutDashboard size={48} style={{ opacity: 0.2 }} />
            <p>Select or create a dashboard to view insights.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div className="flex justify-between items-center mb-6">
              <div>
                <h1 style={{ fontSize: '1.75rem', margin: 0 }}>{activeDashboard.name}</h1>
                <p className="text-muted mt-1">{activeDashboard.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <button className={`btn-${isEditMode ? 'primary' : 'secondary'}`} onClick={() => setIsEditMode(!isEditMode)}>
                  {isEditMode ? 'Done Editing' : 'Edit Layout'}
                </button>
                <button className="btn-ghost" title="Refresh Data" onClick={loadData}><RefreshCw size={18} /></button>
                <button className="btn-ghost" title="Export Dashboard"><Download size={18} /></button>
                <button className="btn-ghost" title="Settings"><Settings size={18} /></button>
              </div>
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {activeDashboard.widgets.length === 0 ? (
                <div className="flex items-center justify-center text-muted" style={{ height: '300px', border: '1px dashed var(--border-color)', borderRadius: 'var(--radius)', background: 'var(--bg-card)' }}>
                  <div className="text-center">
                    <AlertCircle size={32} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
                    <p>This dashboard is empty.</p>
                    <p className="text-sm mt-1">Click "Edit Layout" and add insights from the library.</p>
                  </div>
                </div>
              ) : (
                /* @ts-ignore */
                <ResponsiveGridLayout 
                  className="layout" 
                  layouts={{ lg: activeDashboard.widgets.map((w: any) => ({ i: w.id || w.insight_id, x: w.x, y: w.y, w: w.w, h: w.h })) }} 
                  breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                  cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                  rowHeight={80} 
                  // @ts-ignore
                  isDraggable={isEditMode}
                  // @ts-ignore
                  isResizable={isEditMode}
                  onLayoutStop={onLayoutChange}
                  margin={[16, 16]}
                  useCSSTransforms={true}
                >
                  {activeDashboard.widgets.map((w: any) => {
                    const wid = w.id || w.insight_id;
                    const ins = insights.find(i => i.id === w.insight_id) || w.insight;
                    if (!ins) return <div key={wid} />;
                    
                    const isFullScreen = fullScreenWidgetId === wid;
                    
                    return (
                      <div 
                        key={wid} 
                        className="card" 
                        style={{ 
                          padding: 0, 
                          display: 'flex', 
                          flexDirection: 'column', 
                          border: isEditMode ? '1px dashed var(--primary)' : '1px solid var(--border-color)',
                          boxShadow: isEditMode ? '0 0 0 1px rgba(79, 70, 229, 0.2)' : undefined,
                          ...(isFullScreen ? {
                            position: 'fixed',
                            top: '2rem',
                            left: '2rem',
                            right: '2rem',
                            bottom: '2rem',
                            zIndex: 9999,
                            background: 'var(--bg-card)'
                          } : {})
                        }}
                      >
                        <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-dark)' }} className={isEditMode ? 'cursor-move' : ''}>
                          <div style={{ overflow: 'hidden' }}>
                            <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{ins.name}</h4>
                          </div>
                          <div className="flex gap-1">
                            {isEditMode && (
                              <button className="btn-ghost text-error" style={{ padding: '0.25rem' }} onClick={() => handleRemoveWidget(wid)} title="Remove Widget">
                                <Trash2 size={14} />
                              </button>
                            )}
                            <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={() => setFullScreenWidgetId(isFullScreen ? null : wid)} title="Toggle Fullscreen">
                              {isFullScreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                            </button>
                            <div style={{ position: 'relative' }}>
                              <button className="btn-ghost" style={{ padding: '0.25rem' }} onClick={() => setShowMenuForWidget(showMenuForWidget === wid ? null : wid)}>
                                <MoreVertical size={14} />
                              </button>
                              {showMenuForWidget === wid && (
                                <div style={{ position: 'absolute', right: 0, top: '100%', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', boxShadow: 'var(--shadow-md)', zIndex: 100, minWidth: '120px', overflow: 'hidden' }}>
                                  <button className="btn-ghost" style={{ width: '100%', justifyContent: 'flex-start', padding: '0.5rem 1rem', borderRadius: 0, fontSize: '0.85rem' }} onClick={() => { exportToCSV(ins.chart_config?.data, ins.name); setShowMenuForWidget(null); }}>
                                    <Table2 size={14} style={{ marginRight: '0.5rem' }} /> Export CSV
                                  </button>
                                  <button className="btn-ghost" style={{ width: '100%', justifyContent: 'flex-start', padding: '0.5rem 1rem', borderRadius: 0, fontSize: '0.85rem' }} onClick={() => { 
                                    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(ins.chart_config));
                                    const a = document.createElement('a'); a.href = dataStr; a.download = `${ins.name}.json`; a.click(); 
                                    setShowMenuForWidget(null); 
                                  }}>
                                    <FileJson size={14} style={{ marginRight: '0.5rem' }} /> Export JSON
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                        <div style={{ flex: 1, padding: '1rem', overflow: 'hidden', minHeight: 0 }}>
                          {ins.chart_config ? (
                            <ChartRenderer data={ins.chart_config.data} chartType={ins.chart_config.chartType} />
                          ) : (
                            <div className="flex items-center justify-center h-full text-muted">No visualization data</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </ResponsiveGridLayout>
              )}
            </div>
            
            {/* Fullscreen Overlay Backdrop */}
            {fullScreenWidgetId && (
              <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 9998 }} onClick={() => setFullScreenWidgetId(null)} />
            )}
          </div>
        )}
      </div>
    </div>
  );
};
