import React, { useState, useEffect } from 'react';
import { X, Building2, AlertTriangle, CheckCircle2, Loader2, ArrowRight } from 'lucide-react';
import { fetchApi } from '../services/api';
import { SourceLogo } from './SourceLogos';

export interface SourceTarget {
  id: string;
  name: string;
  type: string;
  tenant_id?: string;
}

interface ReassignEnterpriseModalProps {
  isOpen: boolean;
  onClose: () => void;
  source: SourceTarget | null;
  tenants: any[];
  onSuccess: () => void;
}

export const ReassignEnterpriseModal: React.FC<ReassignEnterpriseModalProps> = ({
  isOpen,
  onClose,
  source,
  tenants,
  onSuccess,
}) => {
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && source) {
      setError(null);
      setSuccessMsg(null);
      // Pre-select the current tenant or the first available different tenant
      const otherTenant = tenants.find((t) => t.id !== source.tenant_id);
      setSelectedTenantId(otherTenant ? otherTenant.id : source.tenant_id || (tenants[0]?.id ?? ''));
    }
  }, [isOpen, source, tenants]);

  if (!isOpen || !source) return null;

  const currentTenant = tenants.find((t) => t.id === source.tenant_id);
  const currentTenantName = currentTenant ? (currentTenant.display_name || currentTenant.name) : 'Default Enterprise';

  const handleReassign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTenantId) return;

    if (selectedTenantId === source.tenant_id) {
      setError('This data source is already assigned to the selected enterprise.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      await fetchApi(`/sources/${source.id}/enterprise`, {
        method: 'PATCH',
        body: JSON.stringify({ tenant_id: selectedTenantId }),
      });
      setSuccessMsg('Enterprise reassigned successfully!');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || 'Failed to reassign enterprise');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '520px', width: '100%' }}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(59, 130, 246, 0.12)',
                color: 'var(--primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Building2 size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>
                Reassign Enterprise
              </h2>
              <p className="text-sm text-muted" style={{ margin: '2px 0 0 0' }}>
                Transfer ownership to another organization boundary
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-ghost"
            onClick={onClose}
            disabled={saving}
            style={{ padding: '6px', borderRadius: 'var(--radius-sm)' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleReassign}>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
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
                <AlertTriangle size={16} style={{ flexShrink: 0 }} />
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

            {/* Target Source Overview */}
            <div
              style={{
                background: 'var(--bg-dark, #0B0E14)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                padding: '0.85rem 1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(255, 255, 255, 0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <SourceLogo type={source.type} size={20} />
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{source.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Type: <span style={{ textTransform: 'capitalize' }}>{source.type}</span>
                  </div>
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Current Enterprise</div>
                <span className="badge badge-default" style={{ marginTop: '2px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <Building2 size={11} />
                  {currentTenantName}
                </span>
              </div>
            </div>

            {/* Target Enterprise Selection */}
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, fontSize: '0.875rem' }}>
                Destination Enterprise Organization
              </label>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {tenants.map((t) => {
                  const isSelected = selectedTenantId === t.id;
                  const isCurrent = source.tenant_id === t.id;

                  return (
                    <div
                      key={t.id}
                      onClick={() => setSelectedTenantId(t.id)}
                      style={{
                        padding: '0.75rem 1rem',
                        borderRadius: 'var(--radius-md)',
                        border: `1.5px solid ${isSelected ? 'var(--primary)' : 'var(--border-color)'}`,
                        background: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-dark, #0B0E14)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div
                          style={{
                            width: 18,
                            height: 18,
                            borderRadius: '50%',
                            border: `2px solid ${isSelected ? 'var(--primary)' : 'var(--border-color)'}`,
                            background: isSelected ? 'var(--primary)' : 'transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {isSelected && (
                            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff' }} />
                          )}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.875rem', color: isSelected ? 'var(--primary)' : 'inherit' }}>
                            {t.display_name || t.name}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            slug: <code>{t.slug}</code>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {isCurrent && (
                          <span className="badge badge-default" style={{ fontSize: '0.7rem' }}>
                            Current
                          </span>
                        )}
                        <span className="badge badge-default" style={{ fontSize: '0.7rem', textTransform: 'uppercase' }}>
                          {t.plan}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Isolation Guardrail Note */}
            <div
              style={{
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.65rem',
                fontSize: '0.8rem',
                lineHeight: 1.45,
                color: 'var(--text-muted)',
              }}
            >
              <AlertTriangle size={16} color="#F59E0B" style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong style={{ color: '#F59E0B', display: 'block', marginBottom: 2 }}>
                  Security & Multi-Tenancy Boundary
                </strong>
                Reassigning this source will transfer its tenant scope. Any table grants previously assigned to users in <em>{currentTenantName}</em> will be automatically dropped to enforce strict cross-tenant data isolation.
              </div>
            </div>
          </div>

          {/* Footer */}
          <div
            className="modal-footer"
            style={{
              padding: '1rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '0.75rem',
              borderTop: '1px solid var(--border-color)',
            }}
          >
            <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={saving || !selectedTenantId || selectedTenantId === source.tenant_id}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {saving ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Reassigning...
                </>
              ) : (
                <>
                  <Building2 size={16} />
                  Reassign Enterprise
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
