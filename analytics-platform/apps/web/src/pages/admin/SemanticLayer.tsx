import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { BookOpen, Layers, GitBranch, Book, Activity, Plus, History, X, Search, CheckCircle2, AlertCircle } from 'lucide-react';

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

  const loadData = async () => {
    setLoading(true);
    try {
      const [mRes, dRes, jRes, gRes] = await Promise.all([
        fetchApi('/semantic/metrics').catch(() => []),
        fetchApi('/semantic/dimensions').catch(() => []),
        fetchApi('/semantic/joins').catch(() => []),
        fetchApi('/semantic/glossary').catch(() => [])
      ]);
      setMetrics(mRes);
      setDimensions(dRes);
      setJoins(jRes);
      setGlossary(gRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

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
      setError(err.message);
    }
  };

  const handleCreateGlossary = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!term.trim()) return setError('Term is required');
    if (!definition.trim()) return setError('Definition is required');
    
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
      setError(err.message);
    }
  };
  
  const loadVersions = async (m: any) => {
    setSelectedMetric(m);
    try {
      const v = await fetchApi(`/semantic/metrics/${m.id}/versions`);
      setVersions(v);
    } catch (e: any) {
      alert(e.message);
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

  const filteredMetrics = metrics.filter(m => m.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredDimensions = dimensions.filter(d => d.business_name.toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredGlossary = glossary.filter(g => g.term.toLowerCase().includes(searchQuery.toLowerCase()) || g.business_definition.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div style={{ position: 'relative', minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="title" style={{ margin: 0 }}>
            <BookOpen size={24} style={{ color: 'var(--primary)' }} /> Semantic Layer
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Define business logic, metrics, and terminology.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
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

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        {[
          { id: 'metrics', label: 'Metrics', icon: <Activity size={16} />, count: metrics.length },
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
                          <button className="btn-ghost" onClick={() => loadVersions(m)} style={{ padding: '0.5rem' }} title="Version History">
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
