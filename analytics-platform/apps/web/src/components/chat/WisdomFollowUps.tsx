import React, { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';

interface WisdomFollowUpsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

export const WisdomFollowUps: React.FC<WisdomFollowUpsProps> = ({ questions, onSelect }) => {
  const [isOpen, setIsOpen] = useState(true);

  if (!questions || questions.length === 0) return null;

  return (
    <div
      className="wisdom-followups-container"
      style={{
        marginTop: '2.5rem',
        marginBottom: '1.5rem',
        padding: '0.5rem 0',
        fontFamily: 'var(--font-results, "Helvetica Neue", Helvetica, Arial, sans-serif)',
        fontSize: '0.9rem',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        textAlign: 'left',
        boxSizing: 'border-box',
      }}
    >
      {/* Collapsible Header with comfortable padding & breathing room */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.6rem',
          background: 'transparent',
          border: 'none',
          borderRadius: '8px',
          padding: '0.45rem 0.75rem',
          cursor: 'pointer',
          color: 'var(--text-muted, #64748B)',
          fontSize: '0.9rem',
          fontWeight: 600,
          userSelect: 'none',
          marginBottom: isOpen ? '1.15rem' : '0',
          transition: 'all 0.15s ease',
          textAlign: 'left',
          marginLeft: '-0.35rem',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = 'var(--text-main, #0F172A)';
          e.currentTarget.style.backgroundColor = 'rgba(241, 245, 249, 0.6)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'var(--text-muted, #64748B)';
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        {isOpen ? (
          <ChevronDown size={17} style={{ color: 'var(--text-muted, #94A3B8)' }} />
        ) : (
          <ChevronRight size={17} style={{ color: 'var(--text-muted, #94A3B8)' }} />
        )}
        <span>Suggested follow-ups</span>
      </button>

      {/* Left-Aligned Follow-up Items with generous padding & vertical center alignment */}
      {isOpen && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.85rem',
            width: '100%',
            alignItems: 'flex-start',
            textAlign: 'left',
            paddingLeft: '0.5rem',
            animation: 'fadeIn 0.2s ease-in-out',
            boxSizing: 'border-box',
          }}
        >
          {questions.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSelect(q)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '0.75rem',
                background: 'transparent',
                border: 'none',
                borderRadius: '8px',
                padding: '0.45rem 0.75rem',
                margin: 0,
                cursor: 'pointer',
                textAlign: 'left',
                color: 'var(--text-main, #334155)',
                fontSize: '0.91rem',
                lineHeight: 1.6,
                fontFamily: 'var(--font-results, "Helvetica Neue", Helvetica, Arial, sans-serif)',
                transition: 'all 0.15s ease',
                boxSizing: 'border-box',
                maxWidth: '100%',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(241, 245, 249, 0.8)';
                e.currentTarget.style.color = '#2563EB';
                const arrowSpan = e.currentTarget.querySelector('.arrow-icon') as HTMLElement;
                if (arrowSpan) {
                  arrowSpan.style.color = '#2563EB';
                  arrowSpan.style.transform = 'translateX(3px)';
                }
                const textSpan = e.currentTarget.querySelector('.followup-text') as HTMLElement;
                if (textSpan) {
                  textSpan.style.color = '#2563EB';
                  textSpan.style.borderBottomColor = '#2563EB';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = 'var(--text-main, #334155)';
                const arrowSpan = e.currentTarget.querySelector('.arrow-icon') as HTMLElement;
                if (arrowSpan) {
                  arrowSpan.style.color = '#94A3B8';
                  arrowSpan.style.transform = 'translateX(0)';
                }
                const textSpan = e.currentTarget.querySelector('.followup-text') as HTMLElement;
                if (textSpan) {
                  textSpan.style.color = 'var(--text-main, #334155)';
                  textSpan.style.borderBottomColor = '#CBD5E1';
                }
              }}
            >
              <span
                className="arrow-icon"
                style={{
                  color: 'var(--text-muted, #94A3B8)',
                  fontSize: '1.05rem',
                  fontWeight: 500,
                  transition: 'all 0.15s ease',
                  flexShrink: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  lineHeight: 1,
                }}
              >
                →
              </span>
              <span
                className="followup-text"
                style={{
                  textAlign: 'left',
                  fontWeight: 500,
                  borderBottom: '1px dashed var(--border-color, #CBD5E1)',
                  paddingBottom: '2px',
                  transition: 'all 0.15s ease',
                }}
              >
                {q}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
