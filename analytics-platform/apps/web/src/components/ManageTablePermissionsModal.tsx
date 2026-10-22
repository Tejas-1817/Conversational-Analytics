import React, { useState, useEffect, useMemo } from 'react';
import { X, Search, Table, ShieldCheck, CheckSquare, Square, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { fetchApi } from '../services/api';
import type { UserAccessTarget } from './ManageDataSourceAccessModal';

export interface UserTableAccessItem {
  table_id: string;
  schema_name: string;
  table_name: string;
  is_granted: boolean;
}

interface ManageTablePermissionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserAccessTarget | null;
  source: { id: string; name: string } | null;
  onSuccess?: () => void;
}

export const ManageTablePermissionsModal: React.FC<ManageTablePermissionsModalProps> = ({
  isOpen,
  onClose,
  user,
  source,
  onSuccess,
}) => {
  const [tables, setTables] = useState<UserTableAccessItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !user || !source) {
      setTables([]);
      setSelectedIds(new Set());
      setSearch('');
      setError(null);
      setSuccessMsg(null);
      return;
    }

    const fetchTables = async () => {
      setLoading(true);
      setError(null);
      try {
        const data: UserTableAccessItem[] = await fetchApi(
          `/users/${user.id}/sources/${source.id}/tables`
        );
        setTables(data);
        const granted = new Set(data.filter((t) => t.is_granted).map((t) => t.table_id));
        setSelectedIds(granted);
      } catch (err: any) {
        setError(err.message || 'Failed to load user table permissions');
      } finally {
        setLoading(false);
      }
    };

    fetchTables();
  }, [isOpen, user, source]);

  const filteredTables = useMemo(() => {
    if (!search.trim()) return tables;
    const q = search.toLowerCase();
    return tables.filter(
      (t) =>
        t.table_name.toLowerCase().includes(q) ||
        t.schema_name.toLowerCase().includes(q) ||
        `${t.schema_name}.${t.table_name}`.toLowerCase().includes(q)
    );
  }, [tables, search]);

  const toggleTable = (tableId: string) => {
    if (user?.role === 'ADMIN') return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(tableId)) {
        next.delete(tableId);
      } else {
        next.add(tableId);
      }
      return next;
    });
  };

  const selectAll = () => {
    if (user?.role === 'ADMIN') return;
    const allFiltered = new Set(selectedIds);
    filteredTables.forEach((t) => allFiltered.add(t.table_id));
    setSelectedIds(allFiltered);
  };

  const deselectAll = () => {
    if (user?.role === 'ADMIN') return;
    const allFiltered = new Set(selectedIds);
    filteredTables.forEach((t) => allFiltered.delete(t.table_id));
    setSelectedIds(allFiltered);
  };

  const handleSave = async () => {
    if (!user || !source || user.role === 'ADMIN') return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await fetchApi(`/users/${user.id}/sources/${source.id}/tables`, {
        method: 'PUT',
        body: JSON.stringify({ table_ids: Array.from(selectedIds) }),
      });
      setSuccessMsg(`Permissions updated: ${selectedIds.size} table(s) granted.`);
      if (onSuccess) onSuccess();
      setTimeout(() => {
        onClose();
      }, 900);
    } catch (err: any) {
      setError(err.message || 'Failed to update table permissions');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !user || !source) return null;

  const isAdmin = user.role === 'ADMIN';

  return (
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
      onClick={e => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '560px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
          overflow: 'hidden',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-surface, #11141D)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(59, 130, 246, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--primary)',
              }}
            >
              <Table size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                Table Permissions
              </h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {user.email} &bull; <strong>{source.name}</strong>
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-ghost"
            onClick={onClose}
            disabled={saving}
            style={{ padding: '0.4rem' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#EF4444',
                fontSize: '0.85rem',
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#10B981',
                fontSize: '0.85rem',
              }}
            >
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>{successMsg}</span>
            </div>
          )}

          {isAdmin ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(59, 130, 246, 0.08)',
                border: '1px solid rgba(59, 130, 246, 0.25)',
              }}
            >
              <ShieldCheck size={24} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              <div style={{ fontSize: '0.875rem' }}>
                Users with the <strong>ADMIN</strong> role have full unrestricted access to all tables in this data source.
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
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search tables by schema or table name..."
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
                    disabled={loading || saving || tables.length === 0}
                    style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={deselectAll}
                    disabled={loading || saving || tables.length === 0}
                    style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
                  >
                    Clear All
                  </button>
                </div>
              </div>

              {/* Selection Summary */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <span>
                  Permitted access to <strong>{selectedIds.size}</strong> of {tables.length} tables
                </span>
                {filteredTables.length < tables.length && (
                  <span>Showing {filteredTables.length} matching tables</span>
                )}
              </div>
            </>
          )}

          {/* Tables List */}
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
                <p style={{ margin: 0, fontSize: '0.875rem' }}>Loading tables...</p>
              </div>
            ) : tables.length === 0 ? (
              <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Table size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.9rem' }}>No tables discovered</p>
                <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem' }}>
                  Run schema ingestion on this data source to discover its tables.
                </p>
              </div>
            ) : filteredTables.length === 0 ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Search size={24} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p style={{ margin: 0, fontSize: '0.875rem' }}>No tables match &quot;{search}&quot;</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {filteredTables.map((t) => {
                  const isChecked = isAdmin || selectedIds.has(t.table_id);
                  return (
                    <div
                      key={t.table_id}
                      onClick={() => !isAdmin && toggleTable(t.table_id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.65rem 1rem',
                        borderBottom: '1px solid var(--border-color)',
                        cursor: isAdmin ? 'default' : 'pointer',
                        background: isChecked ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!isAdmin && !isChecked) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isAdmin && !isChecked) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
                        <div style={{ color: 'var(--text-muted)' }}>
                          <Table size={16} />
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            {t.schema_name && (
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {t.schema_name}.
                              </span>
                            )}
                            <span
                              style={{
                                fontWeight: 600,
                                fontSize: '0.875rem',
                                color: 'var(--text-main)',
                              }}
                            >
                              {t.table_name}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                        {isAdmin ? (
                          <span className="badge badge-primary" style={{ fontSize: '0.7rem' }}>
                            Admin Access
                          </span>
                        ) : (
                          <div
                            style={{
                              color: isChecked ? 'var(--primary)' : 'var(--text-muted)',
                              display: 'flex',
                              alignItems: 'center',
                            }}
                          >
                            {isChecked ? <CheckSquare size={18} /> : <Square size={18} />}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-surface, #11141D)',
          }}
        >
          <button
            type="button"
            className="btn-ghost"
            onClick={onClose}
            disabled={saving}
          >
            {isAdmin ? 'Close' : 'Cancel'}
          </button>
          {!isAdmin && (
            <button
              type="button"
              className="btn-primary"
              onClick={handleSave}
              disabled={loading || saving}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {saving ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Table Permissions'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
