import React, { useState, useEffect } from 'react';

const fetchAuth = async (url: string, options: any = {}) => {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
    'Authorization': `Bearer ${token}`
  };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem('token');
    window.location.href = '/';
  }
  return res;
};

export const SemanticLayer = () => {
  const [activeTab, setActiveTab] = useState('metrics');
  const [metrics, setMetrics] = useState<any[]>([]);
  const [dimensions, setDimensions] = useState<any[]>([]);
  const [joins, setJoins] = useState<any[]>([]);
  const [glossary, setGlossary] = useState<any[]>([]);
  
  const [name, setName] = useState('');
  const [isCalculated, setIsCalculated] = useState(false);
  const [expression, setExpression] = useState('');
  const [aggregation, setAggregation] = useState('SUM');
  
  const [dimName, setDimName] = useState('');
  const [dimType, setDimType] = useState('TEXT');
  
  const [term, setTerm] = useState('');
  const [definition, setDefinition] = useState('');

  const [error, setError] = useState('');
  
  // Versions
  const [selectedMetric, setSelectedMetric] = useState<any>(null);
  const [versions, setVersions] = useState<any[]>([]);

  const loadData = async () => {
    const [mRes, dRes, jRes, gRes] = await Promise.all([
      fetchAuth('/semantic/metrics'),
      fetchAuth('/semantic/dimensions'),
      fetchAuth('/semantic/joins'),
      fetchAuth('/semantic/glossary')
    ]);
    if (mRes.ok) setMetrics(await mRes.json());
    if (dRes.ok) setDimensions(await dRes.json());
    if (jRes.ok) setJoins(await jRes.json());
    if (gRes.ok) setGlossary(await gRes.json());
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateMetric = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const payload = {
      name,
      is_calculated: isCalculated,
      expression,
      aggregation_type: isCalculated ? 'CUSTOM' : aggregation,
      business_name: name
    };
    const res = await fetchAuth('/semantic/metrics', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      setName('');
      setExpression('');
      loadData();
    } else {
      const data = await res.json();
      setError(data.detail || 'Failed to create metric');
    }
  };

  const handleCreateDimension = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetchAuth('/semantic/dimensions', {
      method: 'POST',
      body: JSON.stringify({ business_name: dimName, data_type: dimType })
    });
    if (res.ok) {
      setDimName('');
      loadData();
    }
  };

  const handleCreateGlossary = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetchAuth('/semantic/glossary', {
      method: 'POST',
      body: JSON.stringify({ term, business_definition: definition })
    });
    if (res.ok) {
      setTerm('');
      setDefinition('');
      loadData();
    }
  };
  
  const loadVersions = async (m: any) => {
    setSelectedMetric(m);
    const res = await fetchAuth(`/semantic/metrics/${m.id}/versions`);
    if (res.ok) setVersions(await res.json());
  };
  
  const handleRollback = async (version: number) => {
    if (!selectedMetric) return;
    const res = await fetchAuth(`/semantic/metrics/${selectedMetric.id}/rollback?version=${version}`, { method: 'POST' });
    if (res.ok) {
      setSelectedMetric(null);
      loadData();
    }
  };

  return (
    <div>
      <h2 className="card-title">Semantic Layer</h2>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        {['metrics', 'dimensions', 'joins', 'glossary'].map(t => (
          <button 
            key={t}
            onClick={() => setActiveTab(t)}
            style={{ 
              background: activeTab === t ? 'var(--primary)' : 'transparent',
              color: activeTab === t ? '#fff' : 'var(--text-color)',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === 'metrics' && (
        <div style={{ display: 'flex', gap: '2rem' }}>
          <div className="card" style={{ flex: 1 }}>
            <h3>Create Metric</h3>
            {error && <div className="badge badge-danger" style={{ marginBottom: '1rem', padding: '0.5rem', display: 'block' }}>{error}</div>}
            <form onSubmit={handleCreateMetric}>
              <div className="form-group">
                <label>Metric Name</label>
                <input value={name} onChange={e => setName(e.target.value)} required />
              </div>
              <div className="form-group" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input type="checkbox" id="calc" checked={isCalculated} onChange={e => setIsCalculated(e.target.checked)} />
                <label htmlFor="calc" style={{ margin: 0 }}>Is Calculated Metric?</label>
              </div>
              {!isCalculated && (
                <div className="form-group">
                  <label>Aggregation</label>
                  <select value={aggregation} onChange={e => setAggregation(e.target.value)}>
                    <option value="SUM">SUM</option>
                    <option value="AVG">AVG</option>
                    <option value="COUNT">COUNT</option>
                  </select>
                </div>
              )}
              <div className="form-group">
                <label>Formula / Expression</label>
                <input value={expression} onChange={e => setExpression(e.target.value)} required />
              </div>
              <button type="submit">Create Metric</button>
            </form>
          </div>
          
          <div className="card" style={{ flex: 2 }}>
            <h3>Existing Metrics</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Expression</th>
                  <th>Version</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map(m => (
                  <tr key={m.id}>
                    <td><strong>{m.name}</strong></td>
                    <td><span className="badge badge-default">{m.is_calculated ? 'Calculated' : 'Base'}</span></td>
                    <td style={{ fontFamily: 'monospace' }}>{m.expression}</td>
                    <td>v{m.version}</td>
                    <td><button onClick={() => loadVersions(m)} style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }}>History</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      
      {selectedMetric && (
        <div style={{ position: 'fixed', top: '10%', left: '25%', width: '50%', background: '#fff', border: '1px solid #ccc', padding: '1rem', zIndex: 100, borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
          <h3>Version History: {selectedMetric.name}</h3>
          <table className="table">
            <thead><tr><th>Version</th><th>Reason</th><th>Author</th><th>Action</th></tr></thead>
            <tbody>
              {versions.map(v => (
                <tr key={v.id}>
                  <td>v{v.version}</td>
                  <td>{v.change_reason}</td>
                  <td>{v.created_by}</td>
                  <td>
                    {v.version !== selectedMetric.version && (
                      <button onClick={() => handleRollback(v.version)} style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }}>Rollback</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button onClick={() => setSelectedMetric(null)} style={{ marginTop: '1rem' }}>Close</button>
        </div>
      )}

      {activeTab === 'dimensions' && (
        <div style={{ display: 'flex', gap: '2rem' }}>
          <div className="card" style={{ flex: 1 }}>
            <h3>Create Dimension</h3>
            <form onSubmit={handleCreateDimension}>
              <div className="form-group">
                <label>Dimension Name</label>
                <input value={dimName} onChange={e => setDimName(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Data Type</label>
                <select value={dimType} onChange={e => setDimType(e.target.value)}>
                  <option value="TEXT">TEXT</option>
                  <option value="INTEGER">INTEGER</option>
                  <option value="DATE">DATE</option>
                </select>
              </div>
              <button type="submit">Create Dimension</button>
            </form>
          </div>
          <div className="card" style={{ flex: 2 }}>
            <h3>Dimensions</h3>
            <table className="table">
              <thead><tr><th>Name</th><th>Type</th><th>Version</th></tr></thead>
              <tbody>
                {dimensions.map(d => <tr key={d.id}><td>{d.business_name}</td><td>{d.data_type}</td><td>v{d.version}</td></tr>)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'joins' && (
        <div className="card">
          <h3>Approved Joins</h3>
          <p style={{ color: 'var(--text-muted)' }}>Joins are typically auto-promoted from schema ingestion, but can be manually defined here.</p>
          <table className="table">
            <thead><tr><th>Condition</th><th>Type</th><th>Confidence</th></tr></thead>
            <tbody>
              {joins.map(j => <tr key={j.id}><td>{j.join_condition}</td><td>{j.join_type}</td><td>{j.confidence}</td></tr>)}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'glossary' && (
        <div style={{ display: 'flex', gap: '2rem' }}>
          <div className="card" style={{ flex: 1 }}>
            <h3>Create Glossary Term</h3>
            <form onSubmit={handleCreateGlossary}>
              <div className="form-group">
                <label>Term</label>
                <input value={term} onChange={e => setTerm(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Definition</label>
                <input value={definition} onChange={e => setDefinition(e.target.value)} required />
              </div>
              <button type="submit">Add Term</button>
            </form>
          </div>
          <div className="card" style={{ flex: 2 }}>
            <h3>Business Glossary</h3>
            <table className="table">
              <thead><tr><th>Term</th><th>Definition</th></tr></thead>
              <tbody>
                {glossary.map(g => <tr key={g.id}><td><strong>{g.term}</strong></td><td>{g.business_definition}</td></tr>)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
