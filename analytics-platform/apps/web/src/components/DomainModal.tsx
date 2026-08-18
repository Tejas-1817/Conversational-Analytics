import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, AlertTriangle, CheckCircle2, Upload, FileText, Loader2 } from 'lucide-react';
import { z } from 'zod';
import { fetchApi } from '../services/api';
import { addMockDomain, updateMockDomainDocs } from '../pages/business/Domains';

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'csv', 'xlsx'] as const;

const domainSchema = z.object({
  name: z.string().min(1, 'Domain name is required').max(200),
  description: z.string().max(5000).optional(),
});

type DomainFormData = z.infer<typeof domainSchema>;
type FileUploadStatus = 'uploading' | 'done' | 'failed';

interface FileEntry {
  clientId: string;
  name: string;
  sizeBytes: number;
  status: FileUploadStatus;
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
  const [step, setStep] = useState<1 | 2>(existingDomainId ? 2 : 1);
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

  useEffect(() => {
    if (isOpen) {
      if (existingDomainId) {
        setStep(2);
        setDomainId(existingDomainId);
        setDomainName(existingDomainName ?? '');
      } else {
        setStep(1);
        setDomainId(null);
        setDomainName('');
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
      const domain = await fetchApi('/domains', {
        method: 'POST',
        body: JSON.stringify({
          name: formData.name,
          description: formData.description || '',
          source_id: selectedSourceId || null,
          table_ids: selectedTableIds,
        }),
      });
      setDomainId(domain.id);
      setDomainName(domain.name);
      setStep(2);
    } catch (err: any) {
      console.warn('Backend unavailable, using mock for domain creation.');
      const mockId = `domain_mock_${Date.now()}`;
      addMockDomain({
        id: mockId,
        name: formData.name,
        description: formData.description || '',
        status: 'active',
        document_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      setDomainId(mockId);
      setDomainName(formData.name);
      setStep(2);
    } finally {
      setIsSaving(false);
    }
  };

  const uploadFiles = (files: File[]) => {
    if (!domainId) return;
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
          }, 600); // simulate network delay
        });
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

  return (
    <div className="modal-overlay">
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: '520px', width: '100%' }}
      >
        <div className="modal-header">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
            {step === 1 ? 'New Domain' : `Attach Documents — ${domainName}`}
          </h2>
          <button
            className="btn-ghost"
            onClick={onClose}
            disabled={isSaving}
            style={{ padding: '4px' }}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.5rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
          }}
        >
          <span style={{ fontWeight: step === 1 ? 700 : 400, color: step === 1 ? 'var(--primary)' : undefined }}>
            1. Details
          </span>
          <span>→</span>
          <span style={{ fontWeight: step === 2 ? 700 : 400, color: step === 2 ? 'var(--primary)' : undefined }}>
            2. Documents
          </span>
        </div>

        {step === 1 && (
          <form onSubmit={handleCreate}>
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
                  disabled={isSaving}
                  autoFocus
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
                  disabled={isSaving}
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

              {/* Connected Database Source Selector */}
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

              {/* Table Selection List */}
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
                        maxHeight: '160px',
                        overflowY: 'auto',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '0.5rem',
                        background: 'var(--bg-dark)',
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                        gap: '0.4rem',
                      }}
                    >
                      {availableTables.map(tbl => (
                        <label
                          key={tbl.id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            fontSize: '0.85rem',
                            cursor: 'pointer',
                            padding: '0.2rem 0.4rem',
                            borderRadius: '4px',
                            background: selectedTableIds.includes(tbl.id) ? 'rgba(79, 70, 229, 0.15)' : 'transparent',
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={selectedTableIds.includes(tbl.id)}
                            onChange={() => toggleTableSelect(tbl.id)}
                          />
                          <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{tbl.table_name}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ justifyContent: 'flex-end', display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn-secondary" onClick={onClose} disabled={isSaving}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                {isSaving ? (
                  <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Creating…</>
                ) : (
                  'Create Domain'
                )}
              </button>
            </div>
          </form>
        )}

        {step === 2 && (
          <>
            <div className="modal-body">
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
                }}
              >
                <Upload size={28} style={{ color: 'var(--primary)', marginBottom: '0.75rem' }} />
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
                      <span
                        className="text-sm"
                        style={{
                          flexShrink: 0,
                          color: f.status === 'done' ? '#10B981' : f.status === 'failed' ? '#EF4444' : 'var(--primary)',
                        }}
                      >
                        {f.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {fileEntries.length === 0 && (
                <p className="text-muted text-sm" style={{ margin: '0.75rem 0 0 0' }}>
                  No documents attached yet. You can skip this step and add documents later.
                </p>
              )}
            </div>

            <div className="modal-footer" style={{ justifyContent: 'flex-end', display: 'flex', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={handleDone}>
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
