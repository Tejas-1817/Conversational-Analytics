import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertCircle } from 'lucide-react';
import { fetchApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface AddKnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  domainName: string;
  onSuccess?: () => void;
}

export const AddKnowledgeModal: React.FC<AddKnowledgeModalProps> = ({
  isOpen,
  onClose,
  domainId,
  domainName,
  onSuccess,
}) => {
  const { user } = useAuth();
  const [knowledgeText, setKnowledgeText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const getAuthorName = () => {
    if (user?.email) {
      const prefix = user.email.split('@')[0];
      const parts = prefix.replace(/[._-]/g, ' ').split(/\s+/).filter(Boolean);
      if (parts.length > 0) {
        return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(' ');
      }
    }
    return 'Shailesh Kulkarni';
  };

  useEffect(() => {
    if (isOpen) {
      setKnowledgeText('');
      setErrorMessage(null);
    }
  }, [isOpen]);

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

  const maxChars = 2000;
  const charCount = knowledgeText.length;
  const isSaveDisabled = knowledgeText.trim().length === 0 || submitting;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaveDisabled) return;

    setSubmitting(true);
    setErrorMessage(null);

    try {
      await fetchApi(`/domains/${domainId}/terms`, {
        method: 'POST',
        body: JSON.stringify({
          definition: knowledgeText.trim(),
          term: knowledgeText.trim().slice(0, 60),
          category: 'knowledge',
          author_name: getAuthorName(),
        }),
      });

      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to add knowledge:', err);
      setErrorMessage(err?.message || 'Failed to save knowledge item.');
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
            padding: '20px 24px 14px',
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
            Add Knowledge
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

        {/* Form Body */}
        <form onSubmit={handleSave} style={{ padding: '0 24px 24px' }}>
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

          {/* Outlined Textarea with Floating Label */}
          <div style={{ position: 'relative', marginTop: '8px', marginBottom: '8px' }}>
            <div
              style={{
                border: '1.5px solid #6366F1',
                borderRadius: '8px',
                padding: '16px 16px 28px',
                background: '#FFFFFF',
                position: 'relative',
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
                  fontWeight: 600,
                  color: '#4F46E5',
                  letterSpacing: '0.02em',
                }}
              >
                Knowledge
              </span>

              <textarea
                value={knowledgeText}
                onChange={(e) => setKnowledgeText(e.target.value.slice(0, maxChars))}
                placeholder=""
                rows={5}
                autoFocus
                style={{
                  width: '100%',
                  border: 'none',
                  outline: 'none',
                  boxShadow: 'none',
                  background: 'transparent',
                  padding: 0,
                  borderRadius: 0,
                  resize: 'none',
                  fontSize: '13.5px',
                  lineHeight: 1.55,
                  color: '#1E293B',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => {
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.borderColor = 'transparent';
                  e.currentTarget.style.outline = 'none';
                }}
              />

              {/* Character Counter */}
              <div
                style={{
                  position: 'absolute',
                  bottom: '8px',
                  right: '12px',
                  fontSize: '11.5px',
                  color: charCount >= maxChars ? '#DC2626' : '#94A3B8',
                }}
              >
                {charCount} / {maxChars.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Buttons Footer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              style={{
                padding: '8px 20px',
                borderRadius: '6px',
                border: '1px solid #E2E8F0',
                background: '#FFFFFF',
                color: '#475569',
                fontSize: '13.5px',
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
                background: isSaveDisabled ? '#F1F5F9' : '#4F46E5',
                color: isSaveDisabled ? '#94A3B8' : '#FFFFFF',
                fontSize: '13.5px',
                fontWeight: 600,
                cursor: isSaveDisabled ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {submitting ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
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
