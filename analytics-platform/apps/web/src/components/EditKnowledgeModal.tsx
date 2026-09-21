import React, { useState, useEffect } from 'react';
import { X, Link2, Loader2, AlertCircle, Check } from 'lucide-react';
import { fetchApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface EditKnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  domainName: string;
  item: {
    id: string;
    text: string;
    author: string;
    modified_at: string;
  } | null;
  onSuccess?: () => void;
}

export const EditKnowledgeModal: React.FC<EditKnowledgeModalProps> = ({
  isOpen,
  onClose,
  domainId,
  domainName,
  item,
  onSuccess,
}) => {
  const { user } = useAuth();
  const [knowledgeText, setKnowledgeText] = useState('');
  const [initialText, setInitialText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

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
    if (isOpen && item) {
      setKnowledgeText(item.text);
      setInitialText(item.text);
      setErrorMessage(null);
      setCopiedLink(false);
    }
  }, [isOpen, item]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !item) return null;

  const maxChars = Math.max(10000, knowledgeText.length);
  const charCount = knowledgeText.length;
  const isModified = knowledgeText.trim() !== initialText.trim();
  const isSaveDisabled = !isModified || knowledgeText.trim().length === 0 || submitting;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaveDisabled) return;

    setSubmitting(true);
    setErrorMessage(null);

    try {
      const currentAuthor = getAuthorName();
      if (item.id.startsWith('know-default')) {
        // Create as real record in DB if it was default
        await fetchApi(`/domains/${domainId}/terms`, {
          method: 'POST',
          body: JSON.stringify({
            definition: knowledgeText.trim(),
            term: knowledgeText.trim().slice(0, 60),
            category: 'knowledge',
            author_name: currentAuthor,
          }),
        });
      } else {
        await fetchApi(`/domains/${domainId}/terms/${item.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            definition: knowledgeText.trim(),
            term: knowledgeText.trim().slice(0, 60),
            category: 'knowledge',
            author_name: currentAuthor,
          }),
        });
      }

      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to update knowledge:', err);
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
          maxWidth: '680px',
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
            Edit Knowledge
          </h2>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Copy Link Button */}
            <button
              onClick={handleCopyLink}
              title="Copy link"
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: copiedLink ? '#16A34A' : '#64748B',
                padding: '4px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'color 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!copiedLink) e.currentTarget.style.color = '#1E293B';
              }}
              onMouseLeave={(e) => {
                if (!copiedLink) e.currentTarget.style.color = '#64748B';
              }}
            >
              {copiedLink ? <Check size={17} /> : <Link2 size={17} />}
            </button>

            {/* Close Button */}
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
                onChange={(e) => setKnowledgeText(e.target.value)}
                rows={10}
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
                  lineHeight: 1.6,
                  color: '#1E293B',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                  minHeight: '180px',
                  maxHeight: '380px',
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
                  color: '#94A3B8',
                }}
              >
                {charCount.toLocaleString()} / {charCount.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Last Modified Subtext on Left & Action Buttons on Right */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: '16px',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ fontSize: '12.5px', color: '#64748B' }}>
              Last modified {item.author} at {item.modified_at}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                style={{
                  padding: '8px 20px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
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
          </div>
        </form>
      </div>
    </div>
  );
};
