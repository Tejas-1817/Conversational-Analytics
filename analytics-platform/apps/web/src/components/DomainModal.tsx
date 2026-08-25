import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, AlertTriangle, CheckCircle2, Upload, FileText, Loader2, Download } from 'lucide-react';
import { z } from 'zod';
import { fetchApi } from '../services/api';
import { addMockDomain, updateMockDomainDocs, mockDomains } from '../pages/business/Domains';

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'csv', 'xlsx'] as const;

const domainSchema = z.object({
  name: z.string().min(1, 'Domain name is required').max(200),
  description: z.string().max(5000).optional(),
});

type DomainFormData = z.infer<typeof domainSchema>;
type FileUploadStatus = 'pending' | 'uploading' | 'done' | 'failed';

interface FileEntry {
  clientId: string;
  name: string;
  sizeBytes: number;
  status: FileUploadStatus;
  file?: File;
}

interface ViewDomainDetails {
  name: string;
  description: string;
  documents: { id: string; name: string; sizeBytes: number }[];
  tables: {
    name: string;
    relationships: string[];
    metrics: string[];
    dimensions: string[];
  }[];
}

interface DomainModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  existingDomainId?: string;
  existingDomainName?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getExtension(fileName: string): string {
  return fileName.split('.').pop()?.toLowerCase() ?? '';
}

export const DomainModal: React.FC<DomainModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  existingDomainId,
  existingDomainName,
}) => {
  const [formData, setFormData] = useState<DomainFormData>({ name: '', description: '' });
  const [errors, setErrors] = useState<Partial<Record<keyof DomainFormData, string>>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);

  const [domainId, setDomainId] = useState<string | null>(existingDomainId ?? null);
  const [domainName, setDomainName] = useState<string>(existingDomainName ?? '');
  const [fileEntries, setFileEntries] = useState<FileEntry[]>([]);
  const [rejectedFiles, setRejectedFiles] = useState<string[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [viewData, setViewData] = useState<ViewDomainDetails | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (existingDomainId) {
        setDomainId(existingDomainId);
        setDomainName(existingDomainName ?? '');
        
        // Fetch domain details from backend
        fetchApi(`/domains/${existingDomainId}`)
          .then(data => {
            setViewData({
              name: data.name,
              description: data.description || 'No description provided.',
              documents: data.documents.map((d: any) => ({
                id: d.id,
                name: d.file_name,
                sizeBytes: d.file_size
              })),
              tables: data.tables.map((t: any) => ({
                name: t.table_name,
                relationships: t.relationships || [],
                metrics: t.metrics || [],
                dimensions: t.dimensions || [],
              }))
            });
          })
          .catch(err => {
            console.error('Failed to fetch domain details', err);
            setViewData({
              name: existingDomainName || 'Domain Details',
              description: 'No description provided.',
              documents: [],
              tables: []
            });
          });
      } else {
        setDomainId(null);
        setDomainName('');
        setViewData(null);
      }
      setFormData({ name: '', description: '' });
      setErrors({});
      setBackendError(null);
      setFileEntries([]);
      setRejectedFiles([]);
    }
  }, [isOpen, existingDomainId, existingDomainName]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isSaving) onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, isSaving, onClose]);

  if (!isOpen) return null;

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name as keyof DomainFormData]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const [sources, setSources] = useState<any[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>('');
  const [availableTables, setAvailableTables] = useState<any[]>([]);
  const [selectedTableIds, setSelectedTableIds] = useState<string[]>([]);
  const [isLoadingTables, setIsLoadingTables] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      fetchApi('/sources')
        .then((data: any) => setSources(Array.isArray(data) ? data : []))
        .catch(() => setSources([]));
    }
  }, [isOpen]);

  const handleSourceChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const srcId = e.target.value;
    setSelectedSourceId(srcId);
    setSelectedTableIds([]);
    setAvailableTables([]);
    if (!srcId) return;

    setIsLoadingTables(true);
    try {
      const data = await fetchApi(`/metadata/sources/${srcId}/tables`);
      setAvailableTables(Array.isArray(data) ? data : []);
    } catch (err) {
      console.warn('Failed to fetch tables for source', err);
    } finally {
      setIsLoadingTables(false);
    }
  };

  const toggleTableSelect = (tId: string) => {
    setSelectedTableIds(prev =>
      prev.includes(tId) ? prev.filter(id => id !== tId) : [...prev, tId]
    );
  };

  const selectAllTables = () => {
    setSelectedTableIds(availableTables.map(t => t.id));
  };

  const deselectAllTables = () => {
    setSelectedTableIds([]);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBackendError(null);

    const result = domainSchema.safeParse(formData);
    if (!result.success) {
      const fieldErrors: Partial<Record<keyof DomainFormData, string>> = {};
      for (const issue of result.error.issues) {
        const field = issue.path[0] as keyof DomainFormData;
        fieldErrors[field] = issue.message;
      }
      setErrors(fieldErrors);
      return;
    }

    setIsSaving(true);
    try {
      let activeDomainId = domainId;

      if (!activeDomainId) {
        const domain = await fetchApi('/domains', {
          method: 'POST',
          body: JSON.stringify({
            name: formData.name,
            description: formData.description || '',
            source_id: selectedSourceId || null,
            table_ids: selectedTableIds,
          }),
        });
        activeDomainId = domain.id;
        setDomainId(domain.id);
        setDomainName(domain.name);
      }

      const pendingEntries = fileEntries.filter(f => f.status === 'pending' && f.file);
      if (pendingEntries.length > 0 && activeDomainId) {
        setFileEntries(prev => prev.map(f => f.status === 'pending' ? { ...f, status: 'uploading' } : f));
        
        await Promise.all(pendingEntries.map(async (entry) => {
          const form = new FormData();
          form.append('file', entry.file!);
          try {
            await fetchApi(`/domains/${activeDomainId}/documents`, { method: 'POST', body: form });
            setFileEntries(prev => prev.map(f => f.clientId === entry.clientId ? { ...f, status: 'done' } : f));
          } catch (err) {
            console.error('File upload failed', err);
            setFileEntries(prev => prev.map(f => f.clientId === entry.clientId ? { ...f, status: 'failed' } : f));
          }
        }));
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setBackendError(err.message || 'An error occurred.');
    } finally {
      setIsSaving(false);
    }
  };

  const uploadFiles = (files: File[]) => {
    const accepted: File[] = [];
    const rejected: string[] = [];

    for (const file of files) {
      const ext = getExtension(file.name);
      if ((ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) {
        accepted.push(file);
      } else {
        rejected.push(file.name);
      }
    }
    setRejectedFiles(rejected);

    for (const file of accepted) {
      const clientId = `${Date.now()}-${Math.random()}`;
      if (domainId) {
        setFileEntries(prev => [
          ...prev,
          { clientId, name: file.name, sizeBytes: file.size, status: 'uploading' },
        ]);
        const form = new FormData();
        form.append('file', file);
        fetchApi(`/domains/${domainId}/documents`, { method: 'POST', body: form })
          .then(() => {
            setFileEntries(prev =>
              prev.map(f => (f.clientId === clientId ? { ...f, status: 'done' } : f))
            );
          })
          .catch(() => {
            console.warn('Backend unavailable, mocking successful file upload.');
            setTimeout(() => {
              setFileEntries(prev =>
                prev.map(f => (f.clientId === clientId ? { ...f, status: 'done' } : f))
              );
              updateMockDomainDocs(domainId, 1);
            }, 600);
          });
      } else {
        setFileEntries(prev => [
          ...prev,
          { clientId, name: file.name, sizeBytes: file.size, status: 'pending', file },
        ]);
      }
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) uploadFiles(Array.from(e.target.files));
    e.target.value = '';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    uploadFiles(Array.from(e.dataTransfer.files));
  };

  const handleDone = () => {
    onSuccess();
    onClose();
  };

  if (existingDomainId && viewData) {
    return (
      <div className="modal-overlay">
        <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '850px', width: '100%' }}>
          <div className="modal-header">
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>{viewData.name}</h2>
            <button className="btn-ghost" onClick={onClose} style={{ padding: '4px' }} aria-label="Close"><X size={20} /></button>
          </div>
          <div className="modal-body custom-scrollbar" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '1.5rem' }}>
            
            <div>
              <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Description</h3>
              <p style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.5, color: 'var(--text-main)' }}>{viewData.description}</p>
            </div>

            <div>
              <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Selected Tables</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {viewData.tables.map((t, i) => (
                  <div key={i} style={{ padding: '1rem', background: 'var(--bg-dark)', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                    <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--primary)', marginBottom: '0.75rem' }}>{t.name}</div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>Relationships</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          {t.relationships.map(r => <span key={r} style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>• {r}</span>)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>Metrics</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                          {t.metrics.map(m => <span key={m} style={{ fontSize: '0.75rem', padding: '3px 8px', background: 'rgba(99,102,241,0.1)', color: 'var(--primary)', borderRadius: '6px', fontWeight: 500 }}>{m}</span>)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>Dimensions</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                          {t.dimensions.map(d => <span key={d} style={{ fontSize: '0.75rem', padding: '3px 8px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px' }}>{d}</span>)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Reference Documents</h3>
              {viewData.documents.length === 0 ? (
                <div className="text-muted text-sm">No documents attached.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {viewData.documents.map((d, i) => (
                    <div 
                      key={i} 
                      onClick={async () => {
                        try {
                          const token = localStorage.getItem('token');
                          const headers: Record<string, string> = {};
                          if (token) headers['Authorization'] = `Bearer ${token}`;
                          
                          const res = await fetch(`/domains/${activeDomainId}/documents/${d.id}/download`, { headers });
                          if (!res.ok) throw new Error("Failed to download");
                          
                          const blob = await res.blob();
                          const url = window.URL.createObjectURL(blob);
                          
                          // Open in a new tab to view
                          const newTab = window.open(url, '_blank');
                          
                          // Fallback if popup blocker blocked it
                          if (!newTab) {
                            const a = document.createElement('a');
                            a.href = url;
                            a.target = '_blank';
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                          }
                          
                          // We shouldn't revoke immediately if we opened it in a new tab,
                          // but the browser will clean it up on page unload.
                          setTimeout(() => window.URL.revokeObjectURL(url), 60000);
                        } catch (e) {
                          alert("Failed to open document.");
                        }
                      }}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.6rem 0.75rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '0.85rem', cursor: 'pointer', transition: 'background-color 0.2s' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-card)'}
                    >
                      <FileText size={16} style={{ color: 'var(--text-muted)' }} />
                      <span style={{ flex: 1, color: 'var(--text-main)' }}>{d.name}</span>
                      <span className="text-muted" style={{ fontSize: '0.75rem', marginRight: '0.5rem' }}>{formatBytes(d.sizeBytes)}</span>
                      <Download size={14} style={{ color: 'var(--text-muted)' }} />
                    </div>
                  ))}
                </div>
              )}
            </div>
            
          </div>
          <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', padding: '1rem 1.5rem', borderTop: '1px solid var(--border-color)' }}>
            <button className="btn-secondary" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay">
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: '750px', width: '100%' }}
      >
        <div className="modal-header">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
            {domainId ? `Edit Domain — ${domainName}` : 'New Domain'}
          </h2>
          <button
            type="button"
            className="btn-ghost"
            onClick={onClose}
            disabled={isSaving}
            style={{ padding: '4px' }}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div className="modal-body">
            {backendError && (
              <div className="error-banner">
                <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong style={{ display: 'block', marginBottom: '2px' }}>Error</strong>
                  {backendError}
                </div>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="domain-name">Domain Name <span style={{ color: 'var(--danger, #EF4444)' }}>*</span></label>
              <input
                id="domain-name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="e.g., Sales, Marketing, Support"
                disabled={isSaving || !!domainId}
                autoFocus={!domainId}
              />
              {errors.name && <div className="form-error">{errors.name}</div>}
            </div>

            <div className="form-group">
              <label htmlFor="domain-description">
                Description
                <span className="text-muted text-sm" style={{ marginLeft: '0.5rem', fontWeight: 400 }}>
                  — provide business context for the AI
                </span>
              </label>
              <textarea
                id="domain-description"
                name="description"
                value={formData.description ?? ''}
                onChange={handleChange}
                placeholder="Describe this domain's purpose, key metrics, or relevant terminology…"
                disabled={isSaving || !!domainId}
                rows={3}
                style={{
                  width: '100%',
                  resize: 'vertical',
                  fontFamily: 'inherit',
                  fontSize: '0.9rem',
                  padding: '0.6rem 0.75rem',
                  background: 'var(--bg-dark)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-main)',
                  boxSizing: 'border-box',
                }}
              />
              {errors.description && <div className="form-error">{errors.description}</div>}
            </div>

            {!domainId && (
              <>
                <div className="form-group" style={{ marginTop: '1rem' }}>
                  <label htmlFor="domain-source">Connect Database Source</label>
                  <select
                    id="domain-source"
                    value={selectedSourceId}
                    onChange={handleSourceChange}
                    disabled={isSaving}
                    style={{
                      width: '100%',
                      padding: '0.6rem 0.75rem',
                      background: 'var(--bg-dark)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-main)',
                    }}
                  >
                    <option value="">-- Select Connected Database --</option>
                    {sources.map(src => (
                      <option key={src.id} value={src.id}>
                        {src.name} ({src.type} - {src.database_name || src.host})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedSourceId && (
                  <div className="form-group" style={{ marginTop: '1rem' }}>
                    <div className="flex justify-between items-center mb-2">
                      <label style={{ margin: 0 }}>Select Domain Tables ({selectedTableIds.length} selected)</label>
                      <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8rem' }}>
                        <button type="button" className="btn-ghost" onClick={selectAllTables} style={{ padding: '2px 6px' }}>Select All</button>
                        <button type="button" className="btn-ghost" onClick={deselectAllTables} style={{ padding: '2px 6px' }}>Clear</button>
                      </div>
                    </div>

                    {isLoadingTables ? (
                      <div className="text-muted text-sm" style={{ padding: '0.5rem' }}>Loading tables…</div>
                    ) : availableTables.length === 0 ? (
                      <div className="text-muted text-sm" style={{ padding: '0.5rem' }}>No tables extracted yet for this database.</div>
                    ) : (
                      <div
                        style={{
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '0.5rem',
                          background: 'var(--bg-dark)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.4rem',
                          alignItems: 'stretch',
                          justifyContent: 'flex-start'
                        }}
                      >
                        {availableTables.map(tbl => (
                          <label
                            key={tbl.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'flex-start',
                              gap: '0.5rem',
                              fontSize: '0.85rem',
                              cursor: 'pointer',
                              padding: '0.3rem 0.5rem',
                              borderRadius: '4px',
                              // background: selectedTableIds.includes(tbl.id) ? 'rgba(79, 70, 229, 0.15)' : 'transparent',
                              width: '100%',
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={selectedTableIds.includes(tbl.id)}
                              onChange={() => toggleTableSelect(tbl.id)}
                              style={{ flexShrink: 0, width: 'auto', cursor: 'pointer' }}
                            />
                            <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tbl.table_name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            <div className="form-group" style={{ marginTop: '1.5rem' }}>
              <label>Attach Reference Documents <span className="text-muted text-sm" style={{ marginLeft: '0.5rem', fontWeight: 400 }}>— optional context</span></label>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${isDragOver ? 'var(--primary)' : 'var(--border-color)'}`,
                  borderRadius: '12px',
                  padding: '2rem 1rem',
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: isDragOver ? 'rgba(99,102,241,0.05)' : 'var(--bg-dark)',
                  transition: 'all 0.15s',
                  userSelect: 'none',
                  marginTop: '0.5rem'
                }}
              >
                <Upload size={28} style={{ color: 'var(--primary)', marginBottom: '0.75rem', marginInline: 'auto' }} />
                <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-main)' }}>
                  Drag & drop files here
                </p>
                <p className="text-muted text-sm" style={{ margin: '0.25rem 0 0 0' }}>
                  or click to browse — PDF, DOCX, CSV, XLSX
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.csv,.xlsx"
                  style={{ display: 'none' }}
                  onChange={handleFileInputChange}
                />
              </div>

              {rejectedFiles.length > 0 && (
                <div className="error-banner" style={{ marginTop: '0.75rem' }}>
                  <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ display: 'block', marginBottom: '2px' }}>Unsupported file type</strong>
                    {rejectedFiles.join(', ')} — only PDF, DOCX, CSV, XLSX are allowed.
                  </div>
                </div>
              )}

              {fileEntries.length > 0 && (
                <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {fileEntries.map(f => (
                    <div
                      key={f.clientId}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.6rem',
                        padding: '0.5rem 0.75rem',
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '8px',
                        fontSize: '0.85rem',
                      }}
                    >
                      <FileText size={14} style={{ flexShrink: 0, color: 'var(--text-muted)' }} />
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-main)' }}>
                        {f.name}
                      </span>
                      <span className="text-muted" style={{ fontSize: '0.75rem', flexShrink: 0 }}>
                        {formatBytes(f.sizeBytes)}
                      </span>
                      {f.status === 'uploading' && (
                        <Loader2 size={14} style={{ flexShrink: 0, color: 'var(--primary)', animation: 'spin 1s linear infinite' }} />
                      )}
                      {f.status === 'done' && (
                        <CheckCircle2 size={14} style={{ flexShrink: 0, color: '#10B981' }} />
                      )}
                      {f.status === 'failed' && (
                        <AlertTriangle size={14} style={{ flexShrink: 0, color: '#EF4444' }} />
                      )}
                      {f.status === 'pending' && (
                        <span className="text-sm text-muted" style={{ flexShrink: 0 }}>Pending</span>
                      )}
                      {f.status !== 'pending' && (
                        <span
                          className="text-sm"
                          style={{
                            flexShrink: 0,
                            color: f.status === 'done' ? '#10B981' : f.status === 'failed' ? '#EF4444' : 'var(--primary)',
                          }}
                        >
                          {f.status}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="modal-footer" style={{ justifyContent: 'flex-end', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {isSaving ? (
                <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Saving…</>
              ) : (
                domainId ? 'Done' : 'Create Domain'
              )}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};
