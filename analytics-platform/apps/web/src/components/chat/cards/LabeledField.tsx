import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface LabeledFieldProps {
  label: string;
  contentMarkdown: string;
  visibleChars?: number;
  isFullText?: boolean;
}

export const LabeledField: React.FC<LabeledFieldProps> = ({
  label,
  contentMarkdown,
  visibleChars,
  isFullText = false,
}) => {
  // If visibleChars is provided and not full text, slice the content
  const displayedContent = isFullText || visibleChars === undefined
    ? contentMarkdown
    : contentMarkdown.slice(0, Math.max(0, visibleChars));

  if (!displayedContent && !isFullText) {
    return null;
  }

  const cleanLabel = label.endsWith(':') ? label : `${label}:`;

  return (
    <div style={{ marginBottom: '0.65rem', fontSize: '0.87rem', lineHeight: 1.55 }}>
      <span
        style={{
          fontWeight: 600,
          color: 'var(--text-main)',
          marginRight: '0.35rem',
          display: 'inline',
        }}
      >
        {cleanLabel}
      </span>
      <span style={{ color: 'var(--text-main)' }}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <span style={{ margin: 0 }}>{children}</span>,
            code: ({ children }) => (
              <code
                style={{
                  backgroundColor: 'transparent',
                  color: 'var(--text-main)',
                  fontSize: '0.84rem',
                  fontFamily: 'var(--font-mono, "SFMono-Regular", Consolas, Menlo, monospace)',
                  fontWeight: 500,
                }}
              >
                {children}
              </code>
            ),
            strong: ({ children }) => (
              <strong style={{ fontWeight: 600, color: 'var(--text-main)' }}>{children}</strong>
            ),
          }}
        >
          {displayedContent}
        </ReactMarkdown>
      </span>
    </div>
  );
};
