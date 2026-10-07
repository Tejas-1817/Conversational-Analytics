import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Lightbulb, CheckCircle2, TrendingUp, Layers } from 'lucide-react';

interface WisdomMarkdownRendererProps {
  content: string;
}

/**
 * Splits text outside parenthesis by given delimiters.
 */
function splitOutsideParens(text: string): string[] {
  const items: string[] = [];
  let current = '';
  let parenDepth = 0;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '(' || ch === '[' || ch === '{') parenDepth++;
    else if (ch === ')' || ch === ']' || ch === '}') parenDepth = Math.max(0, parenDepth - 1);

    if (parenDepth === 0) {
      if (text.startsWith(', and another instance of ', i)) {
        if (current.trim()) items.push(current.trim());
        current = '';
        i += ', and another instance of '.length - 1;
        continue;
      }
      if (text.startsWith(', and ', i)) {
        if (current.trim()) items.push(current.trim());
        current = '';
        i += ', and '.length - 1;
        continue;
      }
      if (text.startsWith('; ', i) || text.startsWith(', the ', i) || text.startsWith(', ', i)) {
        if (current.trim()) items.push(current.trim());
        current = '';
        if (text.startsWith(', the ', i)) {
          i += ', '.length - 1;
        } else if (text.startsWith('; ', i)) {
          i += '; '.length - 1;
        } else {
          i += ', '.length - 1;
        }
        continue;
      }
    }
    current += ch;
  }
  if (current.trim()) {
    items.push(current.trim());
  }

  return items.filter((it) => it.length > 2);
}

/**
 * Automatically transforms dense plain-text summary paragraphs into
 * clean, unorganized (unordered) bulleted list items.
 */
export function formatSummaryContent(content: string): string {
  if (!content) return '';

  // If already formatted with markdown lists (- , * , 1. ), keep intact
  if (/^(\s*[-*+]|\s*\d+\.)\s+/m.test(content)) {
    return content;
  }

  // Split into paragraph blocks
  const blocks = content.split(/\n\s*\n/);
  const transformedBlocks = blocks.map((block) => {
    const trimmed = block.trim();
    if (!trimmed) return '';

    // Skip Markdown elements (headings, blockquotes, code fences, tables)
    if (trimmed.startsWith('#') || trimmed.startsWith('>') || trimmed.startsWith('```') || trimmed.startsWith('|')) {
      return trimmed;
    }

    // Split sentences respecting abbreviations
    const sentences = trimmed.match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g) || [trimmed];
    if (sentences.length <= 1) {
      // Check if even a single sentence has a list of items ("...include X, Y, and Z")
      if (trimmed.toLowerCase().includes('include') || (trimmed.includes('(') && trimmed.includes(',') && trimmed.includes(')'))) {
        const parts = splitOutsideParens(trimmed);
        if (parts.length > 1) {
          const intro = parts[0];
          const items = parts.slice(1).map((p) => `- ${p.replace(/^the\s+/i, '').replace(/^[,\s;]+|[,\s;.]+$/g, '')}`);
          return `${intro}:\n\n${items.join('\n')}`;
        }
      }
      return trimmed;
    }

    // First sentence acts as the summary lead-in
    let intro = sentences[0].trim();
    if (!intro.endsWith(':') && !intro.endsWith('.')) {
      intro += ':';
    } else if (intro.endsWith('.')) {
      intro = intro.slice(0, -1) + ':';
    }

    const listItems: string[] = [];
    const remaining = sentences.slice(1);

    remaining.forEach((s) => {
      const st = s.trim();
      if (!st) return;

      // If the sentence contains multiple items separated by commas / includes
      if (
        st.toLowerCase().includes('include') ||
        st.toLowerCase().includes('additionally') ||
        (st.includes('(') && st.includes(',') && st.includes(')'))
      ) {
        // Strip leading keywords
        const cleanedSentence = st
          .replace(/^(Other\s+low\s+stock\s+items\s+include\s+|Other\s+items\s+include\s+|Additionally,\s*|Also,\s*)/i, '')
          .trim();

        const splitItems = splitOutsideParens(cleanedSentence);
        if (splitItems.length > 1) {
          splitItems.forEach((item) => {
            const clean = item
              .replace(/^(the\s+|and\s+another\s+instance\s+of\s+|and\s+the\s+|and\s+)/i, '')
              .replace(/^[,\s;]+|[,\s;.]+$/g, '')
              .trim();
            if (clean.length > 1) {
              listItems.push(clean.charAt(0).toUpperCase() + clean.slice(1));
            }
          });
          return;
        }
      }

      // Standalone sentence item
      const cleanStandalone = st
        .replace(/^(the\s+|additionally,\s*|also,\s*)/i, '')
        .replace(/^[,\s;]+|[,\s;.]+$/g, '')
        .trim();
      if (cleanStandalone.length > 1) {
        listItems.push(cleanStandalone.charAt(0).toUpperCase() + cleanStandalone.slice(1));
      }
    });

    if (listItems.length > 0) {
      const bullets = listItems.map((item) => `- ${item}`).join('\n');
      return `${intro}\n\n${bullets}`;
    }

    return trimmed;
  });

  return transformedBlocks.join('\n\n');
}

export const WisdomMarkdownRenderer: React.FC<WisdomMarkdownRendererProps> = ({ content }) => {
  if (!content) return null;

  const formattedContent = React.useMemo(() => formatSummaryContent(content), [content]);

  return (
    <div
      className="wisdom-summary-card"
      style={{
        width: '100%',
        backgroundColor: 'var(--bg-card, #FFFFFF)',
        border: '1px solid var(--border-color, #E2E8F0)',
        borderRadius: '14px',
        padding: '1.25rem 1.5rem',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.03)',
        fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
        fontSize: '0.92rem',
        lineHeight: 1.68,
        color: 'var(--text-main, #1E293B)',
        boxSizing: 'border-box',
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 style={{
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              fontSize: '1.35rem',
              fontWeight: 700,
              color: 'var(--text-main, #0F172A)',
              margin: '0.75rem 0 0.5rem 0',
              letterSpacing: '-0.02em',
            }}>
              {children}
            </h1>
          ),
          h2: ({ children }) => {
            const textStr = String(children || '');
            const isConclusion = textStr.toLowerCase().includes('conclusion');
            const isPriority = textStr.toLowerCase().includes('prioritize') || textStr.toLowerCase().includes('high-value');
            const isDomains = textStr.toLowerCase().includes('domains') || textStr.toLowerCase().includes('opportunities');

            return (
              <h2 style={{
                fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
                fontSize: '1.12rem',
                fontWeight: 700,
                color: isConclusion ? '#059669' : 'var(--text-main, #0F172A)',
                margin: '1.25rem 0 0.6rem 0',
                letterSpacing: '-0.01em',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}>
                {isConclusion && <CheckCircle2 size={18} style={{ color: '#10B981' }} />}
                {isPriority && <TrendingUp size={18} style={{ color: '#6366F1' }} />}
                {isDomains && <Layers size={18} style={{ color: '#0EA5E9' }} />}
                {children}
              </h2>
            );
          },
          h3: ({ children }) => (
            <h3 style={{
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              fontSize: '0.96rem',
              fontWeight: 700,
              color: 'var(--text-main, #1E293B)',
              margin: '0.85rem 0 0.35rem 0',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
            }}>
              <div style={{
                width: '22px',
                height: '22px',
                borderRadius: '6px',
                background: 'rgba(99, 102, 241, 0.1)',
                color: '#6366F1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                <Lightbulb size={13} />
              </div>
              <span>{children}</span>
            </h3>
          ),
          p: ({ children }) => (
            <p style={{
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              margin: '0.45rem 0 0.65rem 0',
              lineHeight: 1.68,
              color: 'var(--text-main, #334155)',
              fontSize: '0.92rem',
            }}>
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul style={{
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              margin: '0.65rem 0 0.85rem 0',
              paddingLeft: '1.4rem',
              listStyleType: 'disc',
              color: 'var(--text-main, #334155)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.45rem',
            }}>
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol style={{
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              margin: '0.65rem 0 0.85rem 0',
              paddingLeft: '1.4rem',
              color: 'var(--text-main, #334155)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.45rem',
            }}>
              {children}
            </ol>
          ),
          li: ({ children, node }: any) => {
            const isOrdered = node?.parent?.tagName === 'ol';
            const index = node?.index !== undefined ? node.index + 1 : 1;

            if (isOrdered) {
              return (
                <li style={{
                  fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
                  marginBottom: '0.2rem',
                  fontSize: '0.91rem',
                  lineHeight: 1.62,
                  color: 'var(--text-main, #334155)',
                }}>
                  <strong style={{ color: '#0F172A', marginRight: '0.35rem' }}>{index}.</strong>
                  {children}
                </li>
              );
            }

            return (
              <li style={{
                fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
                marginBottom: '0.2rem',
                fontSize: '0.91rem',
                lineHeight: 1.62,
                color: 'var(--text-main, #334155)',
              }}>
                {children}
              </li>
            );
          },
          code: ({ children, className }: any) => {
            const isInline = !className || !className.includes('language-');
            if (isInline) {
              return (
                <code style={{
                  backgroundColor: '#F1F5F9',
                  color: '#0F172A',
                  padding: '0.15rem 0.45rem',
                  borderRadius: '5px',
                  fontSize: '0.84rem',
                  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                  border: '1px solid #E2E8F0',
                }}>
                  {children}
                </code>
              );
            }
            return (
              <pre style={{
                backgroundColor: '#0F172A',
                color: '#F8FAFC',
                padding: '1rem',
                borderRadius: '10px',
                overflowX: 'auto',
                fontSize: '0.84rem',
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                margin: '0.75rem 0',
              }}>
                <code>{children}</code>
              </pre>
            );
          },
          blockquote: ({ children }) => (
            <div style={{
              borderLeft: '3px solid #3B82F6',
              padding: '0.65rem 1rem',
              backgroundColor: 'rgba(59, 130, 246, 0.05)',
              borderRadius: '0 8px 8px 0',
              margin: '0.75rem 0',
              fontStyle: 'normal',
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              color: 'var(--text-main, #1E293B)',
            }}>
              {children}
            </div>
          ),
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '0.75rem 0', borderRadius: '10px', border: '1px solid var(--border-color, #E2E8F0)' }}>
              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '0.84rem',
                textAlign: 'left',
                fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
              }}>
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th style={{
              padding: '0.65rem 0.85rem',
              backgroundColor: '#F8FAFC',
              borderBottom: '2px solid #E2E8F0',
              fontWeight: 700,
              color: '#0F172A',
              textTransform: 'uppercase',
              fontSize: '0.75rem',
              letterSpacing: '0.04em',
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
            }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{
              padding: '0.6rem 0.85rem',
              borderBottom: '1px solid #F1F5F9',
              color: '#334155',
              fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
            }}>
              {children}
            </td>
          ),
        }}
      >
        {formattedContent}
      </ReactMarkdown>
    </div>
  );
};
