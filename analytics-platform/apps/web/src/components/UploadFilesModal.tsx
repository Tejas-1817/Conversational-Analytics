import React, { useState, useRef } from 'react';
import {
  X,
  Upload,
  FileText,
  FileSpreadsheet,
  File,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { fetchApi } from '../services/api';

interface UploadFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  domainName: string;
  onSuccess?: () => void;
}

export const UploadFilesModal: React.FC<UploadFilesModalProps> = ({
  isOpen,
  onClose,
  domainId,
  domainName,
  onSuccess,
}) => {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpen) return null;

  const handleFileSelection = (selectedFiles: FileList | null) => {
    if (!selectedFiles || selectedFiles.length === 0) return;
    setErrorMessage(null);
    setSuccessMessage(null);

    const validExtensions = ['.pdf', '.csv', '.xlsx', '.xls', '.docx', '.doc', '.txt', '.json', '.md'];
    const newFiles: File[] = [];

    Array.from(selectedFiles).forEach((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      if (validExtensions.includes(ext)) {
        // Max 50MB per file
        if (f.size > 50 * 1024 * 1024) {
          setErrorMessage(`File "${f.name}" exceeds maximum allowed size of 50MB.`);
        } else {
          newFiles.push(f);
        }
      } else {
        setErrorMessage(`File "${f.name}" has an unsupported format. Allowed: PDF, CSV, Excel, Word, TXT.`);
      }
    });

    setFiles((prev) => [...prev, ...newFiles]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    if (files.length <= 1) {
      setErrorMessage(null);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setErrorMessage('Please select at least one file to upload.');
      return;
    }

    setUploading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    let uploadedCount = 0;
    const errors: string[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('file', file);

      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/domains/${domainId}/documents`, {
          method: 'POST',
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to upload ${file.name}`);
        }

        uploadedCount++;
        setUploadProgress(Math.round(((i + 1) / files.length) * 100));
      } catch (err: any) {
        errors.push(`${file.name}: ${err.message || 'Upload failed'}`);
      }
    }

    setUploading(false);

    if (errors.length > 0) {
      setErrorMessage(`Uploaded ${uploadedCount}/${files.length} files. Errors: ${errors.join(', ')}`);
    } else {
      setSuccessMessage(`Successfully uploaded ${uploadedCount} file(s) to ${domainName}! Background embeddings & term extraction started.`);
      setTimeout(() => {
        if (onSuccess) onSuccess();
        onClose();
        setFiles([]);
        setSuccessMessage(null);
      }, 1500);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') {
      return <FileSpreadsheet size={20} style={{ color: '#16A34A' }} />;
    }
    if (ext === 'pdf') {
      return <FileText size={20} style={{ color: '#DC2626' }} />;
    }
    if (ext === 'doc' || ext === 'docx') {
      return <FileText size={20} style={{ color: '#2563EB' }} />;
    }
    return <File size={20} style={{ color: '#64748B' }} />;
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
        if (e.target === e.currentTarget && !uploading) onClose();
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '560px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '20px 24px 16px',
            borderBottom: '1px solid #F1F5F9',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: '1.2rem',
                fontWeight: 600,
                color: '#1E293B',
                margin: '0 0 2px 0',
                letterSpacing: '-0.01em',
              }}
            >
              Add Files to Domain Context
            </h2>
            <div style={{ fontSize: '12.5px', color: '#64748B' }}>
              Upload business documents to ground your AI assistant in <strong>{domainName}</strong>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={uploading}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: uploading ? 'not-allowed' : 'pointer',
              color: '#94A3B8',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Content */}
        <div style={{ padding: '24px' }}>
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
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#F0FDF4',
                border: '1px solid #DCFCE7',
                color: '#16A34A',
                fontSize: '13px',
                marginBottom: '16px',
              }}
            >
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Drag & Drop Upload Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              handleFileSelection(e.dataTransfer.files);
            }}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: isDragging ? '2px dashed #4F46E5' : '2px dashed #CBD5E1',
              borderRadius: '10px',
              padding: '32px 20px',
              textAlign: 'center',
              background: isDragging ? '#EEF2FF' : '#F8FAFC',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              marginBottom: files.length > 0 ? '16px' : '0',
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => handleFileSelection(e.target.files)}
              multiple
              accept=".pdf,.csv,.xlsx,.xls,.docx,.doc,.txt,.json,.md"
              style={{ display: 'none' }}
            />

            {/* Icons Stack Illustration */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                marginBottom: '12px',
              }}
            >
              <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 6px', background: '#FEE2E2', color: '#DC2626', borderRadius: '4px' }}>PDF</span>
              <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 6px', background: '#DCFCE7', color: '#16A34A', borderRadius: '4px' }}>CSV</span>
              <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 6px', background: '#DBEAFE', color: '#2563EB', borderRadius: '4px' }}>DOC</span>
              <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 6px', background: '#F1F5F9', color: '#475569', borderRadius: '4px' }}>TXT</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '6px' }}>
              <Upload size={20} style={{ color: '#4F46E5' }} />
              <span style={{ fontWeight: 600, fontSize: '14px', color: '#1E293B' }}>
                Choose files or drag & drop
              </span>
            </div>
            <div style={{ fontSize: '12px', color: '#64748B' }}>
              Supports PDF, DOCX, CSV, XLSX, and TXT up to 50MB
            </div>
          </div>

          {/* Selected Files List */}
          {files.length > 0 && (
            <div style={{ maxHeight: '180px', overflowY: 'auto', marginBottom: '16px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '8px' }}>
                SELECTED FILES ({files.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {files.map((file, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      background: '#F8FAFC',
                      border: '1px solid #E2E8F0',
                      borderRadius: '6px',
                      fontSize: '13px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                      {getFileIcon(file.name)}
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <div style={{ fontWeight: 500, color: '#1E293B' }}>{file.name}</div>
                        <div style={{ fontSize: '11px', color: '#64748B' }}>{formatFileSize(file.size)}</div>
                      </div>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(idx);
                      }}
                      disabled={uploading}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        cursor: uploading ? 'not-allowed' : 'pointer',
                        color: '#94A3B8',
                        padding: '4px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#DC2626')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload Progress Bar */}
          {uploading && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#64748B', marginBottom: '4px' }}>
                <span>Uploading files...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div style={{ height: '6px', background: '#E2E8F0', borderRadius: '3px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${uploadProgress}%`,
                    background: '#4F46E5',
                    borderRadius: '3px',
                    transition: 'width 0.2s ease',
                  }}
                />
              </div>
            </div>
          )}

          {/* Action Footer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button
              onClick={onClose}
              disabled={uploading}
              style={{
                padding: '8px 16px',
                fontSize: '13px',
                fontWeight: 500,
                color: '#475569',
                background: '#FFFFFF',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                cursor: uploading ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>

            <button
              onClick={handleUpload}
              disabled={uploading || files.length === 0}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 20px',
                fontSize: '13.5px',
                fontWeight: 600,
                color: '#FFFFFF',
                background: uploading || files.length === 0 ? '#93C5FD' : '#4F46E5',
                border: 'none',
                borderRadius: '8px',
                cursor: uploading || files.length === 0 ? 'not-allowed' : 'pointer',
                boxShadow: '0 1px 2px rgba(79, 70, 229, 0.2)',
              }}
            >
              {uploading ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <Upload size={14} />
                  <span>Upload {files.length > 0 ? `(${files.length})` : ''}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
