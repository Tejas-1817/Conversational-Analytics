import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  ChevronDown,
  ChevronUp,
  Database,
  Check,
  Plus,
  FileSpreadsheet,
  Layers,
  AlertCircle,
} from 'lucide-react';
import { fetchApi } from '../services/api';
import { SourceLogo } from './SourceLogos';

interface DataSourceItem {
  id: string;
  name: string;
  type: string;
  database_name?: string;
}

interface AddDataSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  domainName: string;
  currentSourceId?: string | null;
  onSelectExistingSource?: (sourceId: string, sourceName: string) => Promise<void> | void;
  onOpenConnectNewModal?: () => void;
  onOpenAddFilesModal?: () => void;
}

export const AddDataSourceModal: React.FC<AddDataSourceModalProps> = ({
  isOpen,
  onClose,
  domainId,
  domainName,
  currentSourceId,
  onSelectExistingSource,
  onOpenConnectNewModal,
  onOpenAddFilesModal,
}) => {
  const [sources, setSources] = useState<DataSourceItem[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>('');
  const [selectedOption, setSelectedOption] = useState<'existing' | 'connect_new' | 'add_files'>('existing');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const dropdownRef = useRef<HTMLDivElement | null>(null);

  // Load available data sources
  useEffect(() => {
    if (!isOpen) return;

    const loadSources = async () => {
      setLoading(true);
      try {
        const data = await fetchApi('/sources');
        if (Array.isArray(data)) {
          setSources(data);
          if (data.length > 0) {
            setSelectedSourceId(currentSourceId || data[0].id);
          }
        }
      } catch (err: any) {
        console.error('Failed to load data sources:', err);
      } finally {
        setLoading(false);
      }
    };

    loadSources();
  }, [isOpen, currentSourceId]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isDropdownOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (isDropdownOpen) {
          setIsDropdownOpen(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isDropdownOpen, onClose]);

  if (!isOpen) return null;

  const selectedSource = sources.find((s) => s.id === selectedSourceId);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (selectedOption === 'connect_new') {
      onClose();
      if (onOpenConnectNewModal) onOpenConnectNewModal();
      return;
    }

    if (selectedOption === 'add_files') {
      onClose();
      if (onOpenAddFilesModal) onOpenAddFilesModal();
      return;
    }

    if (!selectedSourceId) {
      setErrorMessage('Please select a data source from the list.');
      return;
    }

    setSubmitting(true);
    try {
      if (onSelectExistingSource && selectedSource) {
        await onSelectExistingSource(selectedSource.id, selectedSource.name);
      }
      onClose();
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to link data source to domain.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(2px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        animation: 'fadeIn 0.15s ease-out',
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
          maxWidth: '480px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'visible',
          position: 'relative',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '20px 24px 12px',
          }}
        >
          <h2
            style={{
              fontSize: '1.2rem',
              fontWeight: 600,
              color: '#1E293B',
              margin: 0,
              letterSpacing: '-0.01em',
            }}
          >
            Add Data Source
          </h2>

          <button
            onClick={onClose}
            disabled={submitting}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: submitting ? 'not-allowed' : 'pointer',
              color: '#94A3B8',
              padding: '4px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#1E293B')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
          >
            <X size={18} />
          </button>
        </div>

        {/* Center Database + Plus Illustration */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '8px 0 18px',
          }}
        >
          <div style={{ position: 'relative', width: '110px', height: '95px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg viewBox="0 0 110 95" width="110" height="95" fill="none">
              {/* Soft green glowing shadow at the base */}
              <ellipse cx="52" cy="84" rx="38" ry="6" fill="#DCFCE7" opacity="0.8" />
              <ellipse cx="52" cy="84" rx="26" ry="4" fill="#BBF7D0" opacity="0.6" />

              {/* Database cylinder stack */}
              <ellipse cx="52" cy="28" rx="20" ry="7" stroke="#334155" strokeWidth="2.5" fill="#FFFFFF" />
              <path d="M32 28v11c0 3.8 9 7 20 7s20-3.2 20-7V28" stroke="#334155" strokeWidth="2.5" fill="none" />
              <path d="M32 39v11c0 3.8 9 7 20 7s20-3.2 20-7V39" stroke="#334155" strokeWidth="2.5" fill="none" />
              <path d="M32 50v11c0 3.8 9 7 20 7s20-3.2 20-7V50" stroke="#334155" strokeWidth="2.5" fill="none" />

              {/* Small floating Table/Spreadsheet icon at top right */}
              <g transform="translate(68, 14)">
                <rect x="0" y="0" width="16" height="15" rx="2" stroke="#CBD5E1" strokeWidth="1.8" fill="#FFFFFF" />
                <line x1="8" y1="0" x2="8" y2="15" stroke="#CBD5E1" strokeWidth="1.2" />
                <line x1="0" y1="7.5" x2="16" y2="7.5" stroke="#CBD5E1" strokeWidth="1.2" />
              </g>

              {/* Connection link loop at bottom left */}
              <path
                d="M28 58 C 22 58 20 66 26 71 C 30 74 34 70 32 66"
                stroke="#94A3B8"
                strokeWidth="2.6"
                strokeLinecap="round"
                fill="none"
              />

              {/* Green Plus badge at bottom right */}
              <path d="M72 63h8M76 59v8" stroke="#22C55E" strokeWidth="3.2" strokeLinecap="round" />
            </svg>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleFormSubmit} style={{ padding: '0 24px 24px' }}>
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
                marginBottom: '16px',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Section: Select Data Source */}
          <div style={{ marginBottom: '18px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '13.5px',
                fontWeight: 600,
                color: '#1E293B',
                marginBottom: '8px',
              }}
            >
              Select Data Source
            </label>

            {/* Dropdown Container */}
            <div ref={dropdownRef} style={{ position: 'relative' }}>
              <div
                onClick={() => {
                  setSelectedOption('existing');
                  setIsDropdownOpen(!isDropdownOpen);
                }}
                style={{
                  width: '100%',
                  padding: '11px 16px',
                  fontSize: '14px',
                  borderRadius: '8px',
                  border: isDropdownOpen ? '1.5px solid #6366F1' : '1px solid #CBD5E1',
                  background: '#FFFFFF',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  boxSizing: 'border-box',
                  userSelect: 'none',
                  transition: 'border-color 0.15s ease',
                }}
              >
                <span style={{ color: selectedSource ? '#1E293B' : '#94A3B8', fontWeight: selectedSource ? 500 : 400 }}>
                  {selectedSource ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <SourceLogo type={selectedSource.type || selectedSource.name} size={16} />
                      {selectedSource.name}
                    </span>
                  ) : (
                    'Data source'
                  )}
                </span>

                {isDropdownOpen ? (
                  <ChevronUp size={16} style={{ color: '#64748B' }} />
                ) : (
                  <ChevronDown size={16} style={{ color: '#64748B' }} />
                )}
              </div>

              {/* Dropdown Menu */}
              {isDropdownOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 4px)',
                    left: 0,
                    right: 0,
                    background: '#FFFFFF',
                    border: '1px solid #E2E8F0',
                    borderRadius: '8px',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                    zIndex: 1000,
                    padding: '6px 0',
                    maxHeight: '220px',
                    overflowY: 'auto',
                  }}
                >
                  {sources.length === 0 ? (
                    <div style={{ padding: '10px 16px', fontSize: '13px', color: '#94A3B8' }}>
                      No connected sources found.
                    </div>
                  ) : (
                    sources.map((src) => {
                      const isSelected = selectedSourceId === src.id && selectedOption === 'existing';
                      return (
                        <div
                          key={src.id}
                          onClick={() => {
                            setSelectedSourceId(src.id);
                            setSelectedOption('existing');
                            setIsDropdownOpen(false);
                          }}
                          style={{
                            padding: '9px 16px',
                            fontSize: '13.5px',
                            color: isSelected ? '#4F46E5' : '#334155',
                            fontWeight: isSelected ? 600 : 400,
                            background: isSelected ? '#EEF2FF' : 'transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC';
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <SourceLogo type={src.type || src.name} size={16} />
                            <span>{src.name}</span>
                          </div>
                          {isSelected && <Check size={15} style={{ color: '#4F46E5' }} />}
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Divider with text "or" */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              margin: '18px 0',
            }}
          >
            <div style={{ flex: 1, height: '1px', background: '#E2E8F0' }} />
            <span style={{ padding: '0 12px', fontSize: '12.5px', color: '#64748B', fontWeight: 500 }}>or</span>
            <div style={{ flex: 1, height: '1px', background: '#E2E8F0' }} />
          </div>

          {/* Radio Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '28px' }}>
            {/* Option 1: Connect new Data store or MCP server */}
            <label
              onClick={() => setSelectedOption('connect_new')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                cursor: 'pointer',
                fontSize: '13.5px',
                color: '#1E293B',
                userSelect: 'none',
              }}
            >
              <div
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  border: selectedOption === 'connect_new' ? '5px solid #4F46E5' : '1.5px solid #94A3B8',
                  background: '#FFFFFF',
                  boxSizing: 'border-box',
                  transition: 'all 0.15s ease',
                  flexShrink: 0,
                }}
              />
              <span>Connect new Data store or MCP server</span>
            </label>

            {/* Option 2: Add Files */}
            <label
              onClick={() => setSelectedOption('add_files')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                cursor: 'pointer',
                fontSize: '13.5px',
                color: '#1E293B',
                userSelect: 'none',
              }}
            >
              <div
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  border: selectedOption === 'add_files' ? '5px solid #4F46E5' : '1.5px solid #94A3B8',
                  background: '#FFFFFF',
                  boxSizing: 'border-box',
                  transition: 'all 0.15s ease',
                  flexShrink: 0,
                }}
              />
              <span>Add Files</span>
            </label>
          </div>

          {/* Action Button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="submit"
              disabled={submitting}
              style={{
                background: submitting ? '#93C5FD' : '#4F46E5',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                padding: '10px 24px',
                fontSize: '13.5px',
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.15s ease',
                boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
              }}
              onMouseEnter={(e) => {
                if (!submitting) e.currentTarget.style.backgroundColor = '#4338CA';
              }}
              onMouseLeave={(e) => {
                if (!submitting) e.currentTarget.style.backgroundColor = '#4F46E5';
              }}
            >
              {submitting ? 'Adding...' : 'Add Data Source'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
