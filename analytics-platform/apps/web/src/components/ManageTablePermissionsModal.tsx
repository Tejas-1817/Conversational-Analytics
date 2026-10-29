import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  Search,
  Table,
  ShieldCheck,
  CheckSquare,
  Square,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Layers,
  Lock,
  Building2,
  Check,
} from 'lucide-react';
import { fetchApi } from '../services/api';
import type { UserAccessTarget, TablePermissionsSourceTarget } from './ManageDataSourceAccessModal';
import { SourceLogo } from './SourceLogos';

export interface UserTableAccessItem {
  table_id: string;
  schema_name: string;
  table_name: string;
  business_name?: string | null;
  description?: string | null;
  row_count?: number | null;
  is_granted: boolean;
}
export const UserTableAccessItem = {};

interface ManageTablePermissionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserAccessTarget | null;
  source: TablePermissionsSourceTarget | null;
  enterpriseName?: string;
  onSuccess?: () => void;
}

export const ManageTablePermissionsModal: React.FC<ManageTablePermissionsModalProps> = ({
  isOpen,
  onClose,
  user,
  source,
  enterpriseName,
  onSuccess,
}) => {
  const [tables, setTables] = useState<UserTableAccessItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [collapsedSchemas, setCollapsedSchemas] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!isOpen || !user || !source) {
      setTables([]);
      setSelectedIds(new Set());
      setSearch('');
      setError(null);
      setSuccessMsg(null);
      setCollapsedSchemas(new Set());
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

  // Filter tables by search query
  const filteredTables = useMemo(() => {
    if (!search.trim()) return tables;
    const q = search.toLowerCase().trim();
    return tables.filter(
      (t) =>
        t.table_name.toLowerCase().includes(q) ||
        (t.schema_name && t.schema_name.toLowerCase().includes(q)) ||
        (t.business_name && t.business_name.toLowerCase().includes(q)) ||
        (t.description && t.description.toLowerCase().includes(q)) ||
        `${t.schema_name}.${t.table_name}`.toLowerCase().includes(q)
    );
  }, [tables, search]);

  // Group tables by schema_name
  const tablesBySchema = useMemo(() => {
    const groups: Record<string, UserTableAccessItem[]> = {};
    for (const table of filteredTables) {
      const s = table.schema_name || 'public';
      if (!groups[s]) {
        groups[s] = [];
      }
      groups[s].push(table);
    }
    return groups;
  }, [filteredTables]);

  const schemaNames = useMemo(() => Object.keys(tablesBySchema).sort(), [tablesBySchema]);

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

  const toggleSchemaCollapse = (schemaName: string) => {
    setCollapsedSchemas((prev) => {
      const next = new Set(prev);
      if (next.has(schemaName)) {
        next.delete(schemaName);
      } else {
        next.add(schemaName);
      }
      return next;
    });
  };

  const expandAllSchemas = () => setCollapsedSchemas(new Set());
  const collapseAllSchemas = () => setCollapsedSchemas(new Set(schemaNames));

  const selectAllFiltered = () => {
    if (user?.role === 'ADMIN') return;
    const next = new Set(selectedIds);
    filteredTables.forEach((t) => next.add(t.table_id));
    setSelectedIds(next);
  };

  const deselectAllFiltered = () => {
    if (user?.role === 'ADMIN') return;
    const next = new Set(selectedIds);
    filteredTables.forEach((t) => next.delete(t.table_id));
    setSelectedIds(next);
  };

  const selectSchemaTables = (schemaName: string) => {
    if (user?.role === 'ADMIN') return;
    const schemaTables = tablesBySchema[schemaName] || [];
    const next = new Set(selectedIds);
    schemaTables.forEach((t) => next.add(t.table_id));
    setSelectedIds(next);
  };

  const clearSchemaTables = (schemaName: string) => {
    if (user?.role === 'ADMIN') return;
    const schemaTables = tablesBySchema[schemaName] || [];
    const next = new Set(selectedIds);
    schemaTables.forEach((t) => next.delete(t.table_id));
    setSelectedIds(next);
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
      setSuccessMsg(`Permissions saved! ${selectedIds.size} table(s) granted.`);
      if (onSuccess) onSuccess();
      setTimeout(() => {
        onClose();
      }, 750);
    } catch (err: any) {
      setError(err.message || 'Failed to update table permissions');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !user || !source) return null;

  const isAdmin = user.role === 'ADMIN';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '680px',
          width: '100%',
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 'var(--radius-md)',
                background: 'var(--primary-light)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--primary)',
                flexShrink: 0,
              }}
            >
              {source.type ? <SourceLogo type={source.type} size={22} /> : <Table size={18} />}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
                  Table Permissions
                </h2>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-dark)',
                    color: 'var(--text-muted)',
                    border: '1px solid var(--border-color)',
                    fontWeight: 500,
                  }}
                >
                  {source.name}
                </span>
                {enterpriseName && (
                  <span
                    style={{
                      fontSize: '0.7rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--primary-light)',
                      color: 'var(--primary)',
                      fontWeight: 600,
                      border: '1px solid rgba(59, 130, 246, 0.25)',
                    }}
                  >
                    <Building2 size={11} />
                    {enterpriseName}
                  </span>
                )}
              </div>
              <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Configuring table-level access for <strong>{user.email}</strong>
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
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--danger-light)',
                border: '1px solid rgba(220, 38, 38, 0.25)',
                color: 'var(--danger)',
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
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--success-light)',
                border: '1px solid rgba(22, 163, 74, 0.25)',
                color: 'var(--success)',
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
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--primary-light)',
                border: '1px solid rgba(59, 130, 246, 0.25)',
              }}
            >
              <ShieldCheck size={20} style={{ color: 'var(--primary)', flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.875rem', lineHeight: 1.5, color: 'var(--text-main)' }}>
                <strong style={{ display: 'block', marginBottom: 2 }}>
                  Full Administrator Access
                </strong>
                Users with the <strong>ADMIN</strong> role have unrestricted, automatic access to all tables in this data source. Table-level restrictions do not apply to administrators.
              </div>
            </div>
          ) : (
            <>
              {/* Search & Bulk Action Bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
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
                    placeholder="Search tables or schemas..."
                    style={{
                      paddingLeft: '2.25rem',
                      paddingRight: '2rem',
                      paddingTop: '0.5rem',
                      paddingBottom: '0.5rem',
                      fontSize: '0.875rem',
                      width: '100%',
                    }}
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => setSearch('')}
                      style={{
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '2px',
                      }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={selectAllFiltered}
                    disabled={loading || saving || tables.length === 0}
                    style={{ fontSize: '0.78rem', padding: '0.4rem 0.65rem' }}
                    title="Select all currently visible tables"
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={deselectAllFiltered}
                    disabled={loading || saving || tables.length === 0}
                    style={{ fontSize: '0.78rem', padding: '0.4rem 0.65rem' }}
                    title="Clear selection for currently visible tables"
                  >
                    Clear All
                  </button>
                  {schemaNames.length > 1 && (
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => {
                        if (collapsedSchemas.size > 0) {
                          expandAllSchemas();
                        } else {
                          collapseAllSchemas();
                        }
                      }}
                      style={{ fontSize: '0.78rem', padding: '0.4rem 0.65rem' }}
                    >
                      {collapsedSchemas.size > 0 ? 'Expand All' : 'Collapse All'}
                    </button>
                  )}
                </div>
              </div>

              {/* Status and Statistics Ribbon */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  borderRadius: 'var(--radius-sm)',
                  background: selectedIds.size === 0 ? 'var(--danger-light)' : 'var(--primary-light)',
                  border: `1px solid ${selectedIds.size === 0 ? 'rgba(220, 38, 38, 0.25)' : 'rgba(59, 130, 246, 0.25)'}`,
                  fontSize: '0.82rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: selectedIds.size === 0 ? 'var(--danger)' : 'var(--primary)' }}>
                  {selectedIds.size === 0 ? (
                    <Lock size={15} />
                  ) : (
                    <CheckSquare size={15} />
                  )}
                  <span style={{ fontWeight: 600 }}>
                    {selectedIds.size} of {tables.length} tables granted
                  </span>
                </div>
                {selectedIds.size === 0 ? (
                  <span style={{ color: 'var(--danger)', fontSize: '0.75rem', fontWeight: 600 }}>
                    Deny-by-default (No tables accessible)
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    {tables.length - selectedIds.size} tables restricted
                  </span>
                )}
              </div>
            </>
          )}

          {/* Tables Grouped by Schema */}
          <div
            style={{
              maxHeight: '380px',
              overflowY: 'auto',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
            }}
          >
            {loading ? (
              <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
                <p style={{ margin: 0, fontSize: '0.875rem' }}>Loading schema tables...</p>
              </div>
            ) : tables.length === 0 ? (
              <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Table size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.35 }} />
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                  No tables discovered yet
                </p>
                <p style={{ margin: '0.35rem auto 0', fontSize: '0.82rem', maxWidth: '380px', lineHeight: 1.5 }}>
                  This data source does not have any discovered tables. Trigger schema ingestion from the Data Sources page to inspect and discover its catalog.
                </p>
              </div>
            ) : filteredTables.length === 0 ? (
              <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Search size={28} style={{ margin: '0 auto 0.5rem', opacity: 0.35 }} />
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-main)' }}>No matching tables found</p>
                <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem' }}>
                  No tables or schemas match &quot;{search}&quot;.
                </p>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setSearch('')}
                  style={{ marginTop: '0.75rem', fontSize: '0.8rem' }}
                >
                  Clear Search
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {schemaNames.map((schemaName) => {
                  const schemaTables = tablesBySchema[schemaName];
                  const isCollapsed = collapsedSchemas.has(schemaName);
                  const schemaGrantedCount = schemaTables.filter((t) =>
                    isAdmin ? true : selectedIds.has(t.table_id)
                  ).length;
                  const allSchemaGranted = schemaGrantedCount === schemaTables.length;

                  return (
                    <div
                      key={schemaName}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                      }}
                    >
                      {/* Schema Accordion Header */}
                      <div
                        onClick={() => toggleSchemaCollapse(schemaName)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.65rem 1rem',
                          background: 'var(--bg-dark)',
                          cursor: 'pointer',
                          userSelect: 'none',
                          borderLeft: allSchemaGranted
                            ? '3px solid var(--primary)'
                            : schemaGrantedCount > 0
                            ? '3px solid var(--secondary)'
                            : '3px solid transparent',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>
                            {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                          </span>
                          <Layers size={15} style={{ color: 'var(--text-muted)' }} />
                          <span
                            style={{
                              fontFamily: 'var(--font-mono, monospace)',
                              fontSize: '0.85rem',
                              fontWeight: 700,
                              color: 'var(--text-main)',
                            }}
                          >
                            {schemaName}
                          </span>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              padding: '1px 6px',
                              borderRadius: 'var(--radius-sm)',
                              background:
                                schemaGrantedCount > 0
                                  ? 'var(--primary-light)'
                                  : 'var(--bg-card)',
                              color: schemaGrantedCount > 0 ? 'var(--primary)' : 'var(--text-muted)',
                              border: '1px solid var(--border-color)',
                              fontWeight: 600,
                            }}
                          >
                            {schemaGrantedCount} / {schemaTables.length} granted
                          </span>
                        </div>

                        {!isAdmin && (
                          <div
                            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              className="btn-ghost"
                              onClick={() => selectSchemaTables(schemaName)}
                              style={{
                                fontSize: '0.72rem',
                                padding: '2px 6px',
                                height: 'auto',
                                color: 'var(--primary)',
                              }}
                              title={`Grant all tables in ${schemaName}`}
                            >
                              Select All
                            </button>
                            <span style={{ color: 'var(--text-faint)', fontSize: '0.7rem' }}>|</span>
                            <button
                              type="button"
                              className="btn-ghost"
                              onClick={() => clearSchemaTables(schemaName)}
                              style={{
                                fontSize: '0.72rem',
                                padding: '2px 6px',
                                height: 'auto',
                                color: 'var(--text-muted)',
                              }}
                              title={`Clear all tables in ${schemaName}`}
                            >
                              Clear
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Tables under this schema */}
                      {!isCollapsed && (
                        <div style={{ background: 'var(--bg-card)' }}>
                          {schemaTables.map((t) => {
                            const isChecked = isAdmin || selectedIds.has(t.table_id);
                            return (
                              <div
                                key={t.table_id}
                                onClick={() => !isAdmin && toggleTable(t.table_id)}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  padding: '0.65rem 1rem 0.65rem 2rem',
                                  borderTop: '1px solid var(--border-color)',
                                  cursor: isAdmin ? 'default' : 'pointer',
                                  background: isChecked ? 'var(--primary-light)' : 'var(--bg-card)',
                                  transition: 'background 0.15s ease',
                                }}
                                onMouseEnter={(e) => {
                                  if (!isAdmin && !isChecked) {
                                    e.currentTarget.style.background = 'var(--bg-hover)';
                                  }
                                }}
                                onMouseLeave={(e) => {
                                  if (!isAdmin && !isChecked) {
                                    e.currentTarget.style.background = 'var(--bg-card)';
                                  }
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0 }}>
                                  <Table size={15} style={{ color: isChecked ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }} />
                                  <div style={{ minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                                      <span
                                        style={{
                                          fontFamily: 'var(--font-mono, monospace)',
                                          fontWeight: 600,
                                          fontSize: '0.85rem',
                                          color: 'var(--text-main)',
                                        }}
                                      >
                                        {t.table_name}
                                      </span>
                                      {t.business_name && (
                                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                          ({t.business_name})
                                        </span>
                                      )}
                                      {typeof t.row_count === 'number' && t.row_count > 0 && (
                                        <span
                                          style={{
                                            fontSize: '0.7rem',
                                            color: 'var(--text-muted)',
                                            background: 'var(--bg-dark)',
                                            border: '1px solid var(--border-color)',
                                            padding: '1px 6px',
                                            borderRadius: 'var(--radius-sm)',
                                          }}
                                        >
                                          {t.row_count.toLocaleString()} rows
                                        </span>
                                      )}
                                    </div>
                                    {t.description && (
                                      <p
                                        style={{
                                          margin: '2px 0 0',
                                          fontSize: '0.75rem',
                                          color: 'var(--text-muted)',
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          whiteSpace: 'nowrap',
                                          maxWidth: '380px',
                                        }}
                                      >
                                        {t.description}
                                      </p>
                                    )}
                                  </div>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                                  {isAdmin ? (
                                    <span
                                      style={{
                                        fontSize: '0.7rem',
                                        padding: '2px 6px',
                                        borderRadius: 'var(--radius-sm)',
                                        background: 'var(--primary-light)',
                                        color: 'var(--primary)',
                                        fontWeight: 600,
                                      }}
                                    >
                                      Admin
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
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={saving}
          >
            {isAdmin ? 'Close' : 'Cancel'}
          </button>
          {!isAdmin && (
            <button
              type="button"
              onClick={handleSave}
              disabled={loading || saving}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {saving ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Saving Changes...</span>
                </>
              ) : (
                <>
                  <Check size={16} />
                  <span>Save Permissions ({selectedIds.size})</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
