import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Database, Plus, RefreshCw, MoreVertical, Play, Server, Clock, Trash2 } from 'lucide-react';
import { ConnectionModal } from '../../components/ConnectionModal';
import { SourceLogo } from '../../components/SourceLogos';

export const DataSources = () => {
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const loadSources = async (isSilent = false) => {
    // Only show the skeleton loader on initial page mount, never during background auto-refresh
    if (!isSilent) setLoading(true);

    try {
      const [sourcesRes, reposRes] = await Promise.allSettled([
        fetchApi('/sources'),
        fetchApi('/code-repos'),
      ]);

      const regularSources = sourcesRes.status === 'fulfilled' && Array.isArray(sourcesRes.value) ? sourcesRes.value : [];
      const codeRepos = reposRes.status === 'fulfilled' && Array.isArray(reposRes.value) ? reposRes.value : [];

      const formattedRepos = codeRepos.map((r: any) => ({
        id: r.repo_id,
        name: r.name || r.url.split('/').pop()?.replace('.git', '') || 'Git Repository',
        database_name: r.url,
        type: 'github',
        // Dynamic status: shows 'cloning' / 'indexing' / 'connected'
        status: r.status || (r.last_ingested_at ? 'connected' : 'indexing'),
        last_ingested_at: r.last_ingested_at,
        is_code_repo: true,
      }));

      setSources([...regularSources, ...formattedRepos]);
    } catch {
      if (!isSilent) setSources([]);
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  useEffect(() => {
    // 1. Initial load (shows skeleton loader)
    loadSources(false);

    // 2. Background polling every 3 seconds (silent refresh without flickering)
    const interval = setInterval(() => {
      loadSources(true);
    }, 3000);
    return () => clearInterval(interval);
  }, []);


  const triggerIngest = async (source: any) => {
    try {
      if (source.is_code_repo) {
        await fetchApi(`/code-repos/${source.id}/sync`, { method: 'POST' });
        alert(`Repository sync & re-indexing queued for ${source.name}!`);
      } else {
        await fetchApi(`/jobs/ingest/${source.id}`, { method: 'POST' });
        alert('Ingestion triggered successfully!');
      }
      loadSources();
    } catch (e: any) {
      alert(`Failed to trigger ingestion: ${e.message}`);
    }
  };

  const deleteSource = async (source: any) => {
    if (!window.confirm(`Are you sure you want to delete ${source.name}?`)) return;
    try {
      if (source.is_code_repo) {
        await fetchApi(`/code-repos/${source.id}`, { method: 'DELETE' });
      } else {
        await fetchApi(`/sources/${source.id}`, { method: 'DELETE' });
      }
      loadSources();
    } catch (e: any) {
      alert(`Failed to delete: ${e.message}`);
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
            Data Sources
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Manage connections to your data warehouses, databases, and code repositories.
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
                <th>Database / Repo URL</th>
                <th>Source Type</th>
                <th>Connection Status</th>
                <th>Last Ingested</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center p-4">
                    <div className="skeleton" style={{ height: '40px', width: '100%', marginBottom: '10px' }} />
                    <div className="skeleton" style={{ height: '40px', width: '100%' }} />
                  </td>
                </tr>
              ) : sources.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center p-4 text-muted">
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', padding: '3rem' }}>
                      <Server size={48} style={{ opacity: 0.2 }} />
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>No Data Sources Connected</div>
                        <div>Connect your first data source or Git repository to begin profiling metadata.</div>
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
                          <SourceLogo type={s.type} size={20} />
                        </div>
                        <span style={{ fontWeight: 600 }}>{s.name}</span>
                      </div>
                    </td>
                    <td style={{ maxWidth: '280px' }}>
                      <span
                        title={s.is_code_repo ? s.database_name : undefined}
                        style={{
                          fontFamily: 'var(--font-mono, monospace)',
                          fontSize: '13px',
                          color: 'var(--text-main)',
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {s.is_code_repo
                          ? s.database_name
                          : s.database_name || (s.type === 'excel' ? (s.file_path ? s.file_path.split(/[/\\]/).pop() : 'Excel File') : '-')}
                      </span>
                    </td>

                    <td>
                      <span className="badge badge-default" style={{ textTransform: 'capitalize' }}>
                        {s.is_code_repo ? 'GitHub (GraphRAG)' : s.type}
                      </span>
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
                        <button
                          className="btn-ghost"
                          title={s.is_code_repo ? 'Sync & Re-index Repository' : 'Run Ingestion'}
                          onClick={() => triggerIngest(s)}
                          style={{ padding: '0.5rem' }}
                        >
                          <Play size={16} />
                        </button>
                        <button
                          className="btn-ghost"
                          title="Delete Source"
                          style={{ padding: '0.5rem', color: '#ef4444' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSource(s);
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
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
