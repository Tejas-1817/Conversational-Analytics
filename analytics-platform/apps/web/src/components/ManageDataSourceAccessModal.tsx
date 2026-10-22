import React, { useState, useEffect, useMemo } from 'react';
import { X, Search, Database, ShieldCheck, CheckSquare, Square, Loader2, AlertCircle, CheckCircle2, Table, Building2 } from 'lucide-react';
import { fetchApi } from '../services/api';
import { SourceLogo } from './SourceLogos';
import { ManageTablePermissionsModal } from './ManageTablePermissionsModal';

export interface UserDataSourceItem {
  source_id: string;
  name: string;
  type: string;
  database_name?: string | null;
  is_granted: boolean;
}
export const UserDataSourceItem = {};

export interface UserAccessTarget {
  id: string;
  email: string;
  role: string;
  tenant_id?: string;
  granted_sources_count?: number;
}
export const UserAccessTarget = {};

interface ManageDataSourceAccessModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserAccessTarget | null;
  onSuccess?: () => void;
}

export const ManageDataSourceAccessModal: React.FC<ManageDataSourceAccessModalProps> = ({
  isOpen,
  onClose,
  user,
  onSuccess,
}) => {
  const [sources, setSources] = useState<UserDataSourceItem[]>([]);
  const [tenants, setTenants] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedSourceForTables, setSelectedSourceForTables] = useState<{ id: string; name: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !user) {
      setSources([]);
      setSelectedIds(new Set());
      setSearch('');
      setError(null);
      setSuccessMsg(null);
      return;
    }

    const fetchSources = async () => {
      setLoading(true);
      setError(null);
      try {
        const [sourcesData, tenantsData] = await Promise.all([
          fetchApi(`/users/${user.id}/sources`),
          fetchApi('/tenants').catch(() => []),
        ]);
        if (Array.isArray(tenantsData)) {
          setTenants(tenantsData);
        }

        const items: UserDataSourceItem[] = Array.isArray(sourcesData) ? sourcesData : [];
        setSources(items);
        const granted = new Set<string>(items.filter((s) => s.is_granted).map((s) => s.source_id));
        setSelectedIds(granted);
      } catch (err: any) {

        setError(err.message || 'Failed to load user data source permissions');
      } finally {
        setLoading(false);
      }
    };

    fetchSources();
  }, [isOpen, user]);

  const enterpriseName = useMemo(() => {
    if (!user?.tenant_id) return 'Default Enterprise';
    const t = tenants.find(x => x.id === user.tenant_id);
    return t ? (t.display_name || t.name) : 'Default Enterprise';
  }, [tenants, user]);

  const filteredSources = useMemo(() => {
    if (!search.trim()) return sources;
    const q = search.toLowerCase();
    return sources.filter(
      s =>
        s.name.toLowerCase().includes(q) ||
        s.type.toLowerCase().includes(q) ||
        (s.database_name && s.database_name.toLowerCase().includes(q))
    );
  }, [sources, search]);

  const toggleSource = (sourceId: string) => {
    if (user?.role === 'ADMIN') return; // Admins always have access to all sources
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(sourceId)) {
        next.delete(sourceId);
      } else {
        next.add(sourceId);
      }
      return next;
    });
  };

  const selectAll = () => {
    if (user?.role === 'ADMIN') return;
    const allFiltered = new Set(selectedIds);
    filteredSources.forEach(s => allFiltered.add(s.source_id));
    setSelectedIds(allFiltered);
  };

  const deselectAll = () => {
    if (user?.role === 'ADMIN') return;
    const next = new Set(selectedIds);
    filteredSources.forEach(s => next.delete(s.source_id));
    setSelectedIds(next);
  };

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await fetchApi(`/users/${user.id}/sources`, {
        method: 'PUT',
        body: JSON.stringify({
          source_ids: Array.from(selectedIds),
        }),
      });
      setSuccessMsg('Permissions updated successfully!');
      if (onSuccess) onSuccess();
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || 'Failed to update user permissions');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !user) return null;

  const isAdmin = user.role === 'ADMIN';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: '620px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
      >
        {/* Modal Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: 'var(--primary-subtle, rgba(59, 130, 246, 0.15))',
                color: 'var(--primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '1rem',
              }}
            >
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
                  Manage Data Source Access
                </h2>
                <span className={`badge ${isAdmin ? 'badge-primary' : 'badge-default'}`} style={{ fontSize: '0.7rem' }}>
                  {isAdmin && <ShieldCheck size={11} style={{ marginRight: 3 }} />}
                  {user.role}
                </span>
              </div>
              <p className="text-sm text-muted" style={{ margin: '2px 0 0 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>{user.email}</span>
                <span>&bull;</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', color: 'var(--primary)' }}>
                  <Building2 size={12} />
                  {enterpriseName}
                </span>
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-ghost"
            onClick={onClose}
            disabled={saving}
            style={{ padding: '6px', borderRadius: 'var(--radius-sm)' }}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {error && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid var(--danger, #EF4444)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem',
                color: 'var(--danger, #EF4444)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.875rem',
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div
              style={{
                background: 'rgba(34, 197, 94, 0.12)',
                border: '1px solid var(--success, #22C55E)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem',
                color: 'var(--success, #22C55E)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.875rem',
              }}
            >
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>{successMsg}</span>
            </div>
          )}

          {isAdmin ? (
            <div
              style={{
                background: 'rgba(59, 130, 246, 0.08)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
              }}
            >
              <ShieldCheck size={20} color="var(--primary)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.875rem', lineHeight: 1.5 }}>
                <strong style={{ display: 'block', color: 'var(--text-main)', marginBottom: 2 }}>
                  Organization Administrator
                </strong>
                Users with the <strong>ADMIN</strong> role have full unrestricted access to all data sources and tables and cannot be restricted. To limit data access, change their role to <em>USER</em>.
              </div>
            </div>
          ) : (
            <>
              {/* Search & Actions Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <Search
                    size={15}
                    style={{
                      position: 'absolute',
                      left: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)',
                    }}
                  />
                  <input
                    type="text"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search data sources..."
                    style={{
                      paddingLeft: '2.25rem',
                      paddingRight: '0.75rem',
                      paddingTop: '0.5rem',
                      paddingBottom: '0.5rem',
                      fontSize: '0.875rem',
                      width: '100%',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={selectAll}
                    disabled={loading || saving || sources.length === 0}
                    style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={deselectAll}
                    disabled={loading || saving || sources.length === 0}
                    style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
                  >
                    Clear All
                  </button>
                </div>
              </div>

              {/* Selection Summary */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <span>
                  Granted access to <strong>{selectedIds.size}</strong> of {sources.length} sources
                </span>
                {filteredSources.length < sources.length && (
                  <span>Showing {filteredSources.length} matching sources</span>
                )}
              </div>
            </>
          )}

          {/* Sources List */}
          <div
            style={{
              maxHeight: '340px',
              overflowY: 'auto',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-dark, #0B0E14)',
            }}
          >
            {loading ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
                <p style={{ margin: 0, fontSize: '0.875rem' }}>Loading data sources...</p>
              </div>
            ) : sources.length === 0 ? (
              <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Database size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                  No data sources found for {enterpriseName}
                </p>
                <p style={{ margin: '0.5rem auto 0', fontSize: '0.82rem', maxWidth: '380px', lineHeight: 1.5 }}>
                  This user belongs to <strong>{enterpriseName}</strong>. Under tenant isolation, only data sources associated with this enterprise can be granted.
                </p>
                <p style={{ margin: '0.5rem auto 0', fontSize: '0.8rem', color: 'var(--primary)' }}>
                  Go to <strong>Data Sources</strong> to connect a new source to {enterpriseName} or reassign an existing source.
                </p>
              </div>
            ) : filteredSources.length === 0 ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Search size={24} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p style={{ margin: 0, fontSize: '0.875rem' }}>No data sources match &quot;{search}&quot;</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {filteredSources.map(source => {
                  const isChecked = isAdmin || selectedIds.has(source.source_id);
                  return (
                    <div
                      key={source.source_id}
                      onClick={() => !isAdmin && toggleSource(source.source_id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.75rem 1rem',
                        borderBottom: '1px solid var(--border-color)',
                        cursor: isAdmin ? 'default' : 'pointer',
                        background: isChecked ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={e => {
                        if (!isAdmin && !isChecked) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                        }
                      }}
                      onMouseLeave={e => {
                        if (!isAdmin && !isChecked) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
                        <div style={{ flexShrink: 0 }}>
                          <SourceLogo type={source.type} size={28} />
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span
                              style={{
                                fontWeight: 600,
                                fontSize: '0.9rem',
                                color: 'var(--text-main)',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {source.name}
                            </span>
                            <span
                              className="badge badge-default"
                              style={{ fontSize: '0.65rem', textTransform: 'capitalize', padding: '1px 6px' }}
                            >
                              {source.type}
                            </span>
                          </div>
                          {source.database_name && (
                            <span
                              style={{
                                fontFamily: 'var(--font-mono, monospace)',
                                fontSize: '0.75rem',
                                color: 'var(--text-muted)',
                                display: 'block',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                marginTop: '1px',
                              }}
                            >
                              {source.database_name}
                            </span>
                          )}
                        </div>
                      </div>

                      <div style={{ flexShrink: 0, marginLeft: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        {isChecked && !isAdmin && (
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedSourceForTables({ id: source.source_id, name: source.name });
                            }}
                            title="Configure granular table permissions for this data source"
                            style={{
                              padding: '0.25rem 0.5rem',
                              fontSize: '0.75rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              color: 'var(--primary)',
                              border: '1px solid rgba(59, 130, 246, 0.3)',
                              borderRadius: 'var(--radius-sm)',
                              background: 'rgba(59, 130, 246, 0.08)',
                            }}
                          >
                            <Table size={13} />
                            <span>Tables</span>
                          </button>
                        )}
                        {isChecked ? (
                          <CheckSquare size={20} color={isAdmin ? 'var(--text-muted)' : 'var(--primary)'} />
                        ) : (
                          <Square size={20} color="var(--text-muted)" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div
          className="modal-footer"
          style={{
            padding: '1rem var(--space-3)',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '0.75rem',
          }}
        >
          <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>
            {isAdmin ? 'Close' : 'Cancel'}
          </button>
          {!isAdmin && (
            <button
              type="button"
              onClick={handleSave}
              disabled={loading || saving}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {saving && <Loader2 size={16} className="animate-spin" />}
              <span>{saving ? 'Saving...' : 'Save Permissions'}</span>
            </button>
          )}
        </div>
      </div>

      <ManageTablePermissionsModal
        isOpen={!!selectedSourceForTables}
        onClose={() => setSelectedSourceForTables(null)}
        user={user}
        source={selectedSourceForTables}
        onSuccess={onSuccess}
      />
    </div>
  );
};
