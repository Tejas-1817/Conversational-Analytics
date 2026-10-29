import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { X, Search, Users, ShieldCheck, CheckSquare, Square, Loader2, AlertCircle, CheckCircle2, Table } from 'lucide-react';
import { fetchApi } from '../services/api';
import { SourceLogo } from './SourceLogos';
import { ManageTablePermissionsModal } from './ManageTablePermissionsModal';
import type { UserAccessTarget } from './ManageDataSourceAccessModal';

export interface SourceUserItem {
  user_id: string;
  email: string;
  role: string;
  is_granted: boolean;
  granted_tables_count?: number;
  total_tables_count?: number;
}

export interface SourceAccessTarget {
  id: string;
  name: string;
  type: string;
  database_name?: string | null;
}
export const SourceAccessTarget = {};

interface ManageSourceUsersModalProps {
  isOpen: boolean;
  onClose: () => void;
  source: SourceAccessTarget | null;
  onSuccess?: () => void;
}

export const ManageSourceUsersModal: React.FC<ManageSourceUsersModalProps> = ({
  isOpen,
  onClose,
  source,
  onSuccess,
}) => {
  const [users, setUsers] = useState<SourceUserItem[]>([]);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [selectedUserForTables, setSelectedUserForTables] = useState<UserAccessTarget | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    if (!source) return;
    setLoading(true);
    setError(null);
    try {
      const data: SourceUserItem[] = await fetchApi(`/sources/${source.id}/users`);
      setUsers(data);
      const granted = new Set(
        data.filter(u => u.is_granted && u.role !== 'ADMIN').map(u => u.user_id)
      );
      setSelectedUserIds(granted);
    } catch (err: any) {
      setError(err.message || 'Failed to load user access list for this data source');
    } finally {
      setLoading(false);
    }
  }, [source]);

  useEffect(() => {
    if (!isOpen || !source) {
      setUsers([]);
      setSelectedUserIds(new Set());
      setSearch('');
      setError(null);
      setSuccessMsg(null);
      setSelectedUserForTables(null);
      return;
    }

    loadUsers();
  }, [isOpen, source, loadUsers]);

  const filteredUsers = useMemo(() => {
    if (!search.trim()) return users;
    const q = search.toLowerCase();
    return users.filter(
      u => u.email.toLowerCase().includes(q) || u.role.toLowerCase().includes(q)
    );
  }, [users, search]);

  const toggleUser = (userId: string, role: string) => {
    if (role === 'ADMIN') return; // Admins always have access
    setSelectedUserIds(prev => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const selectAll = () => {
    const next = new Set(selectedUserIds);
    filteredUsers.forEach(u => {
      if (u.role !== 'ADMIN') next.add(u.user_id);
    });
    setSelectedUserIds(next);
  };

  const deselectAll = () => {
    const next = new Set(selectedUserIds);
    filteredUsers.forEach(u => {
      if (u.role !== 'ADMIN') next.delete(u.user_id);
    });
    setSelectedUserIds(next);
  };

  const handleSave = async () => {
    if (!source) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await fetchApi(`/sources/${source.id}/users`, {
        method: 'PUT',
        body: JSON.stringify({
          user_ids: Array.from(selectedUserIds),
        }),
      });
      setSuccessMsg('User access updated successfully!');
      if (onSuccess) onSuccess();
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || 'Failed to update user access');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !source) return null;

  const nonAdminCount = users.filter(u => u.role !== 'ADMIN').length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: '620px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ flexShrink: 0 }}>
              <SourceLogo type={source.type} size={32} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
                  Manage User Access
                </h2>
                <span className="badge badge-default" style={{ fontSize: '0.7rem', textTransform: 'capitalize' }}>
                  {source.type}
                </span>
              </div>
              <p className="text-sm text-muted" style={{ margin: '2px 0 0 0' }}>
                {source.name} {source.database_name ? `(${source.database_name})` : ''}
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

        {/* Body */}
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
                placeholder="Search users by email or role..."
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
                disabled={loading || saving || nonAdminCount === 0}
                style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
              >
                Select All
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={deselectAll}
                disabled={loading || saving || nonAdminCount === 0}
                style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
              >
                Clear All
              </button>
            </div>
          </div>

          {/* Selection Summary */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <span>
              <strong>{selectedUserIds.size}</strong> of {nonAdminCount} analysts/viewers granted access
            </span>
            {filteredUsers.length < users.length && (
              <span>Showing {filteredUsers.length} matching users</span>
            )}
          </div>

          {/* Users List */}
          <div
            style={{
              maxHeight: '340px',
              overflowY: 'auto',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
            }}
          >
            {loading ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
                <p style={{ margin: 0, fontSize: '0.875rem' }}>Loading user access...</p>
              </div>
            ) : users.length === 0 ? (
              <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Users size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.9rem' }}>No organization members found</p>
                <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem' }}>
                  Invite team members from Users & Roles.
                </p>
              </div>
            ) : filteredUsers.length === 0 ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Search size={24} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p style={{ margin: 0, fontSize: '0.875rem' }}>No users match &quot;{search}&quot;</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {filteredUsers.map(u => {
                  const isAdmin = u.role === 'ADMIN';
                  const isChecked = isAdmin || selectedUserIds.has(u.user_id);
                  return (
                    <div
                      key={u.user_id}
                      onClick={() => !isAdmin && toggleUser(u.user_id, u.role)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.75rem 1rem',
                        borderBottom: '1px solid var(--border-color)',
                        cursor: isAdmin ? 'default' : 'pointer',
                        background: isChecked ? 'var(--primary-light)' : 'transparent',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={e => {
                        if (!isAdmin && !isChecked) {
                          e.currentTarget.style.background = 'var(--bg-hover)';
                        }
                      }}
                      onMouseLeave={e => {
                        if (!isAdmin && !isChecked) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
                        <div
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            background: isAdmin ? 'var(--primary-subtle, rgba(59, 130, 246, 0.15))' : 'var(--bg-card)',
                            border: '1px solid var(--border-color)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: isAdmin ? 'var(--primary)' : 'var(--text-muted)',
                            fontWeight: 600,
                            fontSize: '0.85rem',
                            flexShrink: 0,
                          }}
                        >
                          {u.email.charAt(0).toUpperCase()}
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
                              {u.email}
                            </span>
                            <span
                              className={`badge ${isAdmin ? 'badge-primary' : 'badge-default'}`}
                              style={{ fontSize: '0.65rem', padding: '1px 6px' }}
                            >
                              {isAdmin && <ShieldCheck size={10} style={{ marginRight: 3 }} />}
                              {u.role}
                            </span>
                          </div>
                          {isAdmin ? (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              Admins automatically have access to all data sources
                            </span>
                          ) : (
                            <span style={{ fontSize: '0.75rem', color: isChecked ? 'var(--primary)' : 'var(--text-muted)' }}>
                              {isChecked ? 'Access granted' : 'No access'}
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
                              setSelectedUserForTables({
                                id: u.user_id,
                                email: u.email,
                                role: u.role,
                              });
                            }}
                            title="Configure granular table permissions for this user"
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
                            <span>
                              {typeof u.granted_tables_count === 'number' && typeof u.total_tables_count === 'number' && u.total_tables_count > 0
                                ? `Tables (${u.granted_tables_count}/${u.total_tables_count})`
                                : 'Tables'}
                            </span>
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

        {/* Footer */}
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
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={loading || saving}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {saving && <Loader2 size={16} className="animate-spin" />}
            <span>{saving ? 'Saving...' : 'Save Permissions'}</span>
          </button>
        </div>
      </div>

      <ManageTablePermissionsModal
        isOpen={!!selectedUserForTables}
        onClose={() => setSelectedUserForTables(null)}
        user={selectedUserForTables}
        source={source ? { id: source.id, name: source.name, type: source.type, database_name: source.database_name } : null}
        onSuccess={() => {
          loadUsers();
          if (onSuccess) onSuccess();
        }}
      />
    </div>
  );
};
