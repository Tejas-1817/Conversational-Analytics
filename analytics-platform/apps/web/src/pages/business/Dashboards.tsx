import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { fetchApi } from '../../services/api';
import { ChartRenderer, type ComboLayoutSpec } from '../../components/visualizations/ChartRenderer';
import { useAuth } from '../../contexts/AuthContext';
import {
  LayoutDashboard,
  Plus,
  Bookmark,
  Settings,
  Minimize2,
  RefreshCw,
  MoreVertical,
  AlertCircle,
  X,
  Trash2,
  FileJson,
  Table2,
  Lock,
  Globe,
  Copy,
  Edit2,
  Check,
  Search,
  Filter,
  BarChart2,
  LineChart,
  PieChart,
  Table as TableIcon,
  Save,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  FileText,
  Clock,
  Move,
  Sparkles,
} from 'lucide-react';
import * as RGL from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

// @ts-ignore
const ResponsiveGridLayout =
  (RGL as any).ResponsiveGridLayout ||
  (RGL as any).Responsive ||
  (RGL as any).default?.Responsive ||
  (RGL as any).default ||
  'div';

function useGridContainerWidth(initialWidth = 1200) {
  const [containerEl, setContainerEl] = React.useState<HTMLDivElement | null>(null);
  const containerRef = React.useCallback((node: HTMLDivElement | null) => {
    setContainerEl(node);
  }, []);
  const [width, setWidth] = React.useState(initialWidth);

  React.useEffect(() => {
    if (!containerEl) return;
    const updateWidth = () => {
      const nextWidth = containerEl.offsetWidth;
      if (nextWidth > 0) {
        setWidth(nextWidth);
      }
    };
    updateWidth();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(updateWidth);
      observer.observe(containerEl);
      return () => observer.disconnect();
    }
  }, [containerEl]);

  return { containerRef, width };
}

// --- Safe URL Transformer for ReactMarkdown ---
const safeUrlTransform = (url: string) => {
  const trimmed = url.trim().toLowerCase();
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('mailto:')) {
    return url;
  }
  return '';
};

// --- Types ---

interface TabItem {
  id: string;
  dashboard_id: string;
  name: string;
  position: number;
  created_at?: string;
  updated_at?: string;
}

interface WidgetItem {
  id: string;
  dashboard_id: string;
  tab_id?: string | null;
  insight_id?: string | null;
  widget_type: 'insight' | 'text';
  x: number;
  y: number;
  w: number;
  h: number;
  title_override?: string | null;
  chart_type_override?: string | null;
  settings?: Record<string, any>;
  layouts?: Record<string, any>;
  insight?: any;
}

interface DashboardItem {
  id: string;
  tenant_id: string;
  user_id: string;
  name: string;
  description?: string | null;
  visibility: 'private' | 'published';
  overview_summary?: string | null;
  created_at: string;
  updated_at: string;
  tabs?: TabItem[];
  widgets: WidgetItem[];
}

// --- Live Widget Component ---

interface DashboardWidgetCardProps {
  widget: WidgetItem;
  isEditMode?: boolean;
  canEdit: boolean;
  isAdmin: boolean;
  tabs: TabItem[];
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
  onRemove: () => void;
  onDuplicate: () => void;
  onMoveToTab: (targetTabId: string) => void;
  onCloneToTab: (targetTabId: string) => void;
  onUpdateWidget: (updates: {
    title_override?: string | null;
    chart_type_override?: string | null;
    settings?: Record<string, any>;
  }) => void;
  onRunFinished?: (widgetId: string, runInfo: { lastRunAt: string | null; cached: boolean }) => void;
  forceRefreshCounter: number;
}

const DashboardWidgetCard: React.FC<DashboardWidgetCardProps> = ({
  widget,
  isEditMode: _isEditMode,
  canEdit,
  isAdmin,
  tabs,
  isFullScreen,
  onToggleFullScreen,
  onRemove,
  onDuplicate,
  onMoveToTab,
  onCloneToTab,
  onUpdateWidget,
  onRunFinished,
  forceRefreshCounter,
}) => {
  const isTextWidget = widget.widget_type === 'text';

  const [loading, setLoading] = useState(!isTextWidget);
  const [error, setError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [lockDetail, setLockDetail] = useState<string | null>(null);
  const [runData, setRunData] = useState<any>(null);

  const [showMenu, setShowMenu] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');

  // Modals for Text Editing, Combo Editing, Tab Move/Clone
  const [showTextEditModal, setShowTextEditModal] = useState(false);
  const [textDraft, setTextDraft] = useState('');

  const [showComboModal, setShowComboModal] = useState(false);
  const [comboXAxis, setComboXAxis] = useState('');
  const [comboLeftType, setComboLeftType] = useState<'bar' | 'line' | 'area'>('bar');
  const [comboLeftCol, setComboLeftCol] = useState('');
  const [comboLeftUnit, setComboLeftUnit] = useState('');
  const [comboRightType, setComboRightType] = useState<'bar' | 'line' | 'area'>('line');
  const [comboRightCol, setComboRightCol] = useState('');
  const [comboRightUnit, setComboRightUnit] = useState('');

  const [showTabActionModal, setShowTabActionModal] = useState<'move' | 'clone' | null>(null);
  const [selectedTargetTabId, setSelectedTargetTabId] = useState<string>('');

  const effectiveTitle =
    widget.title_override ||
    (isTextWidget ? 'Text Note' : widget.insight?.name || 'Untitled Insight');

  const effectiveChartType =
    widget.chart_type_override ||
    widget.insight?.chart_type ||
    widget.insight?.chart_config?.chartType ||
    'table';

  const loadWidgetData = useCallback(
    async (bypassCache = false) => {
      if (isTextWidget || !widget.insight_id) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      setLocked(false);
      setLockDetail(null);

      try {
        const queryParam = bypassCache ? '?force_refresh=true' : '';
        const res = await fetchApi(`/dashboards/insights/${widget.insight_id}/run${queryParam}`, {
          method: 'POST',
        });

        if (res.status === 'locked' || res.locked) {
          setLocked(true);
          setLockDetail(res.detail || 'Access restricted for your account.');
        } else if (res.status === 'error' || res.error) {
          setError(res.error || 'Failed to execute query.');
        } else {
          setRunData(res);
          onRunFinished?.(widget.id, {
            lastRunAt: res.last_run_at || res.cached_at || new Date().toISOString(),
            cached: Boolean(res.cached),
          });
        }
      } catch (err: any) {
        console.error('Failed to run insight widget:', err);
        setError(err.message || 'Execution error');
      } finally {
        setLoading(false);
      }
    },
    [isTextWidget, widget.insight_id, widget.id, onRunFinished]
  );

  useEffect(() => {
    loadWidgetData(false);
  }, [loadWidgetData]);

  // Respond to dashboard-wide refresh trigger
  useEffect(() => {
    if (forceRefreshCounter > 0) {
      loadWidgetData(true);
    }
  }, [forceRefreshCounter, loadWidgetData]);

  const handleSaveTitle = () => {
    const trimmed = titleInput.trim();
    onUpdateWidget({ title_override: trimmed || null });
    setIsEditingTitle(false);
  };

  const handleChangeChartType = (newType: string) => {
    onUpdateWidget({ chart_type_override: newType });
    setShowMenu(false);
  };

  const handleSaveTextWidget = () => {
    onUpdateWidget({
      settings: {
        ...(widget.settings || {}),
        text: textDraft,
      },
    });
    setShowTextEditModal(false);
  };

  const handleOpenComboModal = () => {
    const cols = runData?.columns || [];
    const numCols = cols.filter(
      (c: string) => runData?.column_types?.[c] === 'number' || runData?.column_types?.[c] === 'NUMERIC'
    );
    const existingSpec = widget.settings?.combo_spec;

    if (existingSpec && existingSpec.schema_version === 1) {
      setComboXAxis(existingSpec.x_axis || cols[0] || '');
      const left = existingSpec.y_axes?.[0];
      const right = existingSpec.y_axes?.[1];
      if (left) {
        setComboLeftType(left.series_type === 'column' ? 'bar' : left.series_type || 'bar');
        setComboLeftCol(left.columns?.[0] || '');
        setComboLeftUnit(left.unit || '');
      }
      if (right) {
        setComboRightType(right.series_type === 'column' ? 'bar' : right.series_type || 'line');
        setComboRightCol(right.columns?.[0] || '');
        setComboRightUnit(right.unit || '');
      }
    } else {
      setComboXAxis(cols[0] || '');
      setComboLeftType('bar');
      setComboLeftCol(numCols[0] || cols[1] || cols[0] || '');
      setComboLeftUnit('');
      setComboRightType('line');
      setComboRightCol(numCols[1] || cols[2] || '');
      setComboRightUnit('%');
    }

    setShowComboModal(true);
    setShowMenu(false);
  };

  const handleSaveComboSpec = () => {
    if (!comboXAxis || !comboLeftCol) {
      alert('Please select an X-Axis and at least one Y-Axis column.');
      return;
    }

    const yAxes: any[] = [
      {
        position: 'left',
        series_type: comboLeftType,
        columns: [comboLeftCol],
        unit: comboLeftUnit.trim() || null,
      },
    ];

    if (comboRightCol) {
      yAxes.push({
        position: 'right',
        series_type: comboRightType,
        columns: [comboRightCol],
        unit: comboRightUnit.trim() || null,
      });
    }

    const spec: ComboLayoutSpec = {
      schema_version: 1,
      x_axis: comboXAxis,
      y_axes: yAxes,
    };

    onUpdateWidget({
      chart_type_override: 'combo',
      settings: {
        ...(widget.settings || {}),
        combo_spec: spec,
      },
    });

    setShowComboModal(false);
  };

  const exportToCSV = (data: any[], filename: string) => {
    if (!data || data.length === 0) return;
    const keys = Object.keys(data[0]);
    const csvContent = [
      keys.join(','),
      ...data.map((row) => keys.map((k) => JSON.stringify(row[k] || '')).join(',')),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', `${filename}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const otherTabs = tabs.filter((t) => t.id !== widget.tab_id);

  return (
    <div
      className="card"
      style={{
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        border: '1px solid var(--border-color)',
        overflow: 'hidden',
        background: 'var(--bg-card)',
        ...(isFullScreen
          ? {
              position: 'fixed',
              top: '1.5rem',
              left: '1.5rem',
              right: '1.5rem',
              bottom: '1.5rem',
              zIndex: 9999,
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
            }
          : {}),
      }}
    >
      {/* Widget Header */}
      <div
        style={{
          padding: '0.65rem 0.9rem',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-dark)',
          userSelect: 'none',
        }}
        className={`drag-handle ${canEdit ? 'cursor-move' : ''}`}
      >
        <div style={{ overflow: 'hidden', flex: 1, marginRight: '0.5rem' }}>
          {isEditingTitle ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <input
                type="text"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveTitle();
                  if (e.key === 'Escape') setIsEditingTitle(false);
                }}
                autoFocus
                style={{ padding: '0.2rem 0.4rem', fontSize: '0.85rem', width: '100%' }}
              />
              <button
                className="btn-ghost"
                onClick={handleSaveTitle}
                style={{ padding: '0.2rem', color: 'var(--primary)' }}
                title="Save title"
              >
                <Check size={14} />
              </button>
              <button
                className="btn-ghost"
                onClick={() => setIsEditingTitle(false)}
                style={{ padding: '0.2rem', color: 'var(--text-muted)' }}
                title="Cancel"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {isTextWidget ? (
                <FileText size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              ) : null}
              <h4
                style={{
                  margin: 0,
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  color: 'var(--text-main)',
                }}
                title={effectiveTitle}
              >
                {effectiveTitle}
              </h4>
              {canEdit && (
                <button
                  className="btn-ghost"
                  onClick={() => {
                    setTitleInput(effectiveTitle);
                    setIsEditingTitle(true);
                  }}
                  style={{ padding: '0.15rem', color: 'var(--text-muted)', opacity: 0.7 }}
                  title="Rename widget"
                >
                  <Edit2 size={12} />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1" style={{ flexShrink: 0 }}>
          {/* Admin Freshness Marker */}
          {isAdmin && !isTextWidget && runData && (
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 600,
                padding: '0.1rem 0.4rem',
                borderRadius: '4px',
                background: runData.cached ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                color: runData.cached ? '#d97706' : '#059669',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.2rem',
                marginRight: '0.25rem',
              }}
              title={runData.cached ? 'Served from Redis/Memory viewer cache' : 'Executed live on database'}
            >
              {runData.cached ? '⚡ Cached' : '🟢 Live'}
            </span>
          )}

          {/* Refresh Button (only for insight widgets) */}
          {!isTextWidget && (
            <button
              className="btn-ghost"
              style={{ padding: '0.25rem', borderRadius: '4px' }}
              onClick={() => loadWidgetData(true)}
              disabled={loading}
              title="Refresh widget data"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            </button>
          )}

          {/* Edit Markdown action for Text Widgets */}
          {isTextWidget && canEdit && (
            <button
              className="btn-ghost"
              style={{ padding: '0.25rem', borderRadius: '4px' }}
              onClick={() => {
                setTextDraft(widget.settings?.text || widget.settings?.content || '');
                setShowTextEditModal(true);
              }}
              title="Edit Markdown Text"
            >
              <Edit2 size={13} />
            </button>
          )}

          {/* Exit Fullscreen Button (only shown if currently fullscreen) */}
          {isFullScreen && (
            <button
              className="btn-ghost"
              style={{ padding: '0.25rem', borderRadius: '4px' }}
              onClick={onToggleFullScreen}
              title="Exit fullscreen"
            >
              <Minimize2 size={13} />
            </button>
          )}

          {/* Editor Action Controls */}
          {canEdit && (
            <>
              {/* Duplicate */}
              <button
                className="btn-ghost"
                style={{ padding: '0.25rem', borderRadius: '4px' }}
                onClick={onDuplicate}
                title="Duplicate widget"
              >
                <Copy size={13} />
              </button>
              {/* Remove */}
              <button
                className="btn-ghost text-error"
                style={{ padding: '0.25rem', borderRadius: '4px' }}
                onClick={onRemove}
                title="Remove widget from dashboard"
              >
                <Trash2 size={13} />
              </button>
            </>
          )}

          {/* Dropdown Menu (Chart Switcher & Exports & Tab Move) */}
          <div style={{ position: 'relative' }}>
            <button
              className="btn-ghost"
              style={{ padding: '0.25rem', borderRadius: '4px' }}
              onClick={() => setShowMenu(!showMenu)}
              title="More options"
            >
              <MoreVertical size={13} />
            </button>
            {showMenu && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '100%',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius)',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.2)',
                  zIndex: 100,
                  minWidth: '180px',
                  overflow: 'hidden',
                  padding: '0.25rem 0',
                }}
              >
                {/* Text Widget: Edit Text */}
                {isTextWidget && canEdit && (
                  <button
                    className="btn-ghost"
                    style={{ width: '100%', justifyContent: 'flex-start', padding: '0.4rem 0.75rem', borderRadius: 0, fontSize: '0.8rem' }}
                    onClick={() => {
                      setTextDraft(widget.settings?.text || widget.settings?.content || '');
                      setShowTextEditModal(true);
                      setShowMenu(false);
                    }}
                  >
                    <Edit2 size={13} style={{ marginRight: '0.5rem' }} /> Edit Markdown Note
                  </button>
                )}

                {/* Switch Chart Type Section (when canEdit and not text widget) */}
                {canEdit && !isTextWidget && (
                  <>
                    <div style={{ padding: '0.35rem 0.75rem', fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                      Chart Type
                    </div>
                    {[
                      { id: 'table', label: 'Table', icon: TableIcon },
                      { id: 'bar', label: 'Bar Chart', icon: BarChart2 },
                      { id: 'line', label: 'Line Chart', icon: LineChart },
                      { id: 'pie', label: 'Pie Chart', icon: PieChart },
                      { id: 'combo', label: 'Dual-Axis Combo', icon: SlidersHorizontal },
                    ].map((ct) => {
                      const IconComp = ct.icon;
                      const isSel = effectiveChartType === ct.id;
                      return (
                        <button
                          key={ct.id}
                          className="btn-ghost"
                          style={{
                            width: '100%',
                            justifyContent: 'flex-start',
                            padding: '0.35rem 0.75rem',
                            borderRadius: 0,
                            fontSize: '0.8rem',
                            fontWeight: isSel ? 600 : 400,
                            color: isSel ? 'var(--primary)' : 'var(--text-main)',
                            background: isSel ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                          }}
                          onClick={() => {
                            if (ct.id === 'combo') {
                              handleOpenComboModal();
                            } else {
                              handleChangeChartType(ct.id);
                            }
                          }}
                        >
                          <IconComp size={13} style={{ marginRight: '0.5rem' }} /> {ct.label}
                        </button>
                      );
                    })}

                    <button
                      className="btn-ghost"
                      style={{ width: '100%', justifyContent: 'flex-start', padding: '0.4rem 0.75rem', borderRadius: 0, fontSize: '0.8rem', color: 'var(--primary)' }}
                      onClick={handleOpenComboModal}
                    >
                      <SlidersHorizontal size={13} style={{ marginRight: '0.5rem' }} /> Configure Combo Spec...
                    </button>
                    <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.25rem 0' }} />
                  </>
                )}

                {/* Move / Clone to Tab (if dashboard has >= 2 tabs) */}
                {canEdit && otherTabs.length > 0 && (
                  <>
                    <div style={{ padding: '0.35rem 0.75rem', fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                      Tabs
                    </div>
                    <button
                      className="btn-ghost"
                      style={{ width: '100%', justifyContent: 'flex-start', padding: '0.4rem 0.75rem', borderRadius: 0, fontSize: '0.8rem' }}
                      onClick={() => {
                        setSelectedTargetTabId(otherTabs[0]?.id || '');
                        setShowTabActionModal('move');
                        setShowMenu(false);
                      }}
                    >
                      <Move size={13} style={{ marginRight: '0.5rem' }} /> Move to Tab...
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ width: '100%', justifyContent: 'flex-start', padding: '0.4rem 0.75rem', borderRadius: 0, fontSize: '0.8rem' }}
                      onClick={() => {
                        setSelectedTargetTabId(otherTabs[0]?.id || '');
                        setShowTabActionModal('clone');
                        setShowMenu(false);
                      }}
                    >
                      <Copy size={13} style={{ marginRight: '0.5rem' }} /> Clone to Tab...
                    </button>
                    <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.25rem 0' }} />
                  </>
                )}

                {/* Export Options (only for insight widgets with data) */}
                {!isTextWidget && (
                  <>
                    <button
                      className="btn-ghost"
                      style={{ width: '100%', justifyContent: 'flex-start', padding: '0.4rem 0.75rem', borderRadius: 0, fontSize: '0.8rem' }}
                      onClick={() => {
                        exportToCSV(runData?.data || [], effectiveTitle);
                        setShowMenu(false);
                      }}
                      disabled={!runData?.data?.length}
                    >
                      <Table2 size={13} style={{ marginRight: '0.5rem' }} /> Export CSV
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ width: '100%', justifyContent: 'flex-start', padding: '0.4rem 0.75rem', borderRadius: 0, fontSize: '0.8rem' }}
                      onClick={() => {
                        const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(runData || {}));
                        const a = document.createElement('a');
                        a.href = dataStr;
                        a.download = `${effectiveTitle}.json`;
                        a.click();
                        setShowMenu(false);
                      }}
                      disabled={!runData}
                    >
                      <FileJson size={13} style={{ marginRight: '0.5rem' }} /> Export JSON
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Widget Body Content */}
      <div style={{ flex: 1, padding: '0.75rem', overflow: 'hidden', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {isTextWidget ? (
          /* Text Widget: Safe Markdown Render */
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '0.5rem',
              fontSize: '0.875rem',
              lineHeight: 1.6,
              color: 'var(--text-main)',
            }}
          >
            <ReactMarkdown
              urlTransform={safeUrlTransform}
              components={{
                a: ({ node: _node, ...props }) => {
                  if (!props.href) return <span>{props.children}</span>;
                  return (
                    <a
                      {...props}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--primary)', textDecoration: 'underline' }}
                    />
                  );
                },
              }}
            >
              {widget.settings?.text || widget.settings?.content || '*Click edit to write markdown notes.*'}
            </ReactMarkdown>
          </div>
        ) : loading ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem', justifyContent: 'center', alignItems: 'center' }}>
            <RefreshCw size={24} className="animate-spin text-muted" style={{ opacity: 0.6 }} />
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Running live query...</span>
          </div>
        ) : locked ? (
          /* Locked State Placeholder */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1rem',
              textAlign: 'center',
              background: 'rgba(245, 158, 11, 0.04)',
              borderRadius: 'var(--radius-sm)',
              border: '1px dashed rgba(245, 158, 11, 0.3)',
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: 'rgba(245, 158, 11, 0.12)',
                color: '#d97706',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '0.5rem',
              }}
            >
              <Lock size={20} />
            </div>
            <h5 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>
              Data Access Restricted
            </h5>
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', color: 'var(--text-muted)', maxWidth: '280px', lineHeight: 1.4 }}>
              {lockDetail || 'You do not have permission to view the data source or tables referenced in this insight.'}
            </p>
          </div>
        ) : error ? (
          /* Error State */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1rem',
              textAlign: 'center',
              background: 'rgba(239, 68, 68, 0.05)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
            }}
          >
            <AlertCircle size={22} style={{ color: '#ef4444', marginBottom: '0.4rem' }} />
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#ef4444', maxWidth: '300px' }}>{error}</p>
            <button
              className="btn-secondary"
              onClick={() => loadWidgetData(true)}
              style={{ marginTop: '0.65rem', padding: '0.25rem 0.65rem', fontSize: '0.75rem' }}
            >
              Retry
            </button>
          </div>
        ) : runData?.data ? (
          /* Live Chart Render */
          <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
            <ChartRenderer
              data={runData.data}
              chartType={effectiveChartType}
              columns={runData.columns}
              columnTypes={runData.column_types}
              comboSpec={widget.settings?.combo_spec}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted" style={{ fontSize: '0.8rem' }}>
            No visualization data
          </div>
        )}
      </div>

      {/* Widget Footer Meta */}
      {!isTextWidget && runData && !locked && !error && (
        <div
          style={{
            padding: '0.35rem 0.9rem',
            borderTop: '1px solid var(--border-color)',
            background: 'var(--bg-dark)',
            fontSize: '0.72rem',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{runData.row_count || runData.data?.length || 0} rows</span>
          {runData.execution_time_ms ? <span>{runData.execution_time_ms.toFixed(1)}ms</span> : null}
        </div>
      )}

      {/* Modal: Edit Markdown for Text Widget */}
      {showTextEditModal && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }}
          onClick={() => setShowTextEditModal(false)}
        >
          <div
            className="modal-content"
            style={{ width: '560px', maxWidth: '92vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.25rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Edit Markdown Note</h3>
              </div>
              <button className="btn-ghost" onClick={() => setShowTextEditModal(false)} style={{ padding: '0.2rem' }}>
                <X size={16} />
              </button>
            </div>

            <p style={{ margin: '0 0 0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Supports standard Markdown. Raw HTML is safely escaped.
            </p>

            <textarea
              value={textDraft}
              onChange={(e) => setTextDraft(e.target.value)}
              rows={10}
              placeholder="### Summary&#10;Write narrative notes or executive takeaways here..."
              style={{ width: '100%', padding: '0.6rem', fontSize: '0.85rem', fontFamily: 'monospace', resize: 'vertical' }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
              <button className="btn-secondary" onClick={() => setShowTextEditModal(false)} style={{ padding: '0.4rem 0.8rem' }}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleSaveTextWidget} style={{ padding: '0.4rem 1rem' }}>
                Save Note
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Configure Combo Chart */}
      {showComboModal && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }}
          onClick={() => setShowComboModal(false)}
        >
          <div
            className="modal-content"
            style={{ width: '520px', maxWidth: '92vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.25rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <SlidersHorizontal size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Configure Dual-Axis (Combo) Chart</h3>
              </div>
              <button className="btn-ghost" onClick={() => setShowComboModal(false)} style={{ padding: '0.2rem' }}>
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.85rem' }}>
              {/* X Axis */}
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.3rem' }}>X-Axis Category Column</label>
                <select
                  value={comboXAxis}
                  onChange={(e) => setComboXAxis(e.target.value)}
                  style={{ width: '100%', padding: '0.4rem', fontSize: '0.85rem' }}
                >
                  {(runData?.columns || []).map((col: string) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              </div>

              {/* Left Y Axis */}
              <div style={{ padding: '0.75rem', background: 'var(--bg-dark)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                <span style={{ fontWeight: 600, color: 'var(--primary)', display: 'block', marginBottom: '0.4rem' }}>
                  Left Y-Axis (Primary Metric)
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px', gap: '0.5rem' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Column</label>
                    <select
                      value={comboLeftCol}
                      onChange={(e) => setComboLeftCol(e.target.value)}
                      style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem' }}
                    >
                      {(runData?.columns || []).map((col: string) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Series Type</label>
                    <select
                      value={comboLeftType}
                      onChange={(e) => setComboLeftType(e.target.value as any)}
                      style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem' }}
                    >
                      <option value="bar">Bar (Column)</option>
                      <option value="line">Line</option>
                      <option value="area">Area</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Unit</label>
                    <input
                      type="text"
                      placeholder="e.g. $"
                      value={comboLeftUnit}
                      onChange={(e) => setComboLeftUnit(e.target.value)}
                      style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem' }}
                    />
                  </div>
                </div>
              </div>

              {/* Right Y Axis */}
              <div style={{ padding: '0.75rem', background: 'var(--bg-dark)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                <span style={{ fontWeight: 600, color: 'var(--primary)', display: 'block', marginBottom: '0.4rem' }}>
                  Right Y-Axis (Secondary Metric)
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px', gap: '0.5rem' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Column</label>
                    <select
                      value={comboRightCol}
                      onChange={(e) => setComboRightCol(e.target.value)}
                      style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem' }}
                    >
                      <option value="">(None)</option>
                      {(runData?.columns || []).map((col: string) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Series Type</label>
                    <select
                      value={comboRightType}
                      onChange={(e) => setComboRightType(e.target.value as any)}
                      style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem' }}
                    >
                      <option value="line">Line</option>
                      <option value="bar">Bar (Column)</option>
                      <option value="area">Area</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Unit</label>
                    <input
                      type="text"
                      placeholder="e.g. %"
                      value={comboRightUnit}
                      onChange={(e) => setComboRightUnit(e.target.value)}
                      style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem' }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
              <button className="btn-secondary" onClick={() => setShowComboModal(false)} style={{ padding: '0.4rem 0.8rem' }}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleSaveComboSpec} style={{ padding: '0.4rem 1rem' }}>
                Apply Dual-Axis Spec
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Move / Clone to Tab */}
      {showTabActionModal && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }}
          onClick={() => setShowTabActionModal(null)}
        >
          <div
            className="modal-content"
            style={{ width: '400px', maxWidth: '90vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.25rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 }}>
              {showTabActionModal === 'move' ? 'Move Widget to Tab' : 'Clone Widget to Tab'}
            </h3>
            <p style={{ margin: '0 0 1rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Select target tab for <strong>"{effectiveTitle}"</strong>:
            </p>

            <select
              value={selectedTargetTabId}
              onChange={(e) => setSelectedTargetTabId(e.target.value)}
              style={{ width: '100%', padding: '0.45rem', fontSize: '0.85rem', marginBottom: '1.25rem' }}
            >
              {otherTabs.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={() => setShowTabActionModal(null)} style={{ padding: '0.4rem 0.8rem' }}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={() => {
                  if (!selectedTargetTabId) return;
                  if (showTabActionModal === 'move') {
                    onMoveToTab(selectedTargetTabId);
                  } else {
                    onCloneToTab(selectedTargetTabId);
                  }
                  setShowTabActionModal(null);
                }}
                style={{ padding: '0.4rem 1rem' }}
              >
                {showTabActionModal === 'move' ? 'Move' : 'Clone'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// --- Main Dashboards Page ---

export const Dashboards: React.FC = () => {
  const { user } = useAuth();
  const isObserver = user?.role === 'VIEWER';
  const isAdmin = user?.role === 'ADMIN';

  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const queryId = searchParams.get('id');
  const queryTabId = searchParams.get('tab');

  // Container width measurement hook for react-grid-layout
  const { containerRef: gridContainerRef, width: gridWidth } = useGridContainerWidth(1200);

  const [dashboards, setDashboards] = useState<DashboardItem[]>([]);
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [activeDashboardId, setActiveDashboardId] = useState<string | null>(null);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);

  // Dashboard title dropdown state
  const [isDashDropdownOpen, setIsDashDropdownOpen] = useState(false);
  const dashDropdownRef = useRef<HTMLDivElement | null>(null);

  // Close dashboard dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dashDropdownRef.current && !dashDropdownRef.current.contains(event.target as Node)) {
        setIsDashDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectDashboard = (nextId: string) => {
    if (!nextId || nextId === activeDashboardId) {
      setIsDashDropdownOpen(false);
      return;
    }
    if (hasUnsavedLayout) {
      if (!confirm('You have unsaved layout changes. Discard them?')) return;
    }
    setActiveDashboardId(nextId);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('id', nextId);
      next.delete('tab');
      return next;
    });
    setIsDashDropdownOpen(false);
  };

  // Layout state
  const [hasUnsavedLayout, setHasUnsavedLayout] = useState(false);
  const [currentLayouts, setCurrentLayouts] = useState<any>({});
  const [activeBreakpoint, setActiveBreakpoint] = useState<string>('lg');
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [fullScreenWidgetId, setFullScreenWidgetId] = useState<string | null>(null);

  // Create Dashboard Modal
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Modals & Drawers
  const [showAddInsightDrawer, setShowAddInsightDrawer] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isSavingLayout, setIsSavingLayout] = useState(false);

  // Overview edit modal state
  const [showOverviewModal, setShowOverviewModal] = useState(false);
  const [overviewDraft, setOverviewDraft] = useState('');
  const [overviewCollapsed, setOverviewCollapsed] = useState(false);

  // Tab Rename / Delete Modals
  const [editingTabId, setEditingTabId] = useState<string | null>(null);
  const [tabRenameDraft, setTabRenameDraft] = useState('');
  const [deleteTabModal, setDeleteTabModal] = useState<TabItem | null>(null);
  const [deleteTabMoveTarget, setDeleteTabMoveTarget] = useState<string>('');

  // Refresh & Freshness State
  const [forceRefreshCounter, setForceRefreshCounter] = useState(0);
  const [widgetRunTimes, setWidgetRunTimes] = useState<Record<string, { lastRunAt: string | null; cached: boolean }>>({});

  // Create Dashboard Form state
  const [newDashName, setNewDashName] = useState('');
  const [newDashDesc, setNewDashDesc] = useState('');
  const [newDashVisibility, setNewDashVisibility] = useState<'private' | 'published'>('private');
  const [isCreatingDash, setIsCreatingDash] = useState(false);

  // Settings edit state
  const [editDashName, setEditDashName] = useState('');
  const [editDashDesc, setEditDashDesc] = useState('');
  const [editDashVisibility, setEditDashVisibility] = useState<'private' | 'published'>('private');

  // Search & Filter for Insights Library
  const [insightSearch, setInsightSearch] = useState('');
  const [insightSourceFilter, setInsightSourceFilter] = useState('');

  const loadData = useCallback(async (preferDashId?: string) => {
    try {
      setLoading(true);
      const [dRes, iRes] = await Promise.all([
        fetchApi('/dashboards'),
        fetchApi('/dashboards/insights'),
      ]);
      const dashList: DashboardItem[] = Array.isArray(dRes) ? dRes : [];
      setDashboards(dashList);
      setInsights(Array.isArray(iRes) ? iRes : []);

      // Determine active dashboard
      setActiveDashboardId((prevId) => {
        const targetId = preferDashId || prevId;
        if (targetId && dashList.some((d) => d.id === targetId)) {
          return targetId;
        }
        return dashList.length > 0 ? dashList[0].id : null;
      });
    } catch (err) {
      console.error('Failed to load dashboards data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + URL query parameter / route change check
  useEffect(() => {
    loadData(queryId || undefined);
  }, [queryId, location.key, loadData]);

  const activeDashboard = useMemo(
    () => dashboards.find((d) => d.id === activeDashboardId) || null,
    [dashboards, activeDashboardId]
  );

  const canEditActiveDashboard = useMemo(() => {
    if (isObserver) return false;
    if (!activeDashboard || !user) return false;
    return activeDashboard.user_id === user.id || user.role === 'ADMIN';
  }, [activeDashboard, user, isObserver]);

  // Synchronize activeTabId with activeDashboard and URL query parameter
  useEffect(() => {
    if (!activeDashboard) {
      setActiveTabId(null);
      return;
    }
    const tabs = activeDashboard.tabs || [];
    if (tabs.length === 0) {
      setActiveTabId(null);
      return;
    }
    if (queryTabId && tabs.some((t) => t.id === queryTabId)) {
      setActiveTabId(queryTabId);
    } else {
      setActiveTabId(tabs[0].id);
    }
  }, [activeDashboard?.id, activeDashboard?.tabs, queryTabId]);

  // Read / write overview collapsed state from localStorage
  useEffect(() => {
    if (activeDashboard) {
      const stored = localStorage.getItem(`dash_overview_collapsed_${activeDashboard.id}`);
      setOverviewCollapsed(stored === 'true');
    }
  }, [activeDashboard?.id]);

  const toggleOverviewCollapsed = () => {
    if (!activeDashboard) return;
    const next = !overviewCollapsed;
    setOverviewCollapsed(next);
    localStorage.setItem(`dash_overview_collapsed_${activeDashboard.id}`, String(next));
  };

  // Filter widgets for the current tab
  const activeTabWidgets = useMemo(() => {
    if (!activeDashboard) return [];
    const tabs = activeDashboard.tabs || [];
    if (tabs.length === 0) {
      return activeDashboard.widgets;
    }
    const currentTab = tabs.find((t) => t.id === activeTabId) || tabs[0];
    const isFirstTab = tabs[0]?.id === currentTab.id;
    return activeDashboard.widgets.filter((w) => {
      if (w.tab_id === currentTab.id) return true;
      if (isFirstTab && !w.tab_id) return true; // legacy unassigned widgets fall back to first tab
      return false;
    });
  }, [activeDashboard, activeTabId]);

  // Initialize layout when active tab widgets change
  useEffect(() => {
    if (!activeDashboard) {
      setCurrentLayouts({});
      setHasUnsavedLayout(false);
      return;
    }
    const lgLayout = activeTabWidgets.map((w) => ({
      i: w.id,
      x: w.x ?? 0,
      y: w.y ?? 0,
      w: w.w || 6,
      h: w.h || 4,
      minW: 2,
      minH: 2,
    }));
    setCurrentLayouts({ lg: lgLayout });
    setHasUnsavedLayout(false);
  }, [activeDashboard?.id, activeTabId, activeTabWidgets.length]);

  // Handle Tab Switch
  const handleSelectTab = (tabId: string) => {
    if (hasUnsavedLayout) {
      if (!confirm('You have unsaved layout changes on this tab. Discard them?')) return;
    }
    setActiveTabId(tabId);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', tabId);
      return next;
    });
  };

  // Add new tab
  const handleAddTab = async () => {
    if (!activeDashboard || !canEditActiveDashboard) return;
    const tabName = prompt('Enter a name for the new tab:');
    if (!tabName || !tabName.trim()) return;

    try {
      const updatedDash = await fetchApi(`/dashboards/${activeDashboard.id}/tabs`, {
        method: 'POST',
        body: JSON.stringify({ name: tabName.trim() }),
      });
      setDashboards((prev) => prev.map((d) => (d.id === updatedDash.id ? updatedDash : d)));
      const newTabs = updatedDash.tabs || [];
      const createdTab = newTabs[newTabs.length - 1];
      if (createdTab) {
        handleSelectTab(createdTab.id);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to create tab');
    }
  };

  // Rename tab
  const handleSaveRenameTab = async (tabId: string) => {
    if (!activeDashboard || !canEditActiveDashboard || !tabRenameDraft.trim()) return;
    try {
      const updatedDash = await fetchApi(`/dashboards/${activeDashboard.id}/tabs/${tabId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: tabRenameDraft.trim() }),
      });
      setDashboards((prev) => prev.map((d) => (d.id === updatedDash.id ? updatedDash : d)));
      setEditingTabId(null);
    } catch (err: any) {
      alert(err.message || 'Failed to rename tab');
    }
  };

  // Reorder tabs
  const handleMoveTab = async (tabId: string, direction: 'left' | 'right') => {
    if (!activeDashboard || !canEditActiveDashboard) return;
    const tabs = [...(activeDashboard.tabs || [])];
    const idx = tabs.findIndex((t) => t.id === tabId);
    if (idx < 0) return;
    const targetIdx = direction === 'left' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= tabs.length) return;

    const [moved] = tabs.splice(idx, 1);
    tabs.splice(targetIdx, 0, moved);
    const tabIds = tabs.map((t) => t.id);

    try {
      const updatedDash = await fetchApi(`/dashboards/${activeDashboard.id}/tabs/reorder`, {
        method: 'PUT',
        body: JSON.stringify({ tab_ids: tabIds }),
      });
      setDashboards((prev) => prev.map((d) => (d.id === updatedDash.id ? updatedDash : d)));
    } catch (err: any) {
      alert(err.message || 'Failed to reorder tabs');
    }
  };

  // Delete tab
  const handleDeleteTab = async () => {
    if (!activeDashboard || !canEditActiveDashboard || !deleteTabModal) return;
    const tabId = deleteTabModal.id;
    const query = deleteTabMoveTarget ? `?move_to_tab_id=${deleteTabMoveTarget}` : '';

    try {
      const updatedDash = await fetchApi(`/dashboards/${activeDashboard.id}/tabs/${tabId}${query}`, {
        method: 'DELETE',
      });
      setDashboards((prev) => prev.map((d) => (d.id === updatedDash.id ? updatedDash : d)));
      setDeleteTabModal(null);
      setDeleteTabMoveTarget('');
      const remainingTabs = updatedDash.tabs || [];
      if (remainingTabs.length > 0) {
        handleSelectTab(remainingTabs[0].id);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete tab');
    }
  };

  // Save Overview Summary
  const handleSaveOverviewSummary = async () => {
    if (!activeDashboard || !canEditActiveDashboard) return;
    try {
      const updated = await fetchApi(`/dashboards/${activeDashboard.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ overview_summary: overviewDraft.trim() || null }),
      });
      setDashboards((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      setShowOverviewModal(false);
    } catch (err: any) {
      alert(err.message || 'Failed to update overview summary');
    }
  };

  // Create empty dashboard
  const handleCreateDashboard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDashName.trim() || isObserver) return;
    setIsCreatingDash(true);

    try {
      const created = await fetchApi('/dashboards', {
        method: 'POST',
        body: JSON.stringify({
          name: newDashName.trim(),
          description: newDashDesc.trim() || undefined,
          visibility: newDashVisibility,
          widgets: [],
        }),
      });
      setNewDashName('');
      setNewDashDesc('');
      await loadData(created.id);
    } catch (err: any) {
      alert(err.message || 'Failed to create dashboard');
    } finally {
      setIsCreatingDash(false);
    }
  };

  // Add Insight widget to active dashboard / tab
  const handleAddInsightToActive = async (insightId: string) => {
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      const createdWidget = await fetchApi(`/dashboards/${activeDashboard.id}/widgets`, {
        method: 'POST',
        body: JSON.stringify({
          insight_id: insightId,
          tab_id: activeTabId || undefined,
          widget_type: 'insight',
          x: 0,
          y: 0,
          w: 6,
          h: 4,
        }),
      });

      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? { ...dash, widgets: [...dash.widgets, createdWidget] }
            : dash
        )
      );
      setShowAddInsightDrawer(false);
    } catch (err: any) {
      alert(err.message || 'Failed to add insight to dashboard');
    }
  };

  // Add Text widget to active dashboard / tab
  const _handleAddTextWidget = async () => {
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      const createdWidget = await fetchApi(`/dashboards/${activeDashboard.id}/widgets`, {
        method: 'POST',
        body: JSON.stringify({
          tab_id: activeTabId || undefined,
          widget_type: 'text',
          title_override: 'Executive Notes',
          x: 0,
          y: 0,
          w: 6,
          h: 4,
          settings: {
            text: '### Key Findings & Analysis\n\nAdd markdown bullet points, executive observations, and highlights here.',
          },
        }),
      });

      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? { ...dash, widgets: [...dash.widgets, createdWidget] }
            : dash
        )
      );
    } catch (err: any) {
      alert(err.message || 'Failed to add text widget');
    }
  };

  // Move widget to another tab
  const handleMoveWidgetToTab = async (widgetId: string, targetTabId: string) => {
    if (!activeDashboard || !canEditActiveDashboard) return;
    try {
      const moved = await fetchApi(`/dashboards/${activeDashboard.id}/widgets/${widgetId}/move`, {
        method: 'POST',
        body: JSON.stringify({ target_tab_id: targetTabId }),
      });
      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? { ...dash, widgets: dash.widgets.map((w) => (w.id === widgetId ? moved : w)) }
            : dash
        )
      );
    } catch (err: any) {
      alert(err.message || 'Failed to move widget');
    }
  };

  // Clone widget to another tab
  const handleCloneWidgetToTab = async (widgetId: string, targetTabId: string) => {
    if (!activeDashboard || !canEditActiveDashboard) return;
    try {
      const cloned = await fetchApi(`/dashboards/${activeDashboard.id}/widgets/${widgetId}/clone`, {
        method: 'POST',
        body: JSON.stringify({ target_tab_id: targetTabId }),
      });
      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? { ...dash, widgets: [...dash.widgets, cloned] }
            : dash
        )
      );
    } catch (err: any) {
      alert(err.message || 'Failed to clone widget');
    }
  };

  // Remove widget from dashboard
  const handleRemoveWidget = async (widgetId: string) => {
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      await fetchApi(`/dashboards/${activeDashboard.id}/widgets/${widgetId}`, {
        method: 'DELETE',
      });
      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? { ...dash, widgets: dash.widgets.filter((w) => w.id !== widgetId) }
            : dash
        )
      );
    } catch (err: any) {
      alert(err.message || 'Failed to remove widget');
    }
  };

  // Duplicate widget
  const handleDuplicateWidget = async (widgetId: string) => {
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      const duplicated = await fetchApi(`/dashboards/${activeDashboard.id}/widgets/${widgetId}/duplicate`, {
        method: 'POST',
      });
      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? { ...dash, widgets: [...dash.widgets, duplicated] }
            : dash
        )
      );
    } catch (err: any) {
      alert(err.message || 'Failed to duplicate widget');
    }
  };

  // Update widget settings (title, chart type override, settings)
  const handleUpdateWidget = async (
    widgetId: string,
    updates: {
      title_override?: string | null;
      chart_type_override?: string | null;
      settings?: Record<string, any>;
    }
  ) => {
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      const updated = await fetchApi(`/dashboards/${activeDashboard.id}/widgets/${widgetId}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
      setDashboards((prev) =>
        prev.map((dash) =>
          dash.id === activeDashboard.id
            ? {
                ...dash,
                widgets: dash.widgets.map((w) => (w.id === widgetId ? { ...w, ...updated } : w)),
              }
            : dash
        )
      );
    } catch (err: any) {
      alert(err.message || 'Failed to update widget');
    }
  };

  // Layout change handler (multi-breakpoint responsive grid)
  const onLayoutChange = (_currentLayout: any[], allLayouts: any) => {
    if (!canEditActiveDashboard) return;
    setCurrentLayouts(allLayouts);
  };

  const handleDragStop = (
    _layout: any[],
    oldItem: any,
    newItem: any,
    _placeholder: any,
    _e: any,
    _element: any
  ) => {
    if (!canEditActiveDashboard) return;
    if (oldItem && newItem && (oldItem.x !== newItem.x || oldItem.y !== newItem.y)) {
      setHasUnsavedLayout(true);
    }
  };

  const handleResizeStop = (
    _layout: any[],
    oldItem: any,
    newItem: any,
    _placeholder: any,
    _e: any,
    _element: any
  ) => {
    if (!canEditActiveDashboard) return;
    if (oldItem && newItem && (oldItem.w !== newItem.w || oldItem.h !== newItem.h)) {
      setHasUnsavedLayout(true);
    }
  };

  // Save layout in-place via PUT
  const handleSaveLayout = async () => {
    if (!activeDashboard || !canEditActiveDashboard) return;
    setIsSavingLayout(true);

    try {
      const activeList =
        currentLayouts[activeBreakpoint] ||
        currentLayouts.lg ||
        currentLayouts.md ||
        currentLayouts.sm ||
        [];
      const payloadWidgets = activeDashboard.widgets.map((w) => {
        const item = activeList.find((l: any) => l.i === w.id) || (currentLayouts.lg || []).find((l: any) => l.i === w.id);
        const itemLayouts: Record<string, any> = {};
        for (const bp of Object.keys(currentLayouts)) {
          const bpItem = (currentLayouts[bp] || []).find((l: any) => l.i === w.id);
          if (bpItem) {
            itemLayouts[bp] = { x: bpItem.x, y: bpItem.y, w: bpItem.w, h: bpItem.h };
          }
        }
        return {
          widget_id: w.id,
          x: item?.x ?? w.x,
          y: item?.y ?? w.y,
          w: item?.w ?? w.w,
          h: item?.h ?? w.h,
          layouts: itemLayouts,
        };
      });

      const updatedDash = await fetchApi(`/dashboards/${activeDashboard.id}/layout`, {
        method: 'PUT',
        body: JSON.stringify({ widgets: payloadWidgets }),
      });

      setDashboards((prev) => prev.map((d) => (d.id === updatedDash.id ? updatedDash : d)));
      setHasUnsavedLayout(false);
      setLayoutVersion((v) => v + 1);
    } catch (err: any) {
      alert(err.message || 'Failed to save layout');
    } finally {
      setIsSavingLayout(false);
    }
  };

  // Discard layout changes
  const handleDiscardLayout = () => {
    if (!activeDashboard) return;
    const lgLayout = activeTabWidgets.map((w) => ({
      i: w.id,
      x: w.x ?? 0,
      y: w.y ?? 0,
      w: w.w || 6,
      h: w.h || 4,
      minW: 2,
      minH: 2,
    }));
    setCurrentLayouts({ lg: lgLayout });
    setHasUnsavedLayout(false);
    setLayoutVersion((v) => v + 1);
  };

  // Save Dashboard Metadata (settings)
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      const updated = await fetchApi(`/dashboards/${activeDashboard.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editDashName.trim(),
          description: editDashDesc.trim() || null,
          visibility: editDashVisibility,
        }),
      });
      setDashboards((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      setShowSettingsModal(false);
    } catch (err: any) {
      alert(err.message || 'Failed to update dashboard settings');
    }
  };

  // Delete Dashboard
  const handleDeleteDashboard = async () => {
    if (!activeDashboard || !canEditActiveDashboard) return;

    try {
      await fetchApi(`/dashboards/${activeDashboard.id}`, {
        method: 'DELETE',
      });
      setShowDeleteModal(false);
      setShowSettingsModal(false);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to delete dashboard');
    }
  };

  // Open settings modal and prefill
  const handleOpenSettings = () => {
    if (!activeDashboard) return;
    setEditDashName(activeDashboard.name);
    setEditDashDesc(activeDashboard.description || '');
    setEditDashVisibility(activeDashboard.visibility || 'private');
    setShowSettingsModal(true);
  };

  // Compute "Data as of <time>" and cached status across active widgets
  const { dataAsOfTime, hasCachedResults } = useMemo(() => {
    const times: number[] = [];
    let cached = false;

    activeTabWidgets.forEach((w) => {
      const info = widgetRunTimes[w.id];
      if (info?.lastRunAt) {
        times.push(new Date(info.lastRunAt).getTime());
        if (info.cached) cached = true;
      }
    });

    if (times.length === 0) {
      return { dataAsOfTime: null, hasCachedResults: false };
    }

    // Oldest result shown on dashboard determines the freshness indicator
    const oldestMs = Math.min(...times);
    return {
      dataAsOfTime: new Date(oldestMs).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }),
      hasCachedResults: cached,
    };
  }, [activeTabWidgets, widgetRunTimes]);

  const handleRunFinished = useCallback(
    (widgetId: string, runInfo: { lastRunAt: string | null; cached: boolean }) => {
      setWidgetRunTimes((prev) => ({ ...prev, [widgetId]: runInfo }));
    },
    []
  );

  const handleRefreshAll = () => {
    setForceRefreshCounter((prev) => prev + 1);
  };

  // Distinct sources for insight drawer filter
  const availableSources = useMemo(() => {
    const map = new Map<string, string>();
    insights.forEach((i) => {
      if (i.source_id) {
        map.set(i.source_id, i.source_name || `Source ${i.source_id.slice(0, 8)}`);
      }
    });
    return Array.from(map.entries());
  }, [insights]);

  const filteredInsights = useMemo(() => {
    return insights.filter((i) => {
      const matchSearch =
        !insightSearch ||
        (i.name || '').toLowerCase().includes(insightSearch.toLowerCase()) ||
        (i.query || '').toLowerCase().includes(insightSearch.toLowerCase());
      const matchSource = !insightSourceFilter || i.source_id === insightSourceFilter;
      return matchSearch && matchSource;
    });
  }, [insights, insightSearch, insightSourceFilter]);

  const dashboardTabs = activeDashboard?.tabs || [];
  const showTabBar = dashboardTabs.length >= 2;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', padding: '0.75rem 1.25rem', boxSizing: 'border-box', overflowY: 'auto' }}>
      {loading ? (
        <div className="flex items-center justify-center h-full text-muted">
          <div className="skeleton" style={{ width: '100%', height: '100%', borderRadius: 'var(--radius)' }} />
        </div>
      ) : dashboards.length === 0 ? (
        /* Empty Dashboard State (no dashboards in tenant) */
        <div className="flex items-center justify-center h-full text-muted flex-col gap-3" style={{ minHeight: '350px' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(99, 102, 241, 0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <LayoutDashboard size={32} />
          </div>
          <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>No Dashboards Yet</h3>
          <p style={{ margin: 0, fontSize: '0.875rem' }}>Create your first dashboard to begin visualizing metrics and insights.</p>
          {!isObserver && (
            <button
              className="btn-primary"
              onClick={() => setShowCreateModal(true)}
              style={{ marginTop: '0.5rem', padding: '0.45rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            >
              <Plus size={15} /> Create Dashboard
            </button>
          )}
        </div>
      ) : !activeDashboard ? (
        /* Edge case: dashboards exist but none active */
        <div className="flex items-center justify-center h-full text-muted flex-col gap-3" style={{ minHeight: '350px' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(99, 102, 241, 0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <LayoutDashboard size={32} />
          </div>
          <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>No Dashboard Selected</h3>
          <p style={{ margin: 0, fontSize: '0.875rem' }}>Select an existing dashboard from the dropdown above or create a new one.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          {/* Unsaved Changes Banner */}
          {hasUnsavedLayout && (
            <div
              style={{
                background: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid var(--primary)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.5rem 1rem',
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.85rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', fontWeight: 600 }}>
                <AlertCircle size={16} />
                <span>You have unsaved layout changes on this tab.</span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  className="btn-secondary"
                  onClick={handleDiscardLayout}
                  disabled={isSavingLayout}
                  style={{ padding: '0.25rem 0.65rem', fontSize: '0.78rem' }}
                >
                  <RotateCcw size={12} style={{ marginRight: '0.25rem' }} /> Discard
                </button>
                <button
                  className="btn-primary"
                  onClick={handleSaveLayout}
                  disabled={isSavingLayout}
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.78rem' }}
                >
                  <Save size={12} style={{ marginRight: '0.25rem' }} /> {isSavingLayout ? 'Saving...' : 'Save Layout'}
                </button>
              </div>
            </div>
          )}

          {/* Clean Top Header Bar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.75rem',
              marginBottom: '0.85rem',
              paddingBottom: '0.75rem',
              borderBottom: '1px solid var(--border-color)',
            }}
          >
            {/* Left: Title with Dropdown Selector, Badges, Freshness, Description */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                <div style={{ position: 'relative' }} ref={dashDropdownRef}>
                  <button
                    type="button"
                    aria-label="Select Dashboard"
                    onClick={() => setIsDashDropdownOpen((prev) => !prev)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      margin: 0,
                      outline: 'none',
                      boxShadow: 'none',
                      cursor: 'pointer',
                      color: 'var(--text-main)',
                    }}
                  >
                    <h1 style={{ fontSize: '1.35rem', margin: 0, fontWeight: 700, color: 'inherit' }}>
                      {activeDashboard.name}
                    </h1>
                    <ChevronDown
                      size={18}
                      style={{
                        color: 'var(--text-muted)',
                        transition: 'transform 0.2s',
                        transform: isDashDropdownOpen ? 'rotate(180deg)' : 'none',
                      }}
                    />
                  </button>

                  {/* Dropdown Menu */}
                  {isDashDropdownOpen && (
                    <div
                      role="listbox"
                      style={{
                        position: 'absolute',
                        top: 'calc(100% + 4px)',
                        left: 0,
                        zIndex: 1000,
                        minWidth: '220px',
                        maxWidth: '320px',
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md, 8px)',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
                        padding: '0.35rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                        maxHeight: '300px',
                        overflowY: 'auto',
                      }}
                    >
                      {dashboards.map((d) => {
                        const isCurrent = d.id === activeDashboard.id;
                        return (
                          <button
                            key={d.id}
                            role="option"
                            aria-selected={isCurrent}
                            onClick={() => handleSelectDashboard(d.id)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              gap: '0.75rem',
                              width: '100%',
                              padding: '0.45rem 0.65rem',
                              fontSize: '0.825rem',
                              fontWeight: isCurrent ? 600 : 400,
                              background: isCurrent ? 'var(--primary-light, rgba(59, 130, 246, 0.1))' : 'transparent',
                              color: isCurrent ? 'var(--primary, #2563eb)' : 'var(--text-main)',
                              border: 'none',
                              borderRadius: 'var(--radius-sm, 4px)',
                              cursor: 'pointer',
                              textAlign: 'left',
                            }}
                            onMouseEnter={(e) => {
                              if (!isCurrent) e.currentTarget.style.backgroundColor = 'var(--bg-hover, rgba(148, 163, 184, 0.08))';
                            }}
                            onMouseLeave={(e) => {
                              if (!isCurrent) e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                          >
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {d.name}
                            </span>
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.2rem',
                                fontSize: '0.68rem',
                                color: d.visibility === 'published' ? '#10b981' : 'var(--text-muted)',
                                flexShrink: 0,
                              }}
                            >
                              {d.visibility === 'published' ? <Globe size={10} /> : <Lock size={10} />}
                              {d.visibility === 'published' ? 'Published' : 'Private'}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                <span
                  className="badge"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                    fontSize: '0.72rem',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '12px',
                    background: activeDashboard.visibility === 'published' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(148, 163, 184, 0.15)',
                    color: activeDashboard.visibility === 'published' ? '#10b981' : 'var(--text-muted)',
                    border: '1px solid currentColor',
                  }}
                >
                  {activeDashboard.visibility === 'published' ? <Globe size={11} /> : <Lock size={11} />}
                  {activeDashboard.visibility === 'published' ? 'Published' : 'Private'}
                </span>

                {/* Freshness Indicator: Data as of <time> */}
                {dataAsOfTime && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                      padding: '0.15rem 0.5rem',
                      borderRadius: '6px',
                      background: 'rgba(148, 163, 184, 0.08)',
                    }}
                  >
                    <Clock size={12} />
                    Data as of {dataAsOfTime}
                    {hasCachedResults && (
                      <span style={{ color: '#d97706', fontWeight: 600, fontSize: '0.7rem' }}>(cached)</span>
                    )}
                  </span>
                )}
              </div>

              {activeDashboard.description && (
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {activeDashboard.description}
                </p>
              )}
            </div>

            {/* Right: Actions and "New Dashboard" Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              {canEditActiveDashboard && (
                <>
                  <button
                    className="btn-secondary"
                    onClick={() => setShowAddInsightDrawer(true)}
                    style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem' }}
                  >Add Insight
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={handleAddTab}
                    style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem' }}
                    title="Add a new dashboard tab"
                  >Add Tab
                  </button>
                  <button
                    className="btn-ghost"
                    title="Dashboard Settings"
                    onClick={handleOpenSettings}
                    style={{ padding: '0.35rem' }}
                  >
                    <Settings size={16} />
                  </button>
                </>
              )}

              <button
                className="btn-ghost"
                title="Refresh Data (Bypasses Cache)"
                onClick={handleRefreshAll}
                style={{ padding: '0.35rem' }}
              >
                <RefreshCw size={16} />
              </button>

              {/* New Dashboard Button */}
              {!isObserver && (
                <button
                  className="btn-primary"
                  onClick={() => setShowCreateModal(true)}
                  style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                  title="Create a new dashboard"
                >New Dashboard
                </button>
              )}
            </div>
          </div>

            {/* Collapsible Overview Executive Summary Section */}
            {(activeDashboard.overview_summary || canEditActiveDashboard) && (
              <div
                style={{
                  marginBottom: '1rem',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius)',
                  background: 'var(--bg-card)',
                  overflow: 'hidden',
                  transition: 'box-shadow 0.2s',
                }}
              >
                <div
                  style={{
                    padding: '0.5rem 0.9rem',
                    background: 'var(--bg-dark)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  onClick={toggleOverviewCollapsed}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Sparkles size={15} style={{ color: 'var(--primary)' }} />
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
                      Overview Summary
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {canEditActiveDashboard && (
                      <button
                        className="btn-ghost"
                        style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', color: 'var(--primary)' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setOverviewDraft(activeDashboard.overview_summary || '');
                          setShowOverviewModal(true);
                        }}
                      >
                        <Edit2 size={12} style={{ marginRight: '0.25rem' }} /> Edit Summary
                      </button>
                    )}
                    <button className="btn-ghost" style={{ padding: '0.2rem' }}>
                      {overviewCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                    </button>
                  </div>
                </div>

                {!overviewCollapsed && (
                  <div style={{ padding: '0.85rem 1rem', fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--text-main)' }}>
                    {activeDashboard.overview_summary ? (
                      <ReactMarkdown
                        urlTransform={safeUrlTransform}
                        components={{
                          a: ({ node: _node, ...props }) => (
                            <a
                              {...props}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: 'var(--primary)', textDecoration: 'underline' }}
                            />
                          ),
                        }}
                      >
                        {activeDashboard.overview_summary}
                      </ReactMarkdown>
                    ) : (
                      <p style={{ margin: 0, color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.85rem' }}>
                        No overview summary provided yet. Click "Edit Summary" to add an executive brief.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Dashboard Tabs Bar (Shown only when dashboard has >= 2 tabs) */}
            {showTabBar && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  borderBottom: '1px solid var(--border-color)',
                  marginBottom: '1rem',
                  overflowX: 'auto',
                  flexShrink: 0,
                  paddingBottom: '2px',
                }}
              >
                {dashboardTabs.map((tab, idx) => {
                  const isActive = activeTabId === tab.id;
                  const isRenaming = editingTabId === tab.id;

                  return (
                    <div
                      key={tab.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        padding: '0.45rem 0.85rem',
                        borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                        background: isActive ? 'rgba(99, 102, 241, 0.12)' : 'transparent',
                        color: isActive ? 'var(--primary)' : 'var(--text-muted)',
                        borderBottom: isActive ? '2px solid var(--primary)' : '2px solid transparent',
                        fontWeight: isActive ? 600 : 500,
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                      onClick={() => handleSelectTab(tab.id)}
                    >
                      {isRenaming ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }} onClick={(e) => e.stopPropagation()}>
                          <input
                            type="text"
                            value={tabRenameDraft}
                            onChange={(e) => setTabRenameDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveRenameTab(tab.id);
                              if (e.key === 'Escape') setEditingTabId(null);
                            }}
                            autoFocus
                            style={{ padding: '0.15rem 0.35rem', fontSize: '0.8rem', width: '110px' }}
                          />
                          <button
                            className="btn-ghost"
                            onClick={() => handleSaveRenameTab(tab.id)}
                            style={{ padding: '0.15rem', color: 'var(--primary)' }}
                          >
                            <Check size={12} />
                          </button>
                          <button
                            className="btn-ghost"
                            onClick={() => setEditingTabId(null)}
                            style={{ padding: '0.15rem' }}
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span>{tab.name}</span>
                          {canEditActiveDashboard && (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '2px', opacity: isActive ? 1 : 0.4 }} onClick={(e) => e.stopPropagation()}>
                              <button
                                className="btn-ghost"
                                style={{ padding: '0.1rem', color: 'var(--text-muted)' }}
                                onClick={() => {
                                  setTabRenameDraft(tab.name);
                                  setEditingTabId(tab.id);
                                }}
                                title="Rename Tab"
                              >
                                <Edit2 size={11} />
                              </button>
                              {idx > 0 && (
                                <button
                                  className="btn-ghost"
                                  style={{ padding: '0.1rem', color: 'var(--text-muted)' }}
                                  onClick={() => handleMoveTab(tab.id, 'left')}
                                  title="Move Left"
                                >
                                  <ChevronLeft size={11} />
                                </button>
                              )}
                              {idx < dashboardTabs.length - 1 && (
                                <button
                                  className="btn-ghost"
                                  style={{ padding: '0.1rem', color: 'var(--text-muted)' }}
                                  onClick={() => handleMoveTab(tab.id, 'right')}
                                  title="Move Right"
                                >
                                  <ChevronRight size={11} />
                                </button>
                              )}
                              {dashboardTabs.length > 1 && (
                                <button
                                  className="btn-ghost text-error"
                                  style={{ padding: '0.1rem' }}
                                  onClick={() => {
                                    setDeleteTabModal(tab);
                                    const other = dashboardTabs.find((t) => t.id !== tab.id);
                                    setDeleteTabMoveTarget(other?.id || '');
                                  }}
                                  title="Delete Tab"
                                >
                                  <Trash2 size={11} />
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}

                {canEditActiveDashboard && (
                  <button
                    className="btn-ghost"
                    onClick={handleAddTab}
                    style={{ padding: '0.35rem 0.6rem', fontSize: '0.8rem', color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                    title="Add new tab"
                  >
                    <Plus size={13} /> Add Tab
                  </button>
                )}
              </div>
            )}

            {/* Grid Area */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {activeTabWidgets.length === 0 ? (
                /* Empty Tab / Dashboard State */
                <div
                  className="flex items-center justify-center text-muted"
                  style={{
                    height: '320px',
                    border: '1px dashed var(--border-color)',
                    borderRadius: 'var(--radius)',
                    background: 'var(--bg-card)',
                  }}
                >
                  <div className="text-center">
                    <AlertCircle size={32} style={{ margin: '0 auto 0.75rem', opacity: 0.5 }} />
                    <p style={{ margin: 0, fontWeight: 500, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                      This tab has no widgets
                    </p>
                    {canEditActiveDashboard ? (
                      <>
                        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                          Add insights to this tab.
                        </p>
                        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginTop: '1rem' }}>
                          <button
                            className="btn-primary"
                            onClick={() => setShowAddInsightDrawer(true)}
                            style={{ padding: '0.45rem 1rem', fontSize: '0.85rem' }}
                          >Add Insight
                          </button>
                        </div>
                      </>
                    ) : (
                      <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                        No widgets published to this tab yet.
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                /* Responsive Grid Layout */
                <div ref={gridContainerRef} style={{ width: '100%', minHeight: '100%' }}>
                  {/* @ts-ignore */}
                  <ResponsiveGridLayout
                    key={`grid-${activeDashboard.id}-${activeTabId || 'all'}-${layoutVersion}`}
                    width={gridWidth}
                    className="layout"
                    layouts={currentLayouts}
                    breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                    cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                    rowHeight={80}
                    dragConfig={{
                      enabled: canEditActiveDashboard,
                      handle: '.drag-handle',
                      cancel: 'button, input, select, textarea, a, .no-drag',
                    }}
                    resizeConfig={{
                      enabled: canEditActiveDashboard,
                      handles: ['s', 'w', 'e', 'n', 'sw', 'nw', 'se', 'ne'],
                    }}
                    onBreakpointChange={(newBp: string) => setActiveBreakpoint(newBp)}
                    onLayoutChange={onLayoutChange}
                    onDragStop={handleDragStop}
                    onResizeStop={handleResizeStop}
                    margin={[16, 16]}
                  >
                    {activeTabWidgets.map((w) => {
                      const isFullScreen = fullScreenWidgetId === w.id;
                      return (
                        <div
                          key={w.id}
                          data-grid={{
                            i: w.id,
                            x: w.x ?? 0,
                            y: w.y ?? 0,
                            w: w.w || 6,
                            h: w.h || 4,
                            minW: 2,
                            minH: 2,
                          }}
                        >
                          <DashboardWidgetCard
                            widget={w}
                            isEditMode={canEditActiveDashboard}
                            canEdit={canEditActiveDashboard}
                            isAdmin={isAdmin}
                            tabs={dashboardTabs}
                            isFullScreen={isFullScreen}
                            onToggleFullScreen={() => setFullScreenWidgetId(isFullScreen ? null : w.id)}
                            onRemove={() => handleRemoveWidget(w.id)}
                            onDuplicate={() => handleDuplicateWidget(w.id)}
                            onMoveToTab={(targetTabId) => handleMoveWidgetToTab(w.id, targetTabId)}
                            onCloneToTab={(targetTabId) => handleCloneWidgetToTab(w.id, targetTabId)}
                            onUpdateWidget={(updates) => handleUpdateWidget(w.id, updates)}
                            onRunFinished={handleRunFinished}
                            forceRefreshCounter={forceRefreshCounter}
                          />
                        </div>
                      );
                    })}
                  </ResponsiveGridLayout>
                </div>
              )}
            </div>

            {/* Fullscreen Overlay Backdrop */}
            {fullScreenWidgetId && (
              <div
                style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 9998 }}
                onClick={() => setFullScreenWidgetId(null)}
              />
            )}
          </div>
        )}

      {/* Add Insight Drawer / Modal */}
      {showAddInsightDrawer && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            justifyContent: 'flex-end',
            zIndex: 1000,
          }}
          onClick={() => setShowAddInsightDrawer(false)}
        >
          <div
            style={{
              width: '420px',
              maxWidth: '90vw',
              height: '100%',
              background: 'var(--bg-card)',
              borderLeft: '1px solid var(--border-color)',
              boxShadow: '-10px 0 25px rgba(0,0,0,0.25)',
              display: 'flex',
              flexDirection: 'column',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{ padding: '1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Bookmark size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Add Insights to Dashboard</h3>
              </div>
              <button className="btn-ghost" onClick={() => setShowAddInsightDrawer(false)} style={{ padding: '0.25rem' }}>
                <X size={16} />
              </button>
            </div>

            {/* Search & Filters */}
            <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search insights..."
                  value={insightSearch}
                  onChange={(e) => setInsightSearch(e.target.value)}
                  style={{ width: '100%', padding: '0.45rem 0.5rem 0.45rem 2rem', fontSize: '0.85rem' }}
                />
              </div>

              {availableSources.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Filter size={13} style={{ color: 'var(--text-muted)' }} />
                  <select
                    value={insightSourceFilter}
                    onChange={(e) => setInsightSourceFilter(e.target.value)}
                    style={{ flex: 1, padding: '0.35rem 0.5rem', fontSize: '0.8rem' }}
                  >
                    <option value="">All Data Sources</option>
                    {availableSources.map(([sId, sName]) => (
                      <option key={sId} value={sId}>
                        {sName}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Insight Items List */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {filteredInsights.map((ins) => (
                <div
                  key={ins.id}
                  style={{
                    padding: '0.85rem',
                    background: 'var(--bg-dark)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.4rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-main)' }}>
                      {ins.name}
                    </span>
                    <button
                      className="btn-primary"
                      onClick={() => handleAddInsightToActive(ins.id)}
                      style={{ padding: '0.25rem 0.65rem', fontSize: '0.75rem', flexShrink: 0 }}
                    >
                      <Plus size={12} style={{ marginRight: '0.2rem' }} /> Add
                    </button>
                  </div>
                  {ins.description && (
                    <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {ins.description}
                    </p>
                  )}
                  <code
                    style={{
                      fontSize: '0.72rem',
                      color: 'var(--text-muted)',
                      background: 'rgba(0,0,0,0.2)',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {ins.query}
                  </code>
                </div>
              ))}
              {filteredInsights.length === 0 && (
                <div className="text-muted text-sm text-center py-6">No matching insights found.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal (Rename, Visibility, Delete) */}
      {showSettingsModal && activeDashboard && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
          onClick={() => setShowSettingsModal(false)}
        >
          <div
            className="modal-content"
            style={{ width: '450px', maxWidth: '90vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.5rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>Dashboard Settings</h3>
              <button className="btn-ghost" onClick={() => setShowSettingsModal(false)} style={{ padding: '0.25rem' }}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Dashboard Name
                </label>
                <input
                  type="text"
                  value={editDashName}
                  onChange={(e) => setEditDashName(e.target.value)}
                  required
                  style={{ width: '100%', padding: '0.5rem', fontSize: '0.875rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Description
                </label>
                <textarea
                  value={editDashDesc}
                  onChange={(e) => setEditDashDesc(e.target.value)}
                  rows={2}
                  style={{ width: '100%', padding: '0.5rem', fontSize: '0.875rem', resize: 'vertical' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Visibility
                </label>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="edit-vis"
                      checked={editDashVisibility === 'private'}
                      onChange={() => setEditDashVisibility('private')}
                    />
                    <span>Private (Only you)</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="edit-vis"
                      checked={editDashVisibility === 'published'}
                      onChange={() => setEditDashVisibility('published')}
                    />
                    <span>Published (Tenant viewable)</span>
                  </label>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                <button
                  type="button"
                  className="btn-ghost text-error"
                  onClick={() => setShowDeleteModal(true)}
                  style={{ padding: '0.45rem 0.75rem', fontSize: '0.85rem' }}
                >
                  <Trash2 size={14} style={{ marginRight: '0.35rem' }} /> Delete Dashboard
                </button>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button type="button" className="btn-secondary" onClick={() => setShowSettingsModal(false)} style={{ padding: '0.45rem 0.85rem' }}>
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary" style={{ padding: '0.45rem 1rem' }}>
                    Save
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Dashboard Confirmation Modal */}
      {showDeleteModal && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1010 }}
          onClick={() => setShowDeleteModal(false)}
        >
          <div
            className="modal-content"
            style={{ width: '400px', maxWidth: '90vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.5rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ef4444', marginBottom: '0.75rem' }}>
              <AlertCircle size={20} />
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Delete Dashboard?</h3>
            </div>
            <p style={{ margin: '0 0 1.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Are you sure you want to delete <strong>"{activeDashboard?.name}"</strong>? This will remove all widgets on this dashboard. Reusable insights in your library will remain intact.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={() => setShowDeleteModal(false)} style={{ padding: '0.45rem 0.85rem' }}>
                Cancel
              </button>
              <button
                onClick={handleDeleteDashboard}
                style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', padding: '0.45rem 1rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.85rem' }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Overview Edit Modal */}
      {showOverviewModal && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }}
          onClick={() => setShowOverviewModal(false)}
        >
          <div
            className="modal-content"
            style={{ width: '600px', maxWidth: '92vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.25rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Edit Executive Overview Summary</h3>
              </div>
              <button className="btn-ghost" onClick={() => setShowOverviewModal(false)} style={{ padding: '0.2rem' }}>
                <X size={16} />
              </button>
            </div>

            <p style={{ margin: '0 0 0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Write executive takeaways and contextual narrative. Supports standard Markdown (max 10,000 characters).
            </p>

            <textarea
              value={overviewDraft}
              onChange={(e) => setOverviewDraft(e.target.value)}
              rows={10}
              maxLength={10000}
              placeholder="### Q3 Executive Takeaways&#10;- Revenue grew +18% QoQ driven by Enterprise accounts.&#10;- Churn risk concentrates in lower-tier accounts with SLA breaches."
              style={{ width: '100%', padding: '0.65rem', fontSize: '0.85rem', fontFamily: 'monospace', resize: 'vertical' }}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {overviewDraft.length} / 10,000 characters
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn-secondary" onClick={() => setShowOverviewModal(false)} style={{ padding: '0.4rem 0.8rem' }}>
                  Cancel
                </button>
                <button className="btn-primary" onClick={handleSaveOverviewSummary} style={{ padding: '0.4rem 1rem' }}>
                  Save Summary
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Tab Confirmation Modal */}
      {deleteTabModal && (
        <div
          className="modal-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }}
          onClick={() => setDeleteTabModal(null)}
        >
          <div
            className="modal-content"
            style={{ width: '450px', maxWidth: '92vw', background: 'var(--bg-card)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)', padding: '1.25rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ef4444', marginBottom: '0.75rem' }}>
              <AlertCircle size={20} />
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Delete Tab "{deleteTabModal.name}"?</h3>
            </div>

            <p style={{ margin: '0 0 1rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Choose whether to move any existing widgets on this tab to another tab before deleting:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                <input
                  type="radio"
                  name="tab-delete-action"
                  checked={Boolean(deleteTabMoveTarget)}
                  onChange={() => {
                    const other = dashboardTabs.find((t) => t.id !== deleteTabModal.id);
                    setDeleteTabMoveTarget(other?.id || '');
                  }}
                  style={{ marginTop: '0.2rem' }}
                />
                <div style={{ flex: 1 }}>
                  <span>Move widgets to:</span>
                  <select
                    value={deleteTabMoveTarget}
                    onChange={(e) => setDeleteTabMoveTarget(e.target.value)}
                    disabled={!deleteTabMoveTarget}
                    style={{ width: '100%', padding: '0.35rem', fontSize: '0.8rem', marginTop: '0.35rem' }}
                  >
                    {dashboardTabs
                      .filter((t) => t.id !== deleteTabModal.id)
                      .map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                  </select>
                </div>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                <input
                  type="radio"
                  name="tab-delete-action"
                  checked={!deleteTabMoveTarget}
                  onChange={() => setDeleteTabMoveTarget('')}
                />
                <span>Delete tab and all widgets on it</span>
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={() => setDeleteTabModal(null)} style={{ padding: '0.4rem 0.8rem' }}>
                Cancel
              </button>
              <button
                onClick={handleDeleteTab}
                style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', padding: '0.4rem 1rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.85rem' }}
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Dashboard Modal */}
      {showCreateModal && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowCreateModal(false)}
        >
          <div
            className="modal-content"
            style={{
              width: '460px',
              maxWidth: '92vw',
              background: 'var(--bg-card)',
              borderRadius: 'var(--radius)',
              border: '1px solid var(--border-color)',
              padding: '1.5rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                New Dashboard
              </h3>
              <button className="btn-ghost" onClick={() => setShowCreateModal(false)} style={{ padding: '0.25rem' }}>
                <X size={16} />
              </button>
            </div>

            <form
              onSubmit={async (e) => {
                await handleCreateDashboard(e);
                setShowCreateModal(false);
              }}
              style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
            >
              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Dashboard Name *
                </label>
                <input
                  type="text"
                  value={newDashName}
                  onChange={(e) => setNewDashName(e.target.value)}
                  required
                  placeholder="e.g. Executive Performance Overview"
                  disabled={isCreatingDash}
                  style={{ width: '100%', padding: '0.5rem', fontSize: '0.875rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Description (Optional)
                </label>
                <textarea
                  value={newDashDesc}
                  onChange={(e) => setNewDashDesc(e.target.value)}
                  rows={2}
                  placeholder="Brief summary of this dashboard's purpose"
                  disabled={isCreatingDash}
                  style={{ width: '100%', padding: '0.5rem', fontSize: '0.875rem', resize: 'vertical' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Visibility
                </label>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="modal-new-vis"
                      checked={newDashVisibility === 'private'}
                      onChange={() => setNewDashVisibility('private')}
                    />
                    <span>Private (Only you)</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="modal-new-vis"
                      checked={newDashVisibility === 'published'}
                      onChange={() => setNewDashVisibility('published')}
                    />
                    <span>Published (Tenant viewable)</span>
                  </label>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                  style={{ padding: '0.45rem 0.85rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={isCreatingDash || !newDashName.trim()}
                  style={{ padding: '0.45rem 1rem' }}
                >
                  {isCreatingDash ? 'Creating...' : 'Create Dashboard'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
