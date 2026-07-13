import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Activity, Clock, PlayCircle, RefreshCw } from 'lucide-react';

export const Jobs = () => {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchJobs = () => {
      fetchApi('/jobs')
        .then(data => {
          setJobs(Array.isArray(data) ? data : []);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    };
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="title" style={{ margin: 0 }}>
            <Activity size={24} style={{ color: 'var(--primary)' }} /> Ingestion Jobs
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Monitor automated schema introspection and data profiling tasks.
          </p>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Source ID</th>
                <th>Pipeline Stage</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="text-center p-4">
                    <div className="skeleton" style={{ height: '40px', width: '100%', marginBottom: '10px' }} />
                    <div className="skeleton" style={{ height: '40px', width: '100%' }} />
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center p-4 text-muted">
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', padding: '3rem' }}>
                      <Clock size={48} style={{ opacity: 0.2 }} />
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>No Jobs Running</div>
                        <div>Trigger ingestion on a Data Source to see it here.</div>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map(j => (
                  <tr key={j.id}>
                    <td>
                      <div className="flex items-center gap-2">
                        <PlayCircle size={16} color="var(--text-muted)" />
                        <span style={{ fontFamily: 'monospace', fontWeight: 500 }}>{j.id.slice(0, 8)}...</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{j.source_id.slice(0, 8)}...</td>
                    <td>
                      <span className="badge badge-default" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {j.stage}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${j.status === 'succeeded' ? 'badge-success' : j.status === 'failed' ? 'badge-danger' : 'badge-primary'}`}>
                        {j.status === 'running' || j.status === 'queued' ? (
                          <RefreshCw size={12} className="animate-spin" style={{ marginRight: 6, animation: 'spin 2s linear infinite' }} />
                        ) : (
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', marginRight: 6 }} />
                        )}
                        {j.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
