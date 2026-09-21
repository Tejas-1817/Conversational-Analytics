import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  ChevronDown,
  ChevronUp,
  Check,
  UploadCloud,
  FileText,
  AlertCircle,
  Loader2,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { fetchApi } from '../services/api';

interface ConnectContextBuilderModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  domainName: string;
  onSuccess?: () => void;
}

type SourceType = 'add_files' | 'connect_repo' | 'mcp' | 'query_logs';

interface StagedFileItem {
  id: string;
  name: string;
  size?: number;
  fileObj?: File;
  instructions: string;
  acceptanceStrategy: 'do_not_auto_accept' | 'auto_accept_all';
}

export const ConnectContextBuilderModal: React.FC<ConnectContextBuilderModalProps> = ({
  isOpen,
  onClose,
  domainId,
  domainName,
  onSuccess,
}) => {
  const [sourceType, setSourceType] = useState<SourceType>('add_files');
  const [isSourceDropdownOpen, setIsSourceDropdownOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Staged Files list — empty by default so Step 1 displays initially
  const [stagedFiles, setStagedFiles] = useState<StagedFileItem[]>([]);

  // Active open dropdown for acceptance strategy per row
  const [activeStrategyDropdownId, setActiveStrategyDropdownId] = useState<string | null>(null);

  // Advanced Options state
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(true);
  const [advancedOptions, setAdvancedOptions] = useState({
    metrics: true,
    derivedColumns: true,
    descriptions: true,
    relationships: true,
    knowledge: true,
    reviewedQueries: true,
    synonyms: false,
  });

  // Connect to Repository state
  const [repoDataSource, setRepoDataSource] = useState('');
  const [repoPaths, setRepoPaths] = useState('');
  const [repoInstructions, setRepoInstructions] = useState('');
  const [repoAcceptanceStrategy, setRepoAcceptanceStrategy] = useState<'do_not_auto_accept' | 'auto_accept_all'>('do_not_auto_accept');
  const [isRepoDataSourceOpen, setIsRepoDataSourceOpen] = useState(false);
  const [isRepoStrategyOpen, setIsRepoStrategyOpen] = useState(false);
  const [availableDataSources, setAvailableDataSources] = useState<any[]>([]);

  // MCP inputs
  const [mcpServerUrl, setMcpServerUrl] = useState('');

  // Query logs inputs
  const [queryLogOption, setQueryLogOption] = useState('upload_log');

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const sourceDropdownRef = useRef<HTMLDivElement | null>(null);
  const strategyMenuRef = useRef<HTMLDivElement | null>(null);
  const repoDataSourceRef = useRef<HTMLDivElement | null>(null);
  const repoStrategyRef = useRef<HTMLDivElement | null>(null);

  // Reset state when opening modal
  useEffect(() => {
    if (isOpen) {
      setStagedFiles([]);
      setSourceType('add_files');
      setIsSourceDropdownOpen(false);
      setActiveStrategyDropdownId(null);
      setErrorMessage(null);
      setUploading(false);
      setRepoDataSource('');
      setRepoPaths('');
      setRepoInstructions('');
      setRepoAcceptanceStrategy('do_not_auto_accept');
      setIsRepoDataSourceOpen(false);
      setIsRepoStrategyOpen(false);

      fetchApi('/sources')
        .then((data) => {
          if (Array.isArray(data) && data.length > 0) {
            setAvailableDataSources(data);
          } else {
            setAvailableDataSources([
              { id: '1', name: 'PostgreSQL - Main Analytics' },
              { id: '2', name: 'Snowflake - Enterprise Data Warehouse' },
              { id: '3', name: 'BigQuery - Production Analytics' },
            ]);
          }
        })
        .catch(() => {
          setAvailableDataSources([
            { id: '1', name: 'PostgreSQL - Main Analytics' },
            { id: '2', name: 'Snowflake - Enterprise Data Warehouse' },
            { id: '3', name: 'BigQuery - Production Analytics' },
          ]);
        });
    }
  }, [isOpen]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (sourceDropdownRef.current && !sourceDropdownRef.current.contains(e.target as Node)) {
        setIsSourceDropdownOpen(false);
      }
      if (strategyMenuRef.current && !strategyMenuRef.current.contains(e.target as Node)) {
        setActiveStrategyDropdownId(null);
      }
      if (repoDataSourceRef.current && !repoDataSourceRef.current.contains(e.target as Node)) {
        setIsRepoDataSourceOpen(false);
      }
      if (repoStrategyRef.current && !repoStrategyRef.current.contains(e.target as Node)) {
        setIsRepoStrategyOpen(false);
      }
    };
    if (isSourceDropdownOpen || activeStrategyDropdownId || isRepoDataSourceOpen || isRepoStrategyOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isSourceDropdownOpen, activeStrategyDropdownId, isRepoDataSourceOpen, isRepoStrategyOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (isSourceDropdownOpen) {
          setIsSourceDropdownOpen(false);
        } else if (activeStrategyDropdownId) {
          setActiveStrategyDropdownId(null);
        } else if (isRepoDataSourceOpen) {
          setIsRepoDataSourceOpen(false);
        } else if (isRepoStrategyOpen) {
          setIsRepoStrategyOpen(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSourceDropdownOpen, activeStrategyDropdownId, isRepoDataSourceOpen, isRepoStrategyOpen, onClose]);

  if (!isOpen) return null;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      addFilesToStaging(droppedFiles);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selected = Array.from(e.target.files);
      addFilesToStaging(selected);
    }
  };

  const addFilesToStaging = (newFiles: File[]) => {
    const formatted: StagedFileItem[] = newFiles.map((f, idx) => ({
      id: `staged-${Date.now()}-${idx}`,
      name: f.name.length > 38 ? `${f.name.slice(0, 34)}...` : f.name,
      size: f.size,
      fileObj: f,
      instructions: '',
      acceptanceStrategy: 'do_not_auto_accept',
    }));

    setStagedFiles((prev) => [...prev, ...formatted]);
  };

  const updateInstructions = (id: string, text: string) => {
    setStagedFiles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, instructions: text } : item))
    );
  };

  const updateAcceptanceStrategy = (id: string, strategy: 'do_not_auto_accept' | 'auto_accept_all') => {
    setStagedFiles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, acceptanceStrategy: strategy } : item))
    );
    setActiveStrategyDropdownId(null);
  };

  const removeStagedFile = (id: string) => {
    setStagedFiles((prev) => prev.filter((item) => item.id !== id));
  };

  const toggleAdvancedOption = (key: keyof typeof advancedOptions) => {
    setAdvancedOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (sourceType === 'add_files') {
      const realFiles = stagedFiles.filter((item) => item.fileObj);
      if (realFiles.length === 0) {
        setErrorMessage('Please select at least one file to build context.');
        return;
      }
      
      setUploading(true);
      try {
        const token = localStorage.getItem('token');
        for (let i = 0; i < realFiles.length; i++) {
          const item = realFiles[i];
          if (item.fileObj) {
            const formData = new FormData();
            formData.append('file', item.fileObj);

            const res = await fetch(`/domains/${domainId}/documents`, {
              method: 'POST',
              headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: formData,
            });

            if (!res.ok) {
              const errData = await res.json().catch(() => ({}));
              throw new Error(errData.detail || `Upload failed for ${item.name}`);
            }
          }
        }

        setUploading(false);
        if (onSuccess) onSuccess();
        onClose();
      } catch (err: any) {
        setUploading(false);
        setErrorMessage(err?.message || 'Failed to complete context build.');
      }
    } else if (sourceType === 'connect_repo') {
      if (!repoUrl.trim()) {
        setErrorMessage('Please enter a valid repository URL.');
        return;
      }
      setUploading(true);
      setTimeout(() => {
        setUploading(false);
        if (onSuccess) onSuccess();
        onClose();
      }, 800);
    } else if (sourceType === 'mcp') {
      if (!mcpServerUrl.trim()) {
        setErrorMessage('Please enter a valid MCP server endpoint URL.');
        return;
      }
      setUploading(true);
      setTimeout(() => {
        setUploading(false);
        if (onSuccess) onSuccess();
        onClose();
      }, 800);
    } else {
      setUploading(true);
      setTimeout(() => {
        setUploading(false);
        if (onSuccess) onSuccess();
        onClose();
      }, 800);
    }
  };

  const getSourceTypeLabel = (type: SourceType) => {
    switch (type) {
      case 'add_files':
        return 'Add Files';
      case 'connect_repo':
        return 'Connect to Repository';
      case 'mcp':
        return 'MCP';
      case 'query_logs':
        return 'Build from Query Logs';
    }
  };

  // Has at least one file been staged?
  const hasStagedFiles = stagedFiles.length > 0;

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
        if (e.target === e.currentTarget && !uploading) onClose();
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '12px',
          width: '100%',
          maxWidth: hasStagedFiles ? '900px' : sourceType === 'connect_repo' ? '560px' : '720px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'visible',
          position: 'relative',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          transition: 'max-width 0.2s ease-in-out',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            padding: '22px 28px 12px',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: '1.25rem',
                fontWeight: 600,
                color: '#1E293B',
                margin: '0 0 6px 0',
                letterSpacing: '-0.01em',
              }}
            >
              {hasStagedFiles ? 'Files Staged for Context Build' : 'Connect Context Builder Source'}
            </h2>
            <p
              style={{
                fontSize: '13px',
                color: '#475569',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              {hasStagedFiles
                ? 'Provide build instructions for each uploaded file. This will help clarify any ambiguity and provide direction for how we interpret the file contents.'
                : 'Link your existing repository, files, or query logs to automatically build domain context like metrics, descriptions, knowledge, and relationships.'}
            </p>
          </div>

          <button
            onClick={onClose}
            disabled={uploading}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: uploading ? 'not-allowed' : 'pointer',
              color: '#94A3B8',
              padding: '4px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              marginLeft: '16px',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#1E293B')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <form
          onSubmit={handleSubmit}
          style={{
            padding: '12px 28px 24px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
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

          {/* STEP 1 VIEW: Source Type Selector (shown when no files are staged yet) */}
          {!hasStagedFiles && (
            <div ref={sourceDropdownRef} style={{ position: 'relative', marginTop: '4px' }}>
              <div
                onClick={() => setIsSourceDropdownOpen(!isSourceDropdownOpen)}
                style={{
                  border: isSourceDropdownOpen || sourceType === 'connect_repo' ? '1.5px solid #6366F1' : '1px solid #CBD5E1',
                  borderRadius: '8px',
                  padding: '11px 16px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: '#FFFFFF',
                  position: 'relative',
                  transition: 'all 0.15s ease',
                }}
              >
                {/* Floating Outlined Label */}
                <span
                  style={{
                    position: 'absolute',
                    top: '-9px',
                    left: '12px',
                    background: '#FFFFFF',
                    padding: '0 6px',
                    fontSize: '11.5px',
                    fontWeight: 500,
                    color: isSourceDropdownOpen || sourceType === 'connect_repo' ? '#4F46E5' : '#64748B',
                    letterSpacing: '0.01em',
                  }}
                >
                  Source type
                </span>

                <span style={{ fontSize: '13.5px', fontWeight: 500, color: '#1E293B' }}>
                  {getSourceTypeLabel(sourceType)}
                </span>

                {isSourceDropdownOpen ? (
                  <ChevronUp size={16} style={{ color: '#64748B' }} />
                ) : (
                  <ChevronDown size={16} style={{ color: '#64748B' }} />
                )}
              </div>

              {/* Source Type Options Overlay */}
              {isSourceDropdownOpen && (
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
                    overflow: 'hidden',
                  }}
                >
                  {[
                    { id: 'add_files', label: 'Add Files' },
                    { id: 'connect_repo', label: 'Connect to Repository' },
                    { id: 'mcp', label: 'MCP' },
                    { id: 'query_logs', label: 'Build from Query Logs' },
                  ].map((opt) => {
                    const isSelected = sourceType === opt.id;
                    return (
                      <div
                        key={opt.id}
                        onClick={() => {
                          setSourceType(opt.id as SourceType);
                          setIsSourceDropdownOpen(false);
                        }}
                        style={{
                          padding: '9px 16px',
                          fontSize: '13.5px',
                          color: isSelected ? '#1E293B' : '#334155',
                          fontWeight: isSelected ? 500 : 400,
                          background: isSelected ? '#F1F5F9' : 'transparent',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC';
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                        }}
                      >
                        <div style={{ width: '16px', display: 'flex', alignItems: 'center' }}>
                          {isSelected && <Check size={15} style={{ color: '#4F46E5' }} />}
                        </div>
                        <span>{opt.label}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* STEP 2 VIEW: STAGED FILES TABLE (Shown when files are selected) */}
          {hasStagedFiles && sourceType === 'add_files' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {/* Table Header Row */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '180px 1fr 180px',
                  gap: '16px',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#475569',
                  padding: '0 4px',
                }}
              >
                <div>File name</div>
                <div>Build instructions</div>
                <div>Acceptance strategy</div>
              </div>

              {/* Staged File Rows */}
              {stagedFiles.map((item) => {
                const isStrategyOpen = activeStrategyDropdownId === item.id;
                return (
                  <div
                    key={item.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '180px 1fr 180px',
                      gap: '16px',
                      alignItems: 'center',
                      padding: '4px 0',
                    }}
                  >
                    {/* Column 1: File Name */}
                    <div
                      style={{
                        fontSize: '13px',
                        color: '#1E293B',
                        fontWeight: 500,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        paddingRight: '6px',
                      }}
                      title={item.name}
                    >
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.name}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeStagedFile(item.id)}
                        title="Remove file"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#94A3B8',
                          cursor: 'pointer',
                          padding: '2px',
                          display: 'flex',
                          alignItems: 'center',
                          flexShrink: 0,
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = '#DC2626')}
                        onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>

                    {/* Column 2: Build Instructions Input */}
                    <div>
                      <input
                        type="text"
                        placeholder="Optional — e.g., 'Focus on customer relationships'"
                        value={item.instructions}
                        onChange={(e) => updateInstructions(item.id, e.target.value)}
                        style={{
                          width: '100%',
                          padding: '9px 14px',
                          fontSize: '13px',
                          color: '#1E293B',
                          background: '#FFFFFF',
                          border: '1px solid #CBD5E1',
                          borderRadius: '6px',
                          boxSizing: 'border-box',
                          outline: 'none',
                          transition: 'border-color 0.15s ease',
                        }}
                        onFocus={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                        onBlur={(e) => (e.currentTarget.style.borderColor = '#CBD5E1')}
                      />
                    </div>

                    {/* Column 3: Acceptance Strategy Dropdown */}
                    <div style={{ position: 'relative' }}>
                      <div
                        onClick={() =>
                          setActiveStrategyDropdownId(isStrategyOpen ? null : item.id)
                        }
                        style={{
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: isStrategyOpen ? '1.5px solid #4F46E5' : '1px solid #CBD5E1',
                          background: '#FFFFFF',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '13px',
                          color: '#1E293B',
                          fontWeight: 400,
                          userSelect: 'none',
                          transition: 'border-color 0.15s ease',
                        }}
                      >
                        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {item.acceptanceStrategy === 'do_not_auto_accept'
                            ? 'Do Not Auto Accept'
                            : 'Auto Accept All'}
                        </span>
                        {isStrategyOpen ? (
                          <ChevronUp size={15} style={{ color: '#4F46E5', flexShrink: 0, marginLeft: '4px' }} />
                        ) : (
                          <ChevronDown size={15} style={{ color: '#4F46E5', flexShrink: 0, marginLeft: '4px' }} />
                        )}
                      </div>

                      {/* Acceptance Strategy Dropdown Options */}
                      {isStrategyOpen && (
                        <div
                          ref={strategyMenuRef}
                          style={{
                            position: 'absolute',
                            top: 'calc(100% + 4px)',
                            right: 0,
                            left: 0,
                            background: '#FFFFFF',
                            border: '1px solid #E2E8F0',
                            borderRadius: '8px',
                            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                            zIndex: 1000,
                            padding: '6px 0',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            onClick={() => updateAcceptanceStrategy(item.id, 'auto_accept_all')}
                            style={{
                              padding: '8px 14px',
                              fontSize: '13px',
                              color: item.acceptanceStrategy === 'auto_accept_all' ? '#4F46E5' : '#334155',
                              fontWeight: item.acceptanceStrategy === 'auto_accept_all' ? 600 : 400,
                              background: item.acceptanceStrategy === 'auto_accept_all' ? '#EEF2FF' : 'transparent',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px',
                            }}
                            onMouseEnter={(e) => {
                              if (item.acceptanceStrategy !== 'auto_accept_all')
                                e.currentTarget.style.backgroundColor = '#F8FAFC';
                            }}
                            onMouseLeave={(e) => {
                              if (item.acceptanceStrategy !== 'auto_accept_all')
                                e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                          >
                            <div style={{ width: '14px', display: 'flex', alignItems: 'center' }}>
                              {item.acceptanceStrategy === 'auto_accept_all' && <Check size={14} style={{ color: '#4F46E5' }} />}
                            </div>
                            <span>Auto Accept All</span>
                          </div>

                          <div
                            onClick={() => updateAcceptanceStrategy(item.id, 'do_not_auto_accept')}
                            style={{
                              padding: '8px 14px',
                              fontSize: '13px',
                              color: item.acceptanceStrategy === 'do_not_auto_accept' ? '#4F46E5' : '#334155',
                              fontWeight: item.acceptanceStrategy === 'do_not_auto_accept' ? 600 : 400,
                              background: item.acceptanceStrategy === 'do_not_auto_accept' ? '#EEF2FF' : 'transparent',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px',
                            }}
                            onMouseEnter={(e) => {
                              if (item.acceptanceStrategy !== 'do_not_auto_accept')
                                e.currentTarget.style.backgroundColor = '#F8FAFC';
                            }}
                            onMouseLeave={(e) => {
                              if (item.acceptanceStrategy !== 'do_not_auto_accept')
                                e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                          >
                            <div style={{ width: '14px', display: 'flex', alignItems: 'center' }}>
                              {item.acceptanceStrategy === 'do_not_auto_accept' && <Check size={14} style={{ color: '#4F46E5' }} />}
                            </div>
                            <span>Do Not Auto Accept</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* DRAG OR CLICK TO UPLOAD ZONE (Always present when in Add Files mode) */}
          {sourceType === 'add_files' && (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: isDragging ? '2px dashed #4F46E5' : '1.5px dashed #E2E8F0',
                borderRadius: '10px',
                padding: hasStagedFiles ? '20px 20px' : '32px 20px',
                textAlign: 'center',
                background: isDragging ? '#EEF2FF' : '#FFFFFF',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileInputChange}
                accept=".txt,.md,.sql,.yml,.yaml,.json,.csv,.lkml,.lookml,.pbix,.pbit,.twb,.twbx,.tds,.tdsx,.tfl,.tflx,.pdf,.docx,.doc,.rtf"
              />

              {/* Cloud Illustration with badges */}
              <div
                style={{
                  position: 'relative',
                  width: '100px',
                  height: '75px',
                  margin: '0 auto 10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <svg viewBox="0 0 100 80" width="100" height="80" fill="none">
                  {/* Soft green glow shadow */}
                  <ellipse cx="50" cy="74" rx="28" ry="4" fill="#DCFCE7" opacity="0.8" />

                  {/* Center Cloud Container */}
                  <path
                    d="M32 54 C 24 54 20 46 26 40 C 26 34 32 26 42 28 C 46 22 56 22 60 27 C 68 25 76 31 74 39 C 80 43 78 54 70 54 Z"
                    fill="#FFFFFF"
                    stroke="#475569"
                    strokeWidth="2.2"
                  />

                  {/* Floating Document Badges */}
                  {/* PDF */}
                  <g transform="translate(18, 14)">
                    <rect width="16" height="18" rx="2" fill="#FFFFFF" stroke="#64748B" strokeWidth="1.2" />
                    <text x="8" y="12" fontSize="6.5" fontWeight="bold" fill="#64748B" textAnchor="middle">
                      PDF
                    </text>
                  </g>

                  {/* CSV */}
                  <g transform="translate(64, 14)">
                    <rect width="16" height="18" rx="2" fill="#FFFFFF" stroke="#64748B" strokeWidth="1.2" />
                    <text x="8" y="12" fontSize="6.5" fontWeight="bold" fill="#64748B" textAnchor="middle">
                      CSV
                    </text>
                  </g>

                  {/* DOC */}
                  <g transform="translate(10, 36)">
                    <rect width="16" height="18" rx="2" fill="#FFFFFF" stroke="#64748B" strokeWidth="1.2" />
                    <text x="8" y="12" fontSize="6.5" fontWeight="bold" fill="#64748B" textAnchor="middle">
                      DOC
                    </text>
                  </g>

                  {/* TXT */}
                  <g transform="translate(74, 36)">
                    <rect width="16" height="18" rx="2" fill="#FFFFFF" stroke="#64748B" strokeWidth="1.2" />
                    <text x="8" y="12" fontSize="6.5" fontWeight="bold" fill="#64748B" textAnchor="middle">
                      TXT
                    </text>
                  </g>

                  {/* Code </> badge */}
                  <g transform="translate(42, 28)">
                    <rect width="16" height="15" rx="2" fill="#FFFFFF" stroke="#64748B" strokeWidth="1.2" />
                    <text x="8" y="11" fontSize="7" fontWeight="bold" fill="#64748B" textAnchor="middle">
                      &lt;/&gt;
                    </text>
                  </g>

                  {/* Green Upload Arrow in Cloud Center */}
                  <path
                    d="M50 48 V 38 M45 42 L 50 37 L 55 42"
                    stroke="#22C55E"
                    strokeWidth="2.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>

              <div style={{ fontSize: '13.5px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                Drag or click to upload files here
              </div>

              <div style={{ fontSize: '11.5px', color: '#64748B', maxWidth: '640px', margin: '0 auto 10px', lineHeight: 1.45 }}>
                .txt, .md, .sql, .yml, .yaml, .json, .csv, .lkml, .lookml, .pbix, .pbit, .twb, .twbx, .tds, .tdsx, .tfl, .tflx, .pdf, .docx, .doc, .rtf
              </div>

              {/* Beta Badge */}
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 10px',
                  borderRadius: '16px',
                  background: '#F8FAFC',
                  border: '1px solid #E2E8F0',
                  fontSize: '11px',
                  color: '#64748B',
                }}
              >
                <span
                  style={{
                    background: '#EEF2FF',
                    color: '#4F46E5',
                    fontSize: '10px',
                    fontWeight: 600,
                    padding: '1px 6px',
                    borderRadius: '10px',
                    border: '1px solid #E0E7FF',
                  }}
                >
                  Beta
                </span>
                <span>Tableau (.twb, .twbx, .tds, .tdsx, .tfl, .tflx) and Power BI (.pbix, .pbit) support is in beta</span>
              </div>
            </div>
          )}

          {/* OTHER SOURCE TYPES */}
          {sourceType === 'connect_repo' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '0px' }}>
              {/* Center Graphic/Illustration */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  margin: '4px 0 10px',
                }}
              >
                <div style={{ position: 'relative', width: '120px', height: '84px' }}>
                  {/* Soft green glow shadow */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '0px',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: '90px',
                      height: '14px',
                      background: '#DCFCE7',
                      borderRadius: '50%',
                      opacity: 0.85,
                    }}
                  />

                  {/* GitHub Octocat Icon */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '2px',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <svg viewBox="0 0 98 96" width="54" height="54" fill="#4B4769">
                      <path fillRule="evenodd" clipRule="evenodd" d="M48.854 0C21.839 0 0 22 0 49.217c0 21.756 13.993 40.172 33.405 46.69 2.427.49 3.316-1.059 3.316-2.362 0-1.141-.08-5.052-.08-9.127-13.59 2.934-16.42-5.867-16.42-5.867-2.184-5.704-5.42-7.17-5.42-7.17-4.448-3.015.324-3.015.324-3.015 4.934.326 7.523 5.052 7.523 5.052 4.367 7.496 11.404 5.378 14.235 4.074.404-3.178 1.699-5.378 3.074-6.6-10.839-1.141-22.243-5.378-22.243-24.283 0-5.378 1.94-9.778 5.014-13.2-.485-1.222-2.184-6.275.486-13.038 0 0 4.125-1.304 13.426 5.052a46.97 46.97 0 0 1 12.214-1.63c4.125 0 8.33.571 12.213 1.63 9.302-6.356 13.427-5.052 13.427-5.052 2.67 6.763.97 11.816.485 13.038 3.155 3.422 5.015 7.822 5.015 13.2 0 18.905-11.404 23.06-22.324 24.283 1.78 1.548 3.316 4.481 3.316 9.126 0 6.6-.08 11.897-.08 13.526 0 1.304.89 2.853 3.316 2.364 19.412-6.52 33.405-24.935 33.405-46.691C97.707 22 75.788 0 48.854 0z" />
                    </svg>
                  </div>

                  {/* Paperclip top right */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '0px',
                      right: '20px',
                      transform: 'rotate(25deg)',
                    }}
                  >
                    <svg width="20" height="24" viewBox="0 0 24 24" fill="none" stroke="#71717A" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                    </svg>
                  </div>

                  {/* Transfer / Sync arrows bottom left */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '12px',
                      left: '22px',
                    }}
                  >
                    <svg width="18" height="15" viewBox="0 0 24 20" fill="none" stroke="#94A3B8" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 6h14M14 2l4 4-4 4M20 14H6M10 10l-4 4 4 4" />
                    </svg>
                  </div>

                  {/* Green plus bottom right */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '12px',
                      right: '22px',
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#84CC16" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Select Data Source section */}
              <div>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#1E293B', marginBottom: '8px' }}>
                  Select Data Source
                </label>

                {/* Data source Dropdown */}
                <div ref={repoDataSourceRef} style={{ position: 'relative' }}>
                  <div
                    onClick={() => setIsRepoDataSourceOpen(!isRepoDataSourceOpen)}
                    style={{
                      border: isRepoDataSourceOpen ? '1.5px solid #6366F1' : '1px solid #CBD5E1',
                      borderRadius: '6px',
                      padding: '10px 14px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: '#FFFFFF',
                      fontSize: '13.5px',
                      color: repoDataSource ? '#1E293B' : '#64748B',
                    }}
                  >
                    <span>
                      {repoDataSource
                        ? availableDataSources.find((s) => s.id === repoDataSource)?.name || repoDataSource
                        : 'Data source'}
                    </span>
                    <ChevronDown size={16} style={{ color: '#64748B' }} />
                  </div>

                  {isRepoDataSourceOpen && (
                    <div
                      style={{
                        position: 'absolute',
                        top: 'calc(100% + 4px)',
                        left: 0,
                        right: 0,
                        background: '#FFFFFF',
                        border: '1px solid #E2E8F0',
                        borderRadius: '6px',
                        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                        zIndex: 1000,
                        padding: '4px 0',
                        maxHeight: '180px',
                        overflowY: 'auto',
                      }}
                    >
                      {availableDataSources.map((ds) => (
                        <div
                          key={ds.id}
                          onClick={() => {
                            setRepoDataSource(ds.id);
                            setIsRepoDataSourceOpen(false);
                          }}
                          style={{
                            padding: '8px 14px',
                            fontSize: '13px',
                            color: '#1E293B',
                            background: repoDataSource === ds.id ? '#F1F5F9' : 'transparent',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = '#F8FAFC')}
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.background = repoDataSource === ds.id ? '#F1F5F9' : 'transparent')
                          }
                        >
                          {ds.name}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Repository paths Input */}
              <div>
                <input
                  type="text"
                  placeholder="Repository paths"
                  value={repoPaths}
                  onChange={(e) => setRepoPaths(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13.5px',
                    boxSizing: 'border-box',
                    outline: 'none',
                    background: '#FFFFFF',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = '#CBD5E1')}
                />
                <p style={{ fontSize: '11.5px', color: '#64748B', margin: '5px 0 0 2px' }}>
                  Press Enter to add a repository - relative path. Leave blank to include the whole repository.
                </p>
              </div>

              {/* Build Instructions */}
              <div>
                <textarea
                  placeholder="Build Instructions"
                  value={repoInstructions}
                  onChange={(e) => setRepoInstructions(e.target.value)}
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13.5px',
                    boxSizing: 'border-box',
                    outline: 'none',
                    background: '#FFFFFF',
                    fontFamily: 'inherit',
                    resize: 'vertical',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = '#CBD5E1')}
                />
              </div>

              {/* Acceptance Strategy Dropdown */}
              <div>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#1E293B', marginBottom: '8px' }}>
                  Acceptance Strategy
                </label>
                <div ref={repoStrategyRef} style={{ position: 'relative' }}>
                  <div
                    onClick={() => setIsRepoStrategyOpen(!isRepoStrategyOpen)}
                    style={{
                      border: isRepoStrategyOpen ? '1.5px solid #6366F1' : '1px solid #CBD5E1',
                      borderRadius: '6px',
                      padding: '10px 14px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: '#FFFFFF',
                      fontSize: '13.5px',
                      color: '#1E293B',
                    }}
                  >
                    <span>
                      {repoAcceptanceStrategy === 'do_not_auto_accept' ? 'Do Not Auto Accept' : 'Auto Accept All'}
                    </span>
                    <ChevronDown size={16} style={{ color: '#64748B' }} />
                  </div>

                  {isRepoStrategyOpen && (
                    <div
                      style={{
                        position: 'absolute',
                        top: 'calc(100% + 4px)',
                        left: 0,
                        right: 0,
                        background: '#FFFFFF',
                        border: '1px solid #E2E8F0',
                        borderRadius: '6px',
                        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                        zIndex: 1000,
                        padding: '4px 0',
                      }}
                    >
                      <div
                        onClick={() => {
                          setRepoAcceptanceStrategy('do_not_auto_accept');
                          setIsRepoStrategyOpen(false);
                        }}
                        style={{
                          padding: '8px 14px',
                          fontSize: '13px',
                          color: '#1E293B',
                          background: repoAcceptanceStrategy === 'do_not_auto_accept' ? '#F1F5F9' : 'transparent',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = '#F8FAFC')}
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background =
                            repoAcceptanceStrategy === 'do_not_auto_accept' ? '#F1F5F9' : 'transparent')
                        }
                      >
                        Do Not Auto Accept
                      </div>
                      <div
                        onClick={() => {
                          setRepoAcceptanceStrategy('auto_accept_all');
                          setIsRepoStrategyOpen(false);
                        }}
                        style={{
                          padding: '8px 14px',
                          fontSize: '13px',
                          color: '#1E293B',
                          background: repoAcceptanceStrategy === 'auto_accept_all' ? '#F1F5F9' : 'transparent',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = '#F8FAFC')}
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background =
                            repoAcceptanceStrategy === 'auto_accept_all' ? '#F1F5F9' : 'transparent')
                        }
                      >
                        Auto Accept All
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {sourceType === 'mcp' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '4px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#1E293B', marginBottom: '8px' }}>
                  MCP Server Endpoint
                </label>
                <input
                  type="text"
                  placeholder="http://localhost:8000/mcp"
                  value={mcpServerUrl}
                  onChange={(e) => setMcpServerUrl(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13.5px',
                    boxSizing: 'border-box',
                    outline: 'none',
                    background: '#FFFFFF',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = '#CBD5E1')}
                />
              </div>
            </div>
          )}

          {sourceType === 'query_logs' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '4px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#1E293B', marginBottom: '8px' }}>
                  Query Log Source
                </label>
                <div style={{ position: 'relative' }}>
                  <select
                    value={queryLogOption}
                    onChange={(e) => setQueryLogOption(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '11px 14px',
                      borderRadius: '8px',
                      border: '1px solid #CBD5E1',
                      fontSize: '13.5px',
                      boxSizing: 'border-box',
                      background: '#FFFFFF',
                      appearance: 'none',
                      cursor: 'pointer',
                      color: '#1E293B',
                      outline: 'none',
                    }}
                    onFocus={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                    onBlur={(e) => (e.currentTarget.style.borderColor = '#CBD5E1')}
                  >
                    <option value="upload_log">Upload SQL Query Log File (.sql, .csv, .json)</option>
                    <option value="database_history">Sync from connected database query history</option>
                  </select>
                  <ChevronDown
                    size={16}
                    style={{
                      position: 'absolute',
                      right: '14px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#64748B',
                      pointerEvents: 'none',
                    }}
                  />
                </div>
              </div>

              {queryLogOption === 'upload_log' && (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: '1.5px dashed #CBD5E1',
                    borderRadius: '8px',
                    padding: '24px 16px',
                    textAlign: 'center',
                    background: '#F8FAFC',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#6366F1')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#CBD5E1')}
                >
                  <UploadCloud size={24} style={{ color: '#6366F1', margin: '0 auto 8px', display: 'block' }} />
                  <div style={{ fontSize: '13px', fontWeight: 500, color: '#1E293B', marginBottom: '4px' }}>
                    Select or drag SQL log files here
                  </div>
                  <div style={{ fontSize: '11.5px', color: '#64748B' }}>
                    Supported formats: .sql, .csv, .json
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ADVANCED OPTIONS (Displayed when files are staged for add_files mode) */}
          {hasStagedFiles && sourceType === 'add_files' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '6px' }}>
              <div
                onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  userSelect: 'none',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#334155',
                }}
              >
                {isAdvancedOpen ? <ChevronDown size={16} /> : <ChevronDown size={16} style={{ transform: 'rotate(-90deg)' }} />}
                <span>Advanced options</span>
              </div>

              {isAdvancedOpen && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '18px',
                    flexWrap: 'wrap',
                    paddingLeft: '4px',
                    fontSize: '13px',
                    color: '#334155',
                  }}
                >
                  {[
                    { key: 'metrics', label: 'Metrics' },
                    { key: 'derivedColumns', label: 'Derived Columns' },
                    { key: 'descriptions', label: 'Descriptions' },
                    { key: 'relationships', label: 'Relationships' },
                    { key: 'knowledge', label: 'Knowledge' },
                    { key: 'reviewedQueries', label: 'Reviewed Queries' },
                    { key: 'synonyms', label: 'Synonyms' },
                  ].map((opt) => {
                    const isChecked = advancedOptions[opt.key as keyof typeof advancedOptions];
                    return (
                      <label
                        key={opt.key}
                        onClick={() => toggleAdvancedOption(opt.key as keyof typeof advancedOptions)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          cursor: 'pointer',
                          userSelect: 'none',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}}
                          style={{
                            width: '15px',
                            height: '15px',
                            accentColor: '#4F46E5',
                            cursor: 'pointer',
                          }}
                        />
                        <span>{opt.label}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* FOOTER ACTION BUTTONS (Displayed for staged files OR when non-add_files source type is selected) */}
          {(hasStagedFiles || sourceType !== 'add_files') && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: '12px',
                paddingTop: '16px',
                marginTop: '10px',
              }}
            >
              <button
                type="button"
                onClick={onClose}
                disabled={uploading}
                style={{
                  padding: '8px 20px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  background: '#FFFFFF',
                  color: '#334155',
                  fontSize: '13.5px',
                  fontWeight: 500,
                  cursor: uploading ? 'not-allowed' : 'pointer',
                }}
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={uploading || (sourceType === 'connect_repo' && !repoDataSource)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 20px',
                  borderRadius: '6px',
                  border: 'none',
                  background:
                    uploading
                      ? '#93C5FD'
                      : sourceType === 'connect_repo' && !repoDataSource
                      ? '#F1F5F9'
                      : '#4F46E5',
                  color:
                    sourceType === 'connect_repo' && !repoDataSource && !uploading
                      ? '#94A3B8'
                      : '#FFFFFF',
                  fontSize: '13.5px',
                  fontWeight: 500,
                  cursor:
                    uploading || (sourceType === 'connect_repo' && !repoDataSource)
                      ? 'not-allowed'
                      : 'pointer',
                  boxShadow:
                    sourceType === 'connect_repo' && !repoDataSource
                      ? 'none'
                      : '0 1px 2px rgba(79, 70, 229, 0.2)',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!uploading && (sourceType !== 'connect_repo' || repoDataSource)) {
                    e.currentTarget.style.backgroundColor = '#4338CA';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!uploading && (sourceType !== 'connect_repo' || repoDataSource)) {
                    e.currentTarget.style.backgroundColor = '#4F46E5';
                  }
                }}
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Building Context...</span>
                  </>
                ) : (
                  <>
                    <RefreshCw size={15} />
                    <span>Build Context</span>
                  </>
                )}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
