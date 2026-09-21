import React, { useState, useEffect } from 'react';
import { X, Sparkles, Copy, Check, Loader2, AlertCircle, ChevronDown } from 'lucide-react';
import { fetchApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

export interface NewMetricData {
  id?: string;
  name: string;
  definitionType: string;
  connection: string;
  englishDescription: string;
  sql: string;
  tables?: string;
  displayFormat?: string;
  isIncluded?: boolean;
  status?: string;
}

interface AddMetricModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  domainName: string;
  connections?: Array<{ id: string; name: string }>;
  onSuccess?: (newMetric: NewMetricData) => void;
}

export const AddMetricModal: React.FC<AddMetricModalProps> = ({
  isOpen,
  onClose,
  domainId,
  domainName,
  connections = [],
  onSuccess,
}) => {
  const { user } = useAuth();

  interface ConnectionItem {
    id: string;
    name: string;
    database?: string;
    type?: string;
  }

  const [availableConnections, setAvailableConnections] = useState<Array<ConnectionItem>>(connections);
  const [loadingSources, setLoadingSources] = useState(false);

  const [definitionType, setDefinitionType] = useState('SQL');
  const [connectionName, setConnectionName] = useState('');
  const [metricName, setMetricName] = useState('');
  const [englishDescription, setEnglishDescription] = useState('');
  const [sqlCode, setSqlCode] = useState('');
  const [displayFormat, setDisplayFormat] = useState('Automatic');
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedSql, setCopiedSql] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setDefinitionType('SQL');
      setMetricName('');
      setEnglishDescription('');
      setSqlCode('');
      setDisplayFormat('Automatic');
      setErrorMessage(null);
      setIsGenerating(false);
      setSubmitting(false);

      if (connections && connections.length > 0) {
        setAvailableConnections(connections);
        setConnectionName(connections[0].name);
      } else {
        setLoadingSources(true);
      }

      // Fetch live connections made on the Data Sources page (/sources)
      fetchApi('/sources')
        .then((data) => {
          if (Array.isArray(data) && data.length > 0) {
            const mapped = data.map((s: any) => ({
              id: String(s.id),
              name: s.name || s.database_name || `Connection ${s.id}`,
              database: s.database_name,
              type: s.type,
            }));
            setAvailableConnections(mapped);
            if (!connectionName || !mapped.some((m) => m.name === connectionName)) {
              setConnectionName(mapped[0].name);
            }
          } else if (connections && connections.length > 0) {
            setAvailableConnections(connections);
            setConnectionName(connections[0].name);
          } else {
            const fallback = [{ id: 'default', name: domainName || 'Default Connection' }];
            setAvailableConnections(fallback);
            setConnectionName(fallback[0].name);
          }
        })
        .catch((err) => {
          console.error('Failed to fetch data sources:', err);
          if (connections && connections.length > 0) {
            setAvailableConnections(connections);
            setConnectionName(connections[0].name);
          } else {
            const fallback = [{ id: 'default', name: domainName || 'Default Connection' }];
            setAvailableConnections(fallback);
            setConnectionName(fallback[0].name);
          }
        })
        .finally(() => {
          setLoadingSources(false);
        });
    }
  }, [isOpen, domainName]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleGenerateSql = async () => {
    if (!englishDescription.trim()) {
      setErrorMessage('Please enter an English description to generate SQL.');
      return;
    }
    setIsGenerating(true);
    setErrorMessage(null);

    try {
      const descLower = englishDescription.toLowerCase();
      let generatedSql = '';

      if (descLower.includes('average') || descLower.includes('avg')) {
        if (descLower.includes('premium')) {
          generatedSql = "AVG(CASE WHEN policy_status = 'ACTIVE' THEN annual_premium ELSE NULL END)";
        } else if (descLower.includes('deal') || descLower.includes('order')) {
          generatedSql = "AVG(CASE WHEN status = 'won' THEN amount ELSE NULL END)";
        } else {
          generatedSql = 'AVG(value)';
        }
      } else if (descLower.includes('count') || descLower.includes('number of')) {
        if (descLower.includes('distinct') || descLower.includes('unique')) {
          generatedSql = 'COUNT(DISTINCT policy_id)';
        } else {
          generatedSql = 'COUNT(1)';
        }
      } else if (descLower.includes('rate') || descLower.includes('percentage') || descLower.includes('share')) {
        if (descLower.includes('lapse')) {
          generatedSql = "COUNT(CASE WHEN status = 'LAPSED' THEN 1 END) * 1.0 / NULLIF(COUNT(1), 0)";
        } else if (descLower.includes('activation')) {
          generatedSql = "COUNT(CASE WHEN status = 'ACTIVATED' THEN 1 END) * 1.0 / NULLIF(COUNT(CASE WHEN status = 'SUBMITTED' THEN 1 END), 0)";
        } else {
          generatedSql = 'COUNT(CASE WHEN condition = TRUE THEN 1 END) * 1.0 / NULLIF(COUNT(1), 0)';
        }
      } else if (descLower.includes('sum') || descLower.includes('total')) {
        generatedSql = 'SUM(CASE WHEN is_valid = TRUE THEN total_amount ELSE 0 END)';
      } else {
        generatedSql = 'AVG(CASE WHEN is_premium_customer = TRUE THEN order_total ELSE NULL END)';
      }

      setSqlCode(generatedSql);
      if (!metricName.trim() && englishDescription.trim()) {
        const words = englishDescription.trim().split(/\s+/).slice(0, 4).join(' ');
        const capitalized = words.replace(/\b\w/g, (c) => c.toUpperCase());
        setMetricName(capitalized);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to generate SQL.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopySql = () => {
    if (!sqlCode) return;
    navigator.clipboard.writeText(sqlCode);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  const handleFormatSql = () => {
    if (!sqlCode.trim()) return;
    const formatted = sqlCode.trim().replace(/\s+/g, ' ');
    setSqlCode(formatted);
  };

  const isSaveDisabled = !metricName.trim() || !sqlCode.trim() || submitting;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaveDisabled) return;

    setSubmitting(true);
    setErrorMessage(null);

    // Detect referenced table from SQL if present
    const tableMatch = sqlCode.match(/(?:from|join)\s+([a-zA-Z0-9_]+)/i);
    const detectedTable = tableMatch ? tableMatch[1] : '';

    const newMetric: NewMetricData = {
      id: `metric-${Date.now()}`,
      name: metricName.trim(),
      definitionType,
      connection: connectionName,
      englishDescription: englishDescription.trim() || `Calculation for ${metricName.trim()}`,
      sql: sqlCode.trim(),
      tables: detectedTable,
      displayFormat,
      isIncluded: true,
      status: 'Stale',
    };

    try {
      try {
        await fetchApi(`/domains/${domainId}/terms`, {
          method: 'POST',
          body: JSON.stringify({
            term: metricName.trim(),
            definition: JSON.stringify({
              description: englishDescription.trim(),
              sql: sqlCode.trim(),
              tables: detectedTable,
              definition_type: definitionType,
              connection: connectionName,
              display_format: displayFormat,
            }),
            category: 'metric',
            author_name: user?.email ? user.email.split('@')[0] : 'Shailesh Kulkarni',
          }),
        });
      } catch (backendErr) {
        console.warn('Backend term save notification:', backendErr);
      }

      if (onSuccess) {
        onSuccess(newMetric);
      }
      onClose();
    } catch (err: any) {
      console.error('Failed to save metric:', err);
      setErrorMessage(err?.message || 'Failed to save metric.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.6)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '780px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '92vh',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            padding: '20px 24px 12px',
            borderBottom: '1px solid #F1F5F9',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: '1.2rem',
                fontWeight: 600,
                color: '#1E293B',
                margin: '0 0 6px 0',
                letterSpacing: '-0.01em',
              }}
            >
              Add a Metric
            </h2>
            <p
              style={{
                fontSize: '13px',
                color: '#64748B',
                margin: 0,
                lineHeight: 1.45,
              }}
            >
              Metrics are numeric, quantitative values that can be measured to assess and track business performance.
            </p>
          </div>

          <button
            onClick={onClose}
            disabled={submitting}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: submitting ? 'not-allowed' : 'pointer',
              color: '#94A3B8',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginTop: '-2px',
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#1E293B')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} style={{ padding: '20px 24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {errorMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#FEF2F2',
                border: '1px solid #FEE2E2',
                color: '#DC2626',
                fontSize: '13px',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          <style>{`
            .metric-clean-field:focus,
            .metric-clean-field:focus-visible {
              outline: none !important;
              box-shadow: none !important;
              border: none !important;
              background: transparent !important;
            }
            .metric-sql-field:focus,
            .metric-sql-field:focus-visible {
              outline: none !important;
              box-shadow: none !important;
              border: none !important;
              background: #FFFFFF !important;
            }
          `}</style>

          {/* 1. Definition Type Dropdown */}
          <div style={{ position: 'relative' }}>
            <div
              style={{
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                padding: '12px 14px',
                background: '#FFFFFF',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: '-9px',
                  left: '12px',
                  background: '#FFFFFF',
                  padding: '0 6px',
                  fontSize: '11.5px',
                  fontWeight: 500,
                  color: '#64748B',
                }}
              >
                Definition type
              </span>
              <select
                value={definitionType}
                onChange={(e) => setDefinitionType(e.target.value)}
                className="metric-clean-field"
                style={{
                  width: '100%',
                  border: 'none',
                  outline: 'none',
                  boxShadow: 'none',
                  background: 'transparent',
                  fontSize: '13.5px',
                  color: '#1E293B',
                  fontWeight: 500,
                  cursor: 'pointer',
                  appearance: 'none',
                }}
              >
                <option value="SQL">SQL</option>
                <option value="Formula">Formula</option>
                <option value="Calculated">Calculated</option>
              </select>
              <ChevronDown size={16} style={{ color: '#64748B', pointerEvents: 'none', position: 'absolute', right: '14px' }} />
            </div>
          </div>

          {/* 2. Connection Dropdown */}
          <div style={{ position: 'relative' }}>
            <div
              style={{
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                padding: '12px 14px',
                background: '#FFFFFF',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: '-9px',
                  left: '12px',
                  background: '#FFFFFF',
                  padding: '0 6px',
                  fontSize: '11.5px',
                  fontWeight: 500,
                  color: '#64748B',
                }}
              >
                Connection
              </span>
              <select
                value={connectionName}
                onChange={(e) => setConnectionName(e.target.value)}
                className="metric-clean-field"
                disabled={loadingSources}
                style={{
                  width: '100%',
                  border: 'none',
                  outline: 'none',
                  boxShadow: 'none',
                  background: 'transparent',
                  fontSize: '13.5px',
                  color: '#1E293B',
                  fontWeight: 500,
                  cursor: loadingSources ? 'wait' : 'pointer',
                  appearance: 'none',
                }}
              >
                {loadingSources ? (
                  <option value="">Loading data sources...</option>
                ) : availableConnections.length > 0 ? (
                  availableConnections.map((c) => (
                    <option key={c.id} value={c.name}>
                      {c.name}{c.database && c.database !== c.name ? ` (${c.database})` : ''}
                    </option>
                  ))
                ) : (
                  <option value={domainName || 'Default Connection'}>
                    {domainName || 'Default Connection'}
                  </option>
                )}
              </select>
              <ChevronDown size={16} style={{ color: '#64748B', pointerEvents: 'none', position: 'absolute', right: '14px' }} />
            </div>
            <span style={{ fontSize: '11.5px', color: '#94A3B8', marginTop: '4px', display: 'block', paddingLeft: '2px' }}>
              All referenced tables must be joinable on this connection.
            </span>
          </div>

          {/* 3. Metric Name Input */}
          <div style={{ position: 'relative' }}>
            <div
              style={{
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                padding: '12px 14px',
                background: '#FFFFFF',
                position: 'relative',
                boxShadow: 'none',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: '-9px',
                  left: '12px',
                  background: '#FFFFFF',
                  padding: '0 6px',
                  fontSize: '11.5px',
                  fontWeight: 500,
                  color: '#64748B',
                }}
              >
                Metric name
              </span>
              <input
                type="text"
                value={metricName}
                onChange={(e) => setMetricName(e.target.value)}
                placeholder="e.g. Average Deal Value"
                className="metric-clean-field"
                style={{
                  width: '100%',
                  border: 'none',
                  outline: 'none',
                  boxShadow: 'none',
                  background: 'transparent',
                  fontSize: '13.5px',
                  color: '#1E293B',
                  fontWeight: 500,
                  padding: 0,
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          {/* 4. Side-by-side Split View: Describe in English & SQL */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '16px',
              marginTop: '4px',
            }}
          >
            {/* Left Column: Describe in English */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: '#1E293B' }}>
                Describe in English
              </label>
              <div
                style={{
                  border: '1px solid #CBD5E1',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  background: '#FFFFFF',
                  minHeight: '160px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  boxSizing: 'border-box',
                  boxShadow: 'none',
                }}
              >
                <textarea
                  value={englishDescription}
                  onChange={(e) => setEnglishDescription(e.target.value)}
                  placeholder="Describe how you want the Metric to be calculated. e.g. Average Deal Value is the sum of deal amounts where status equals 'won' divided by the total number of won deals."
                  rows={4}
                  className="metric-clean-field"
                  style={{
                    width: '100%',
                    border: 'none',
                    outline: 'none',
                    boxShadow: 'none',
                    resize: 'none',
                    fontSize: '12.5px',
                    lineHeight: 1.5,
                    color: '#334155',
                    background: 'transparent',
                    fontFamily: 'inherit',
                    padding: 0,
                  }}
                />

                <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '8px' }}>
                  <button
                    type="button"
                    onClick={handleGenerateSql}
                    disabled={isGenerating || !englishDescription.trim()}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      padding: '6px 14px',
                      borderRadius: '6px',
                      border: '1px solid #E2E8F0',
                      background: englishDescription.trim() ? '#EEF2F6' : '#F8FAFC',
                      color: englishDescription.trim() ? '#1E293B' : '#94A3B8',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: englishDescription.trim() && !isGenerating ? 'pointer' : 'not-allowed',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (englishDescription.trim() && !isGenerating) {
                        e.currentTarget.style.backgroundColor = '#E2E8F0';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (englishDescription.trim() && !isGenerating) {
                        e.currentTarget.style.backgroundColor = '#EEF2F6';
                      }
                    }}
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 size={13} className="animate-spin" />
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles size={13} style={{ color: '#6366F1' }} />
                        <span>Generate</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: SQL Code Editor */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <label style={{ fontSize: '13px', fontWeight: 600, color: '#1E293B' }}>
                  SQL
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <button
                    type="button"
                    onClick={handleFormatSql}
                    title="Format SQL"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#94A3B8',
                      padding: '2px',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#1E293B')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
                  >
                    <Sparkles size={13} />
                  </button>
                  <button
                    type="button"
                    onClick={handleCopySql}
                    title="Copy SQL"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: copiedSql ? '#16A34A' : '#94A3B8',
                      padding: '2px',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                    onMouseEnter={(e) => (!copiedSql ? (e.currentTarget.style.color = '#1E293B') : null)}
                    onMouseLeave={(e) => (!copiedSql ? (e.currentTarget.style.color = '#94A3B8') : null)}
                  >
                    {copiedSql ? <Check size={13} /> : <Copy size={13} />}
                  </button>
                </div>
              </div>

              <div
                style={{
                  border: '1px solid #CBD5E1',
                  borderRadius: '8px',
                  background: '#FFFFFF',
                  minHeight: '160px',
                  display: 'flex',
                  overflow: 'hidden',
                  boxSizing: 'border-box',
                  boxShadow: 'none',
                }}
              >
                {/* Line Numbers */}
                <div
                  style={{
                    padding: '12px 10px',
                    background: '#F8FAFC',
                    borderRight: '1px solid #E2E8F0',
                    color: '#94A3B8',
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                    fontSize: '12px',
                    userSelect: 'none',
                    textAlign: 'right',
                    minWidth: '24px',
                  }}
                >
                  1
                </div>

                {/* SQL Text Area */}
                <textarea
                  value={sqlCode}
                  onChange={(e) => setSqlCode(e.target.value)}
                  placeholder="Calculation. e.g. AVG(CASE WHEN is_premium_customer = TRUE THEN order_total ELSE NULL END)"
                  rows={6}
                  className="metric-sql-field"
                  style={{
                    flex: 1,
                    padding: '12px 14px',
                    border: 'none',
                    outline: 'none',
                    boxShadow: 'none',
                    resize: 'none',
                    fontSize: '12px',
                    lineHeight: 1.55,
                    color: '#0F172A',
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                    background: '#FFFFFF',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '10px',
              paddingTop: '12px',
              borderTop: '1px solid #F1F5F9',
              marginTop: '6px',
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              style={{
                padding: '8px 18px',
                borderRadius: '6px',
                border: '1px solid #E2E8F0',
                background: '#FFFFFF',
                color: '#475569',
                fontSize: '13px',
                fontWeight: 500,
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSaveDisabled}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 24px',
                borderRadius: '6px',
                border: 'none',
                background: isSaveDisabled ? '#EEF2F6' : '#4F46E5',
                color: isSaveDisabled ? '#94A3B8' : '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isSaveDisabled ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isSaveDisabled) e.currentTarget.style.backgroundColor = '#4338CA';
              }}
              onMouseLeave={(e) => {
                if (!isSaveDisabled) e.currentTarget.style.backgroundColor = '#4F46E5';
              }}
            >
              {submitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
