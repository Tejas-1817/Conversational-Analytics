import React, { useState, useEffect, useRef } from 'react';
import { fetchApi } from '../../services/api';
import {
  Bookmark,
  Plus,
  Search,
  LayoutDashboard,
  Check,
  AlertCircle,
  X,
  Lock,
  Globe,
  Loader2,
} from 'lucide-react';

export interface SaveInsightModalProps {
  isOpen: boolean;
  onClose: () => void;
  message?: any;
  messages?: any[];
  sourceId?: string;
  domainId?: string;
  conversationId?: string;
  onSaved: (insightOrResult: any, targetDashboardId: string, dashboardName: string) => void;
}

export const SaveInsightModal: React.FC<SaveInsightModalProps> = ({
  isOpen,
  onClose,
  message,
  messages,
  sourceId,
  domainId,
  conversationId,
  onSaved,
}) => {
  const isBulk = Array.isArray(messages) && messages.length > 0;
  const [insightName, setInsightName] = useState('');
  const [insightDesc, setInsightDesc] = useState('');
  const [dashboards, setDashboards] = useState<any[]>([]);
  const [loadingDashboards, setLoadingDashboards] = useState(false);
  const [dashboardSearch, setDashboardSearch] = useState('');
  const [selectedDashboardId, setSelectedDashboardId] = useState<string | null>(null);

  // Inline "Create new dashboard" mode
  const [isCreatingNewDash, setIsCreatingNewDash] = useState(false);
  const [newDashName, setNewDashName] = useState('');
  const [newDashDesc, setNewDashDesc] = useState('');

  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const initialFocusRef = useRef<HTMLInputElement | null>(null);
  const triggerElementRef = useRef<Element | null>(null);

  // Capture trigger element for focus restoration & prefill fields when modal opens
  useEffect(() => {
    if (isOpen) {
      triggerElementRef.current = document.activeElement;
      if (isBulk && messages) {
        setInsightName(`${messages.length} Insights`);
        setInsightDesc('');
      } else {
        const initialName =
          message?.title ||
          (message?.recommended_visualization && typeof message.recommended_visualization === 'object'
            ? message.recommended_visualization.title
            : null) ||
          message?.question ||
          'New Insight';
        setInsightName(initialName);
        setInsightDesc(message?.question || '');
      }
      setErrorMessage(null);
      setIsCreatingNewDash(false);
      setNewDashName('');
      setNewDashDesc('');

      // Fetch user's dashboards
      setLoadingDashboards(true);
      fetchApi('/dashboards')
        .then((data: any) => {
          const list = Array.isArray(data) ? data : [];
          setDashboards(list);
          if (list.length > 0) {
            setSelectedDashboardId(list[0].id);
          } else {
            setIsCreatingNewDash(true);
          }
        })
        .catch((err) => {
          console.error('Failed to load dashboards', err);
        })
        .finally(() => {
          setLoadingDashboards(false);
        });

      // Focus first input after render
      setTimeout(() => {
        initialFocusRef.current?.focus();
      }, 50);
    } else {
      if (triggerElementRef.current && (triggerElementRef.current as HTMLElement).focus) {
        (triggerElementRef.current as HTMLElement).focus();
      }
    }
  }, [isOpen, message, messages, isBulk]);

  // Handle ESC key to dismiss modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filteredDashboards = dashboards.filter((d) =>
    (d.name || '').toLowerCase().includes(dashboardSearch.toLowerCase().trim())
  );

  const isSaveDisabled =
    saving ||
    (!isBulk && !insightName.trim()) ||
    (isCreatingNewDash ? !newDashName.trim() : !selectedDashboardId);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaveDisabled) return;

    setSaving(true);
    setErrorMessage(null);

    try {
      if (isBulk && messages) {
        const items = messages.map((m: any, idx: number) => {
          let resolvedChartType =
            m.visualization ||
            m.chart_recommendation ||
            (m.recommended_visualization && typeof m.recommended_visualization === 'object'
              ? m.recommended_visualization.chart_type
              : m.recommended_visualization) ||
            'table';

          const columns =
            m.columns ||
            (Array.isArray(m.result_data) && m.result_data.length > 0 && typeof m.result_data[0] === 'object'
              ? Object.keys(m.result_data[0])
              : []);

          const name =
            m.title ||
            (m.recommended_visualization && typeof m.recommended_visualization === 'object'
              ? m.recommended_visualization.title
              : null) ||
            m.question ||
            `Insight ${idx + 1}`;

          return {
            name: name.slice(0, 100),
            description: m.question ? m.question.slice(0, 200) : undefined,
            query: m.sql || m.generated_sql || '',
            chart_type: resolvedChartType,
            chart_config: {
              chartType: resolvedChartType,
              columns,
              columnTypes: m.column_types || {},
            },
            source_id: sourceId || m.source_id || undefined,
            domain_id: domainId || m.domain_id || undefined,
            conversation_id: conversationId || m.conversation_id || undefined,
            message_id: m.id || undefined,
          };
        });

        const bulkPayload: any = {
          items,
        };
        if (isCreatingNewDash) {
          bulkPayload.new_dashboard_name = newDashName.trim();
          bulkPayload.new_dashboard_description = newDashDesc.trim() || undefined;
        } else {
          bulkPayload.dashboard_id = selectedDashboardId;
        }

        const bulkResult = await fetchApi('/dashboards/bulk-save', {
          method: 'POST',
          body: JSON.stringify(bulkPayload),
        });

        onSaved(bulkResult, bulkResult.dashboard_id, bulkResult.dashboard_name);
        onClose();
        return;
      }

      // 1. Determine resolved chart type
      let resolvedChartType =
        message?.visualization ||
        message?.chart_recommendation ||
        (message?.recommended_visualization && typeof message.recommended_visualization === 'object'
          ? message.recommended_visualization.chart_type
          : message.recommended_visualization) ||
        'table';

      const columns =
        message?.columns ||
        (Array.isArray(message?.result_data) && message.result_data.length > 0 && typeof message.result_data[0] === 'object'
          ? Object.keys(message.result_data[0])
          : []);

      // 2. Create the Saved Insight (do not store raw rows snapshot)
      const insightPayload = {
        name: insightName.trim(),
        description: insightDesc.trim() || undefined,
        query: message?.sql || message?.generated_sql || '',
        chart_type: resolvedChartType,
        chart_config: {
          chartType: resolvedChartType,
          columns: columns,
          columnTypes: message?.column_types || {},
        },
        source_id: sourceId || message?.source_id || undefined,
        domain_id: domainId || message?.domain_id || undefined,
        conversation_id: conversationId || message?.conversation_id || undefined,
        message_id: message?.id || undefined,
      };

      const createdInsight = await fetchApi('/dashboards/insights', {
        method: 'POST',
        body: JSON.stringify(insightPayload),
      });

      // 3. Attach insight to chosen or new dashboard
      let targetDashId = selectedDashboardId;
      let targetDashName = '';

      if (isCreatingNewDash) {
        const newDash = await fetchApi('/dashboards', {
          method: 'POST',
          body: JSON.stringify({
            name: newDashName.trim(),
            description: newDashDesc.trim() || undefined,
            visibility: 'private',
            widgets: [
              {
                insight_id: createdInsight.id,
                x: 0,
                y: 0,
                w: 6,
                h: 4,
              },
            ],
          }),
        });
        targetDashId = newDash.id;
        targetDashName = newDash.name;
      } else if (targetDashId) {
        const found = dashboards.find((d) => d.id === targetDashId);
        targetDashName = found?.name || 'Dashboard';

        // Add widget to existing dashboard
        await fetchApi(`/dashboards/${targetDashId}/widgets`, {
          method: 'POST',
          body: JSON.stringify({
            insight_id: createdInsight.id,
            x: 0,
            y: 0,
            w: 6,
            h: 4,
          }),
        });
      }

      onSaved(createdInsight, targetDashId!, targetDashName);
      onClose();
    } catch (err: any) {
      console.error('Failed to save insight:', err);
      let msg = 'Failed to save insight. Please try again.';
      if (typeof err?.message === 'string') {
        msg = err.message;
      } else if (typeof err?.detail === 'string') {
        msg = err.detail;
      } else if (Array.isArray(err?.detail)) {
        msg = err.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
      } else if (typeof err === 'string') {
        msg = err;
      }
      setErrorMessage(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="save-insight-modal-title"
    >
      <div
        className="modal-content"
        style={{
          width: '100%',
          maxWidth: '520px',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border-color)',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'rgba(99, 102, 241, 0.12)',
                color: 'var(--primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Bookmark size={18} />
            </div>
            <div>
              <h2
                id="save-insight-modal-title"
                style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0, color: 'var(--text-main)' }}
              >
                {isBulk && messages ? `Save ${messages.length} Insights` : 'Save Insight'}
              </h2>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {isBulk && messages
                  ? 'Add selected charts to your dashboard library in bulk'
                  : 'Add this chart to your dashboards library'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={saving}
            className="btn-ghost"
            style={{ padding: '0.35rem', borderRadius: 'var(--radius-sm)' }}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1 }}>
          <div style={{ padding: '1.25rem 1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
            {errorMessage && (
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  color: '#ef4444',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{errorMessage}</span>
              </div>
            )}

            {isBulk && messages ? (
              <div
                style={{
                  padding: '0.75rem 1rem',
                  background: 'var(--bg-main)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-main)' }}>
                  <Bookmark size={15} style={{ color: 'var(--primary)' }} />
                  <span>{messages.length} Insights to be added:</span>
                </div>
                <div style={{ maxHeight: '130px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  {messages.map((m: any, idx: number) => {
                    const title = m.title || (m.recommended_visualization && typeof m.recommended_visualization === 'object' ? m.recommended_visualization.title : null) || m.question || `Insight ${idx + 1}`;
                    const chartType = m.visualization || m.chart_recommendation || (m.recommended_visualization && typeof m.recommended_visualization === 'object' ? m.recommended_visualization.chart_type : 'table') || 'table';
                    return (
                      <div
                        key={m.id || idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '0.8rem',
                          padding: '0.35rem 0.6rem',
                          background: 'var(--bg-card)',
                          borderRadius: '6px',
                          border: '1px solid var(--border-color)',
                        }}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '75%', color: 'var(--text-main)' }}>
                          {title}
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: 'var(--bg-hover)', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                          {chartType}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <>
                {/* Insight Name */}
                <div>
                  <label
                    htmlFor="insight-name-input"
                    style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-main)' }}
                  >
                    Insight Name <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    id="insight-name-input"
                    ref={initialFocusRef}
                    type="text"
                    value={insightName}
                    onChange={(e) => setInsightName(e.target.value)}
                    placeholder="e.g. Monthly Revenue by Region"
                    required
                    disabled={saving}
                    style={{ width: '100%', padding: '0.55rem 0.75rem', fontSize: '0.9rem' }}
                  />
                </div>

                {/* Insight Description */}
                <div>
                  <label
                    htmlFor="insight-desc-input"
                    style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-main)' }}
                  >
                    Description <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-muted)' }}>(Optional)</span>
                  </label>
                  <input
                    id="insight-desc-input"
                    type="text"
                    value={insightDesc}
                    onChange={(e) => setInsightDesc(e.target.value)}
                    placeholder="Brief summary or question context"
                    disabled={saving}
                    style={{ width: '100%', padding: '0.55rem 0.75rem', fontSize: '0.9rem' }}
                  />
                </div>
              </>
            )}

            {/* Dashboard Destination Section */}
            <div>
              <label
                style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-main)' }}
              >
                Save to which dashboard? <span style={{ color: '#ef4444' }}>*</span>
              </label>

              {/* Toggle: Select Existing vs Create New */}
              <div
                style={{
                  display: 'flex',
                  gap: '0.5rem',
                  marginBottom: '0.75rem',
                  padding: '3px',
                  background: 'var(--bg-dark)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <button
                  type="button"
                  onClick={() => setIsCreatingNewDash(false)}
                  disabled={dashboards.length === 0}
                  style={{
                    flex: 1,
                    padding: '0.4rem 0.75rem',
                    fontSize: '0.825rem',
                    fontWeight: !isCreatingNewDash ? 600 : 400,
                    borderRadius: '4px',
                    border: 'none',
                    cursor: dashboards.length > 0 ? 'pointer' : 'not-allowed',
                    background: !isCreatingNewDash ? 'var(--bg-card)' : 'transparent',
                    color: !isCreatingNewDash ? 'var(--primary)' : 'var(--text-muted)',
                    boxShadow: !isCreatingNewDash ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  Choose Dashboard ({dashboards.length})
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingNewDash(true)}
                  style={{
                    flex: 1,
                    padding: '0.4rem 0.75rem',
                    fontSize: '0.825rem',
                    fontWeight: isCreatingNewDash ? 600 : 400,
                    borderRadius: '4px',
                    border: 'none',
                    cursor: 'pointer',
                    background: isCreatingNewDash ? 'var(--bg-card)' : 'transparent',
                    color: isCreatingNewDash ? 'var(--primary)' : 'var(--text-muted)',
                    boxShadow: isCreatingNewDash ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.35rem',
                  }}
                >
                  <Plus size={14} /> Create new dashboard
                </button>
              </div>

              {!isCreatingNewDash ? (
                <div>
                  {/* Search Existing Dashboards */}
                  {dashboards.length > 4 && (
                    <div style={{ position: 'relative', marginBottom: '0.5rem' }}>
                      <Search
                        size={14}
                        style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
                      />
                      <input
                        type="text"
                        placeholder="Filter dashboards..."
                        value={dashboardSearch}
                        onChange={(e) => setDashboardSearch(e.target.value)}
                        style={{ width: '100%', padding: '0.4rem 0.5rem 0.4rem 2rem', fontSize: '0.85rem' }}
                      />
                    </div>
                  )}

                  {/* Dashboard List */}
                  <div
                    style={{
                      maxHeight: '180px',
                      overflowY: 'auto',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--bg-dark)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '1px',
                    }}
                  >
                    {loadingDashboards ? (
                      <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                        Loading dashboards...
                      </div>
                    ) : filteredDashboards.length === 0 ? (
                      <div style={{ padding: '1.25rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                        No dashboards found.{' '}
                        <button
                          type="button"
                          onClick={() => setIsCreatingNewDash(true)}
                          style={{ background: 'transparent', border: 'none', color: 'var(--primary)', cursor: 'pointer', textDecoration: 'underline' }}
                        >
                          Create one now
                        </button>
                      </div>
                    ) : (
                      filteredDashboards.map((dash) => {
                        const isSelected = selectedDashboardId === dash.id;
                        return (
                          <div
                            key={dash.id}
                            onClick={() => setSelectedDashboardId(dash.id)}
                            style={{
                              padding: '0.6rem 0.75rem',
                              background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'var(--bg-card)',
                              borderLeft: isSelected ? '3px solid var(--primary)' : '3px solid transparent',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              transition: 'background 0.15s',
                            }}
                            className="hover-bg-light"
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                              <LayoutDashboard size={15} style={{ color: isSelected ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }} />
                              <div style={{ overflow: 'hidden' }}>
                                <div
                                  style={{
                                    fontWeight: isSelected ? 600 : 500,
                                    fontSize: '0.85rem',
                                    color: isSelected ? 'var(--primary)' : 'var(--text-main)',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                >
                                  {dash.name}
                                </div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <span>{dash.widgets?.length || 0} widgets</span>
                                  <span>•</span>
                                  <span style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                                    {dash.visibility === 'published' ? <Globe size={11} /> : <Lock size={11} />}
                                    {dash.visibility === 'published' ? 'Published' : 'Private'}
                                  </span>
                                </div>
                              </div>
                            </div>
                            {isSelected && <Check size={16} style={{ color: 'var(--primary)', flexShrink: 0 }} />}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              ) : (
                /* Inline Create Dashboard Form */
                <div
                  style={{
                    padding: '0.85rem',
                    background: 'var(--bg-dark)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.65rem',
                  }}
                >
                  <div>
                    <label
                      htmlFor="new-dashboard-name"
                      style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem', color: 'var(--text-main)' }}
                    >
                      New Dashboard Name <span style={{ color: '#ef4444' }}>*</span>
                    </label>
                    <input
                      id="new-dashboard-name"
                      type="text"
                      value={newDashName}
                      onChange={(e) => setNewDashName(e.target.value)}
                      placeholder="e.g. Executive Performance"
                      required={isCreatingNewDash}
                      disabled={saving}
                      style={{ width: '100%', padding: '0.45rem 0.65rem', fontSize: '0.85rem' }}
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="new-dashboard-desc"
                      style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '0.25rem', color: 'var(--text-muted)' }}
                    >
                      Description (Optional)
                    </label>
                    <input
                      id="new-dashboard-desc"
                      type="text"
                      value={newDashDesc}
                      onChange={(e) => setNewDashDesc(e.target.value)}
                      placeholder="Brief overview of this dashboard"
                      disabled={saving}
                      style={{ width: '100%', padding: '0.45rem 0.65rem', fontSize: '0.85rem' }}
                    />
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Will be created as a <strong>Private</strong> dashboard owned by you.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer Actions */}
          <div
            style={{
              padding: '1rem 1.5rem',
              borderTop: '1px solid var(--border-color)',
              background: 'var(--bg-dark)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '0.75rem',
            }}
          >
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={saving}
              style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSaveDisabled}
              style={{
                padding: '0.5rem 1.25rem',
                fontSize: '0.875rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              {saving ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Saving...
                </>
              ) : (
                <>
                  <Bookmark size={15} /> Save to Dashboard
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
