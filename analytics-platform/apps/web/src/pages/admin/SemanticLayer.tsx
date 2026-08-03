import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { BookOpen, Layers, GitBranch, Book, Activity, Plus, History, X, Search, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

export const SemanticLayer = () => {
  const [activeTab, setActiveTab] = useState('metrics');
  const [metrics, setMetrics] = useState<any[]>([]);
  const [dimensions, setDimensions] = useState<any[]>([]);
  const [joins, setJoins] = useState<any[]>([]);
  const [glossary, setGlossary] = useState<any[]>([]);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false);
  
  const [name, setName] = useState('');
  const [isCalculated, setIsCalculated] = useState(false);
  const [expression, setExpression] = useState('');
  const [aggregation, setAggregation] = useState('SUM');
  
  const [dimName, setDimName] = useState('');
  const [dimType, setDimType] = useState('TEXT');
  
  const [term, setTerm] = useState('');
  const [definition, setDefinition] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [selectedMetric, setSelectedMetric] = useState<any>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [schemaMetadata, setSchemaMetadata] = useState<{ 
    database_name?: string;
    status?: string;
    generated_at?: string;
    table_count?: number;
    column_count?: number;
    relationship_count?: number;
    schema_name?: string; 
    last_updated?: string; 
  } | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [refreshingSchema, setRefreshingSchema] = useState(false);
  const [schemaError, setSchemaError] = useState('');
  const [draftMetrics, setDraftMetrics] = useState<any[]>([]);
  const [draftDimensions, setDraftDimensions] = useState<any[]>([]);
  const [draftRelationships, setDraftRelationships] = useState<any[]>([]);
  const [draftJoinPaths, setDraftJoinPaths] = useState<any[]>([]);
  const [regeneratingSemantic, setRegeneratingSemantic] = useState(false);

  const formatLastUpdated = (isoString?: string, showSeconds = false, showMs = false) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;

    const day = date.getDate().toString().padStart(2, '0');
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const month = monthNames[date.getMonth()];
    const year = date.getFullYear();

    let hours = date.getHours();
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    const ms = date.getMilliseconds().toString().padStart(3, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    const strHours = hours.toString().padStart(2, '0');

    let timeStr = `${strHours}:${minutes} ${ampm}`;
    if (showMs) {
      timeStr = `${strHours}:${minutes}:${seconds}.${ms} ${ampm}`;
    } else if (showSeconds) {
      timeStr = `${strHours}:${minutes}:${seconds} ${ampm}`;
    }
    return `${day} ${month} ${year}, ${timeStr}`;
  };

  const loadData = async () => {
    setLoading(true);
    setSchemaLoading(true);
    setSchemaError('');
    try {
      const [mRes, dRes, jRes, gRes, metaRes, draftRes] = await Promise.all([
        fetchApi('/semantic/metrics').catch(() => []),
        fetchApi('/semantic/dimensions').catch(() => []),
        fetchApi('/semantic/joins').catch(() => []),
        fetchApi('/semantic/glossary').catch(() => []),
        fetchApi('/schema/metadata').catch(() => fetchApi('/semantic/schema-metadata')).catch(() => null),
        fetchApi('/api/v1/semantic-layer').catch(() => null)
      ]);
      setMetrics(mRes);
      setDimensions(dRes);
      setJoins(jRes);
      setGlossary(gRes);
      if (draftRes) {
        setSchemaMetadata(draftRes);
        if (draftRes.metrics) setDraftMetrics(draftRes.metrics);
        if (draftRes.dimensions) setDraftDimensions(draftRes.dimensions);
        if (draftRes.relationships) setDraftRelationships(draftRes.relationships);
        if (draftRes.join_paths) setDraftJoinPaths(draftRes.join_paths);
      } else if (metaRes) {
        setSchemaMetadata(metaRes);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setSchemaLoading(false);
    }
  };

  const handleRefreshSchema = async () => {
    setRefreshingSchema(true);
    setSchemaError('');
    try {
      const metaRes = await fetchApi('/schema/refresh', { method: 'POST' });
      setSchemaMetadata(metaRes);
      await loadData();
    } catch (err: any) {
      setSchemaError(err.message || 'Failed to refresh schema');
    } finally {
      setRefreshingSchema(false);
    }
  };

  const handleRegenerateSemanticLayer = async () => {
    setRegeneratingSemantic(true);
    setSchemaError('');
    try {
      const draftRes = await fetchApi('/api/v1/semantic-layer/regenerate', { method: 'POST' });
      setSchemaMetadata(draftRes);
      if (draftRes.metrics) setDraftMetrics(draftRes.metrics);
      if (draftRes.dimensions) setDraftDimensions(draftRes.dimensions);
      if (draftRes.relationships) setDraftRelationships(draftRes.relationships);
      if (draftRes.join_paths) setDraftJoinPaths(draftRes.join_paths);
      await loadData();
    } catch (err: any) {
      setSchemaError(err.message || 'Failed to regenerate semantic layer');
    } finally {
      setRegeneratingSemantic(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredMetrics = (draftMetrics.length > 0 ? draftMetrics : metrics).filter(m => (m.metric_name || m.name || '').toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredDimensions = (draftDimensions.length > 0 ? draftDimensions : dimensions).filter(d => (d.dimension_name || d.business_name || d.name || '').toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredGlossary = glossary.filter(g => (g.term || '').toLowerCase().includes(searchQuery.toLowerCase()) || (g.business_definition || '').toLowerCase().includes(searchQuery.toLowerCase()));

  // Simple formula validation: check for balanced parentheses and non-empty
  const isFormulaValid = (expr: string) => {
    if (!expr.trim()) return false;
    let count = 0;
    for (let char of expr) {
      if (char === '(') count++;
      if (char === ')') count--;
      if (count < 0) return false;
    }
    return count === 0;
  };

  const handleCreateMetric = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    
    if (!name.trim()) return setError('Name is required');
    if (!expression.trim()) return setError('Formula/Expression is required');
    if (isCalculated && !isFormulaValid(expression)) return setError('Invalid formula (check parentheses)');
    
    try {
      await fetchApi('/semantic/metrics', {
        method: 'POST',
        body: JSON.stringify({
          name,
          is_calculated: isCalculated,
          expression,
          aggregation_type: isCalculated ? 'CUSTOM' : aggregation,
          business_name: name
        })
      });
      setName('');
      setExpression('');
      setSuccess('Metric created successfully!');
      setTimeout(() => {
        setIsSidePanelOpen(false);
        setSuccess('');
      }, 1000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create metric');
    }
  };

  const handleCreateDimension = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!dimName.trim()) return setError('Dimension name is required');
    
    try {
      await fetchApi('/semantic/dimensions', {
        method: 'POST',
        body: JSON.stringify({ business_name: dimName, data_type: dimType })
      });
      setDimName('');
      setSuccess('Dimension created successfully!');
      setTimeout(() => {
        setIsSidePanelOpen(false);
        setSuccess('');
      }, 1000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create dimension');
    }
  };

  const handleCreateGlossary = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!term.trim() || !definition.trim()) return setError('Term and definition are required');
    
    try {
      await fetchApi('/semantic/glossary', {
        method: 'POST',
        body: JSON.stringify({ term, business_definition: definition })
      });
      setTerm('');
      setDefinition('');
      setSuccess('Term added successfully!');
      setTimeout(() => {
        setIsSidePanelOpen(false);
        setSuccess('');
      }, 1000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to add glossary term');
    }
  };
  
  const handleSelectMetric = async (m: any) => {
    setSelectedMetric(m);
    try {
      const v = await fetchApi(`/semantic/metrics/${m.id}/versions`);
      setVersions(v);
    } catch (e) {
      console.error(e);
    }
  };
  
  const handleRollback = async (version: number) => {
    if (!selectedMetric) return;
    try {
      await fetchApi(`/semantic/metrics/${selectedMetric.id}/rollback?version=${version}`, { method: 'POST' });
      setSelectedMetric(null);
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BookOpen className="text-primary" size={24} /> Semantic Layer
          </h1>
          <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>
            Deterministic candidate semantic objects extracted from database catalog (Draft State).
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field"
              style={{ paddingLeft: '2.5rem', width: '250px' }}
            />
          </div>
          {activeTab !== 'joins' && (
            <button className="btn-primary" onClick={() => { setIsSidePanelOpen(true); setError(''); setSuccess(''); }}>
              <Plus size={18} /> Create {activeTab.charAt(0).toUpperCase() + activeTab.slice(1, -1)}
            </button>
          )}
        </div>
      </div>

      {/* Schema Metadata Panel */}
      <div style={{
        display: 'flex',
        gap: '1.75rem',
        alignItems: 'center',
        padding: '0.75rem 1.25rem',
        marginBottom: '1.25rem',
        backgroundColor: 'var(--bg-input, #1e1e2d)',
        borderRadius: 'var(--radius-sm, 6px)',
        border: '1px solid var(--border-color, #2b2b40)'
      }}>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #888)', fontWeight: 500, marginBottom: '0.2rem' }}>Database Name</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main, #fff)' }}>
            {schemaLoading ? 'Loading...' : (schemaMetadata?.database_name || 'analytics_db')}
          </div>
        </div>

        <div style={{ borderLeft: '1px solid var(--border-color, #2b2b40)', paddingLeft: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #888)', fontWeight: 500, marginBottom: '0.2rem' }}>Schema Status</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--warning, #f59e0b)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            {schemaLoading ? 'Loading...' : (
              <>
                {schemaMetadata?.status || 'Draft'} <CheckCircle2 size={15} />
              </>
            )}
          </div>
        </div>

        <div style={{ borderLeft: '1px solid var(--border-color, #2b2b40)', paddingLeft: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #888)', fontWeight: 500, marginBottom: '0.2rem' }}>Schema Generated At</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main, #fff)' }}>
            {schemaLoading ? (
              <span style={{ color: 'var(--text-muted, #888)' }}>Loading...</span>
            ) : schemaError ? (
              <span style={{ color: 'var(--danger, #ef4444)' }}>Error loading metadata</span>
            ) : (
              formatLastUpdated(schemaMetadata?.generated_at || schemaMetadata?.last_updated)
            )}
          </div>
        </div>

        <div style={{ borderLeft: '1px solid var(--border-color, #2b2b40)', paddingLeft: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #888)', fontWeight: 500, marginBottom: '0.2rem' }}>Tables</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main, #fff)' }}>
            {schemaLoading ? '...' : (schemaMetadata?.table_count ?? 0)}
          </div>
        </div>

        <div style={{ borderLeft: '1px solid var(--border-color, #2b2b40)', paddingLeft: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #888)', fontWeight: 500, marginBottom: '0.2rem' }}>Columns</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main, #fff)' }}>
            {schemaLoading ? '...' : (schemaMetadata?.column_count ?? 0)}
          </div>
        </div>

        <div style={{ borderLeft: '1px solid var(--border-color, #2b2b40)', paddingLeft: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #888)', fontWeight: 500, marginBottom: '0.2rem' }}>Relationships</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main, #fff)' }}>
            {schemaLoading ? '...' : (schemaMetadata?.relationship_count ?? 0)}
          </div>
        </div>

        <div style={{ borderLeft: '1px solid var(--border-color, #2b2b40)', paddingLeft: '1.25rem', display: 'flex', gap: '0.5rem', marginLeft: 'auto' }}>
          <button
            onClick={handleRegenerateSemanticLayer}
            disabled={regeneratingSemantic || schemaLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 0.85rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              borderRadius: '6px',
              backgroundColor: 'var(--primary, #6366f1)',
              color: '#fff',
              border: 'none',
              cursor: (regeneratingSemantic || schemaLoading) ? 'not-allowed' : 'pointer'
            }}
          >
            <RefreshCw size={14} style={{ animation: regeneratingSemantic ? 'spin 1s linear infinite' : 'none' }} />
            {regeneratingSemantic ? 'Regenerating...' : 'Regenerate Semantic Layer'}
          </button>

          <button
            onClick={handleRefreshSchema}
            disabled={refreshingSchema || schemaLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 0.85rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              borderRadius: '6px',
              backgroundColor: 'var(--bg-card, #2b2b40)',
              color: 'var(--text-main, #fff)',
              border: '1px solid var(--border-color, #3b3b54)',
              cursor: (refreshingSchema || schemaLoading) ? 'not-allowed' : 'pointer'
            }}
          >
            <RefreshCw size={14} style={{ animation: refreshingSchema ? 'spin 1s linear infinite' : 'none' }} />
            {refreshingSchema ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        {[
          { id: 'dimensions', label: 'Dimensions', icon: <Layers size={16} />, count: dimensions.length },
          { id: 'joins', label: 'Joins', icon: <GitBranch size={16} />, count: joins.length },
          { id: 'glossary', label: 'Glossary', icon: <Book size={16} />, count: glossary.length }
        ].map(t => (
          <button 
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{ 
              background: activeTab === t.id ? 'var(--bg-input)' : 'transparent',
              color: activeTab === t.id ? 'var(--text-main)' : 'var(--text-muted)',
              border: activeTab === t.id ? '1px solid var(--border-color)' : '1px solid transparent',
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontWeight: 600,
              borderBottom: activeTab === t.id ? '2px solid var(--primary)' : '1px solid transparent',
              transition: 'all 0.2s'
            }}
          >
            {t.icon} {t.label}
            <span className="badge badge-default" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}>{t.count}</span>
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column' }}>
        {loading ? (
          <div className="flex items-center justify-center h-full" style={{ minHeight: '300px' }}>
            <div className="spinner" />
          </div>
        ) : (
          <div className="table-container" style={{ border: 'none', borderRadius: 0, flex: 1, overflowY: 'auto' }}>
            {activeTab === 'metrics' && (
              <table>
                <thead>
                  <tr>
                    <th>Metric Name</th>
                    <th>Type</th>
                    <th>Dependencies</th>
                    <th>Expression</th>
                    <th>Version</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMetrics.map(m => (
                    <tr key={m.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <Activity size={16} color="var(--primary)" />
                          <span style={{ fontWeight: 600 }}>{m.name}</span>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-default">{m.is_calculated ? 'Calculated' : 'Base'}</span>
                      </td>
                      <td>
                        <div className="flex gap-1 flex-wrap">
                          {m.source_table_id ? <span className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>Table Ref</span> : <span className="text-muted text-sm">None</span>}
                        </div>
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{m.expression}</td>
                      <td><span className="badge badge-primary">v{m.version}</span></td>
                      <td>
                        <div className="flex items-center justify-end">
                          <button className="btn-ghost" onClick={() => handleSelectMetric(m)} style={{ padding: '0.5rem' }} title="Version History">
                            <History size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredMetrics.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center p-8 text-muted">
                        <Activity size={32} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
                        No metrics found matching your criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            {activeTab === 'dimensions' && (
              <table>
                <thead><tr><th>Dimension Name</th><th>Dependencies</th><th>Data Type</th><th>Version</th></tr></thead>
                <tbody>
                  {filteredDimensions.map(d => (
                    <tr key={d.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <Layers size={16} color="var(--success)" />
                          <span style={{ fontWeight: 600 }}>{d.business_name}</span>
                        </div>
                      </td>
                      <td>
                        {d.source_table_id ? <span className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>Table Ref</span> : <span className="text-muted text-sm">-</span>}
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{d.data_type}</td>
                      <td><span className="badge badge-primary">v{d.version}</span></td>
                    </tr>
                  ))}
                  {filteredDimensions.length === 0 && (
                    <tr>
                      <td colSpan={4} className="text-center p-8 text-muted">
                        <Layers size={32} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
                        No dimensions found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            {activeTab === 'joins' && (
              <table>
                <thead><tr><th>Join Condition</th><th>Type</th><th>AI Confidence</th></tr></thead>
                <tbody>
                  {joins.map(j => (
                    <tr key={j.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <GitBranch size={16} color="var(--warning)" />
                          <span style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{j.join_condition}</span>
                        </div>
                      </td>
                      <td><span className="badge badge-default">{j.join_type}</span></td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div style={{ width: '80px', height: '6px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ width: `${j.confidence * 100}%`, height: '100%', background: j.confidence > 0.8 ? 'var(--success)' : 'var(--warning)' }} />
                          </div>
                          <span className="text-sm font-medium">{(j.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {joins.length === 0 && (
                    <tr>
                      <td colSpan={3} className="text-center p-8 text-muted">
                        <GitBranch size={32} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
                        No joins detected or approved.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            {activeTab === 'glossary' && (
              <table>
                <thead><tr><th>Business Term</th><th>Definition</th></tr></thead>
                <tbody>
                  {filteredGlossary.map(g => (
                    <tr key={g.id}>
                      <td style={{ width: '30%' }}>
                        <div className="flex items-center gap-2">
                          <Book size={16} color="var(--secondary)" />
                          <span style={{ fontWeight: 600 }}>{g.term}</span>
                        </div>
                      </td>
                      <td className="text-muted" style={{ lineHeight: 1.5 }}>{g.business_definition}</td>
                    </tr>
                  ))}
                  {filteredGlossary.length === 0 && (
                    <tr>
                      <td colSpan={2} className="text-center p-8 text-muted">
                        <Book size={32} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
                        No glossary terms found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Slide-out Panel for Creation */}
      <div className={`side-panel ${isSidePanelOpen ? 'open' : ''}`}>
        <div className="side-panel-header">
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Plus size={18} /> Create {activeTab.charAt(0).toUpperCase() + activeTab.slice(1, -1)}
          </h3>
          <button className="btn-ghost" onClick={() => setIsSidePanelOpen(false)} style={{ padding: '0.25rem' }}>
            <X size={20} />
          </button>
        </div>
        <div className="side-panel-content">
          {error && (
            <div className="badge badge-danger mb-4 flex items-start gap-2" style={{ padding: '1rem', width: '100%', borderRadius: 'var(--radius-sm)' }}>
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>{error}</div>
            </div>
          )}
          {success && (
            <div className="badge badge-success mb-4 flex items-center gap-2" style={{ padding: '1rem', width: '100%', borderRadius: 'var(--radius-sm)' }}>
              <CheckCircle2 size={16} />
              <div>{success}</div>
            </div>
          )}
          
          {activeTab === 'metrics' && (
            <form onSubmit={handleCreateMetric} className="flex flex-col gap-4">
              <div className="form-group">
                <label>Metric Name <span className="text-error">*</span></label>
                <input value={name} onChange={e => setName(e.target.value)} required placeholder="e.g. Monthly Revenue" autoFocus />
              </div>
              <div className="form-group" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', background: 'var(--bg-input)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                <input type="checkbox" id="calc" checked={isCalculated} onChange={e => setIsCalculated(e.target.checked)} style={{ width: '1.25rem', height: '1.25rem', cursor: 'pointer' }} />
                <label htmlFor="calc" style={{ margin: 0, cursor: 'pointer', userSelect: 'none' }}>This is a Calculated Metric</label>
              </div>
              {!isCalculated && (
                <div className="form-group">
                  <label>Base Aggregation</label>
                  <select value={aggregation} onChange={e => setAggregation(e.target.value)}>
                    <option value="SUM">SUM (Total)</option>
                    <option value="AVG">AVG (Average)</option>
                    <option value="COUNT">COUNT (Rows)</option>
                    <option value="MAX">MAX (Highest)</option>
                    <option value="MIN">MIN (Lowest)</option>
                  </select>
                </div>
              )}
              <div className="form-group">
                <label>Formula / Expression <span className="text-error">*</span></label>
                <div style={{ position: 'relative' }}>
                  <input 
                    value={expression} 
                    onChange={e => setExpression(e.target.value)} 
                    required 
                    placeholder={isCalculated ? "e.g. (sum(revenue) - sum(cost)) / sum(revenue)" : "e.g. amount"} 
                    style={{ 
                      fontFamily: 'monospace', 
                      width: '100%', 
                      border: isCalculated && expression && !isFormulaValid(expression) ? '1px solid var(--error)' : undefined 
                    }} 
                  />
                  {isCalculated && expression && (
                    <div style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}>
                      {isFormulaValid(expression) ? <CheckCircle2 size={16} className="text-success" /> : <span title="Invalid parentheses"><AlertCircle size={16} className="text-error" /></span>}
                    </div>
                  )}
                </div>
                <div className="text-xs text-muted mt-1">Use valid SQL syntax appropriate for your data source.</div>
              </div>
              <button type="submit" className="btn-primary" style={{ marginTop: '1rem' }}>Create Metric</button>
            </form>
          )}

          {activeTab === 'dimensions' && (
            <form onSubmit={handleCreateDimension} className="flex flex-col gap-4">
              <div className="form-group">
                <label>Dimension Name <span className="text-error">*</span></label>
                <input value={dimName} onChange={e => setDimName(e.target.value)} required placeholder="e.g. User Region" autoFocus />
              </div>
              <div className="form-group">
                <label>Data Type</label>
                <select value={dimType} onChange={e => setDimType(e.target.value)}>
                  <option value="TEXT">TEXT / VARCHAR</option>
                  <option value="INTEGER">INTEGER / NUMERIC</option>
                  <option value="DATE">DATE / TIMESTAMP</option>
                  <option value="BOOLEAN">BOOLEAN</option>
                </select>
              </div>
              <button type="submit" className="btn-primary" style={{ marginTop: '1rem' }}>Create Dimension</button>
            </form>
          )}

          {activeTab === 'glossary' && (
            <form onSubmit={handleCreateGlossary} className="flex flex-col gap-4">
              <div className="form-group">
                <label>Term <span className="text-error">*</span></label>
                <input value={term} onChange={e => setTerm(e.target.value)} required placeholder="e.g. Churned User" autoFocus />
              </div>
              <div className="form-group">
                <label>Business Definition <span className="text-error">*</span></label>
                <textarea 
                  value={definition} 
                  onChange={e => setDefinition(e.target.value)} 
                  required 
                  rows={8} 
                  style={{ resize: 'vertical' }} 
                  placeholder="Provide a clear, business-friendly definition that anyone in the company can understand..." 
                />
              </div>
              <button type="submit" className="btn-primary" style={{ marginTop: '1rem' }}>Add Term</button>
            </form>
          )}
        </div>
      </div>

      {/* Version History Modal Overlay */}
      {selectedMetric && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(8px)' }}>
          <div className="card animate-slide-up" style={{ width: '700px', maxWidth: '95%', padding: '2rem', display: 'flex', flexDirection: 'column', maxHeight: '80vh' }}>
            <div className="flex justify-between items-center mb-6">
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <History size={20} className="text-primary" /> Version History: {selectedMetric.name}
              </h3>
              <button className="btn-ghost" onClick={() => setSelectedMetric(null)}><X size={20} /></button>
            </div>
            
            <div className="table-container" style={{ flex: 1, overflowY: 'auto', marginBottom: '1.5rem', border: '1px solid var(--border-color)' }}>
              <table>
                <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-dark)', zIndex: 10 }}>
                  <tr><th>Version</th><th>Reason</th><th>Author</th><th style={{ textAlign: 'right' }}>Action</th></tr>
                </thead>
                <tbody>
                  {versions.map(v => (
                    <tr key={v.id}>
                      <td><span className="badge badge-primary">v{v.version}</span></td>
                      <td className="text-sm">{v.change_reason || '-'}</td>
                      <td className="text-sm text-muted">{v.created_by}</td>
                      <td style={{ textAlign: 'right' }}>
                        {v.version !== selectedMetric.version ? (
                          <button className="btn-secondary" onClick={() => handleRollback(v.version)} style={{ padding: '0.4rem 0.75rem', fontSize: '0.75rem' }}>Rollback</button>
                        ) : (
                          <span className="badge badge-success">Current</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {versions.length === 0 && (
                    <tr>
                      <td colSpan={4} className="text-center p-4 text-muted">No version history available.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
