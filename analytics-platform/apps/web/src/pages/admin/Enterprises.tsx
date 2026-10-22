import React, { useState, useEffect } from 'react';
import { fetchApi } from '../../services/api';
import { Building2, Plus, Users, ShieldAlert, CheckCircle, ShieldCheck, Loader2, X } from 'lucide-react';

export const Enterprises = () => {
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTenantForUsers, setSelectedTenantForUsers] = useState<any | null>(null);
  const [tenantUsers, setTenantUsers] = useState<any[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [plan, setPlan] = useState('enterprise');
  const [maxUsers, setMaxUsers] = useState(50);
  const [maxSources, setMaxSources] = useState(10);
  const [submitting, setSubmitting] = useState(false);

  const loadTenants = async () => {
    setLoading(true);
    try {
      const data = await fetchApi('/tenants');
      setTenants(Array.isArray(data) ? data : []);
    } catch (e: any) {
      console.error('Failed to load tenants', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenants();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetchApi('/tenants', {
        method: 'POST',
        body: JSON.stringify({
          name,
          slug: slug.toLowerCase().replace(/[^a-z0-9_-]/g, '-'),
          display_name: displayName || name,
          plan,
          max_users: Number(maxUsers),
          max_sources: Number(maxSources),
        }),
      });
      setShowCreateModal(false);
      setName('');
      setSlug('');
      setDisplayName('');
      loadTenants();
    } catch (err: any) {
      alert(err.message || 'Failed to create enterprise');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (tenant: any) => {
    const action = tenant.is_active ? 'suspend' : 'reactivate';
    if (!confirm(`Are you sure you want to ${action} ${tenant.display_name || tenant.name}?`)) return;
    try {
      await fetchApi(`/tenants/${tenant.id}/${action}`, { method: 'POST' });
      loadTenants();
    } catch (err: any) {
      alert(err.message || `Failed to ${action} enterprise`);
    }
  };

  const handleViewUsers = async (tenant: any) => {
    setSelectedTenantForUsers(tenant);
    setLoadingUsers(true);
    try {
      const data = await fetchApi(`/tenants/${tenant.id}/users`);
      setTenantUsers(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setTenantUsers([]);
    } finally {
      setLoadingUsers(false);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="title" style={{ margin: 0 }}>
            Enterprises
          </h2>
          <p className="subtitle" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
            Platform multi-tenant organization boundaries and tenancy isolation.
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => setShowCreateModal(true)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <Plus size={16} /> New Enterprise
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Enterprise</th>
                <th>Slug</th>
                <th>Plan</th>
                <th>Limits</th>
                <th>Status</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center p-4">
                    <div className="skeleton" style={{ height: '40px', width: '100%', marginBottom: '10px' }} />
                    <div className="skeleton" style={{ height: '40px', width: '100%' }} />
                  </td>
                </tr>
              ) : tenants.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No enterprises found.
                  </td>
                </tr>
              ) : (
                tenants.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div
                          style={{
                            width: 34,
                            height: 34,
                            borderRadius: 'var(--radius-sm)',
                            background: 'rgba(59, 130, 246, 0.1)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'var(--primary)',
                          }}
                        >
                          <Building2 size={18} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 600 }}>{t.display_name || t.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ID: {t.id}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <code style={{ fontSize: '0.8rem', background: 'var(--bg-dark)', padding: '2px 6px', borderRadius: '4px' }}>
                        {t.slug}
                      </code>
                    </td>
                    <td>
                      <span className="badge badge-default" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
                        {t.plan}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {t.max_users} users &bull; {t.max_sources} sources
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${t.is_active ? 'badge-success' : 'badge-warning'}`}>
                        <div
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: 'currentColor',
                            marginRight: 6,
                          }}
                        />
                        {t.is_active ? 'Active' : 'Suspended'}
                      </span>
                    </td>
                    <td>
                      <span className="text-sm text-muted">
                        {new Date(t.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => handleViewUsers(t)}
                          style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                          title="View Members"
                        >
                          <Users size={14} /> Members
                        </button>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => handleToggleActive(t)}
                          style={{
                            padding: '0.4rem 0.6rem',
                            fontSize: '0.8rem',
                            color: t.is_active ? 'var(--warning, #F59E0B)' : 'var(--success, #10B981)',
                          }}
                          title={t.is_active ? 'Suspend Enterprise' : 'Reactivate Enterprise'}
                        >
                          {t.is_active ? 'Suspend' : 'Reactivate'}
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

      {/* View Members Modal */}
      {selectedTenantForUsers && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedTenantForUsers(null);
          }}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '560px',
              padding: 0,
              overflow: 'hidden',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div
              style={{
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                  {selectedTenantForUsers.display_name || selectedTenantForUsers.name} Members
                </h3>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Enterprise ID: {selectedTenantForUsers.id}
                </p>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setSelectedTenantForUsers(null)}
                style={{ padding: '0.4rem' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.25rem 1.5rem', maxHeight: '380px', overflowY: 'auto' }}>
              {loadingUsers ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
                  Loading members...
                </div>
              ) : tenantUsers.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No users enrolled in this enterprise yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {tenantUsers.map((u) => (
                    <div
                      key={u.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.65rem 0.75rem',
                        background: 'var(--bg-dark)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-color)',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{u.email}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Joined {new Date(u.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <span className={`badge ${u.role === 'ADMIN' ? 'badge-primary' : 'badge-default'}`}>
                        {u.role}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div
              style={{
                padding: '1rem 1.5rem',
                borderTop: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'flex-end',
              }}
            >
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setSelectedTenantForUsers(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Enterprise Modal */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !submitting) setShowCreateModal(false);
          }}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '500px',
              padding: 0,
              overflow: 'hidden',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div
              style={{
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Building2 size={18} color="var(--primary)" /> Onboard New Enterprise
              </h3>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setShowCreateModal(false)}
                disabled={submitting}
                style={{ padding: '0.4rem' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreate} style={{ padding: '1.25rem 1.5rem' }}>
              <div className="form-group">
                <label>Organization Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (!slug) setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '-'));
                  }}
                  required
                  placeholder="Acme Corporation"
                />
              </div>

              <div className="form-group">
                <label>Slug (Unique identifier)</label>
                <input
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value.toLowerCase())}
                  required
                  placeholder="acme-corp"
                />
              </div>

              <div className="form-group">
                <label>Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Acme Global Industries"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label>Max Users</label>
                  <input
                    type="number"
                    value={maxUsers}
                    onChange={(e) => setMaxUsers(Number(e.target.value))}
                    min={1}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Max Data Sources</label>
                  <input
                    type="number"
                    value={maxSources}
                    onChange={(e) => setMaxSources(Number(e.target.value))}
                    min={1}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={submitting}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                  {submitting && <Loader2 size={16} className="animate-spin" />}
                  <span>{submitting ? 'Creating...' : 'Create Enterprise'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
