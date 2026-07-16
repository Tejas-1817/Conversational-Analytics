import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Database, Plus, RefreshCw, MoreVertical, Play, Server, Clock, Trash2 } from 'lucide-react';
import { ConnectionModal } from '../../components/ConnectionModal';

export const DataSources = () => {
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const loadSources = () => {
    setLoading(true);
    fetchApi('/sources')
      .then(data => {
        setSources(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    loadSources();
  }, []);

  const triggerIngest = async (id: string) => {
    try {
      await fetchApi(`/jobs/ingest/${id}`, { method: 'POST' });
      alert('Ingestion triggered successfully!');
    } catch (e: any) {
      alert(`Failed to trigger ingestion: ${e.message}`);
    }
  };

  const deleteSource = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this data source?')) return;
    try {
      await fetchApi(`/sources/${id}`, { method: 'DELETE' });
      loadSources();
    } catch (e: any) {
      alert(`Failed to delete data source: ${e.message}`);
    }
  };

  return (
    <div onClick={() => setOpenMenuId(null)}>
      <ConnectionModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSuccess={loadSources} 
      />
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="title" style={{ margin: 0 }}>
            <Database size={24} style={{ color: 'var(--primary)' }} /> Data Sources
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Manage connections to your data warehouses and databases.
          </p>
        </div>
        <button onClick={() => setIsModalOpen(true)}><Plus size={18} /> Connect Data Source</button>
      </div>
      
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Source Name</th>
                <th>Database Type</th>
                <th>Connection Status</th>
                <th>Last Ingested</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center p-4">
                    <div className="skeleton" style={{ height: '40px', width: '100%', marginBottom: '10px' }} />
                    <div className="skeleton" style={{ height: '40px', width: '100%' }} />
                  </td>
                </tr>
              ) : sources.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center p-4 text-muted">
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', padding: '3rem' }}>
                      <Server size={48} style={{ opacity: 0.2 }} />
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>No Data Sources Connected</div>
                        <div>Connect your first data source to begin profiling metadata.</div>
                      </div>
                      <button className="btn-secondary mt-2" onClick={() => setIsModalOpen(true)}><Plus size={18} /> Connect Data Source</button>
                    </div>
                  </td>
                </tr>
              ) : (
                sources.map(s => (
                  <tr key={s.id}>
                    <td>
                      <div className="flex items-center gap-2">
                        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--bg-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Database size={16} color="var(--primary)" />
                        </div>
                        <span style={{ fontWeight: 600 }}>{s.name}</span>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-default" style={{ textTransform: 'capitalize' }}>{s.type}</span>
                    </td>
                    <td>
                      <span className={`badge ${s.status === 'connected' || s.status === 'registered' ? 'badge-success' : 'badge-warning'}`}>
                        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', marginRight: 6 }} />
                        {s.status}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-1 text-muted text-sm">
                        <Clock size={14} /> {s.last_ingested_at ? new Date(s.last_ingested_at).toLocaleDateString() : 'Never'}
                      </div>
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-2 relative">
                        <button className="btn-ghost" title="Run Ingestion" onClick={() => triggerIngest(s.id)} style={{ padding: '0.5rem' }}>
                          <Play size={16} />
                        </button>
                        <div className="relative">
                          <button 
                            className="btn-ghost" 
                            title="More Options" 
                            style={{ padding: '0.5rem' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(openMenuId === s.id ? null : s.id);
                            }}
                          >
                            <MoreVertical size={16} />
                          </button>
                          {openMenuId === s.id && (
                            <div className="absolute right-0 mt-1 w-32 rounded-md shadow-lg bg-gray-800 ring-1 ring-black ring-opacity-5 z-10" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                              <div className="py-1" role="menu" aria-orientation="vertical" aria-labelledby="options-menu">
                                <button
                                  className="block w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-gray-700 flex items-center gap-2"
                                  style={{ color: '#ef4444' }}
                                  role="menuitem"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    deleteSource(s.id);
                                    setOpenMenuId(null);
                                  }}
                                >
                                  <Trash2 size={14} /> Delete
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
