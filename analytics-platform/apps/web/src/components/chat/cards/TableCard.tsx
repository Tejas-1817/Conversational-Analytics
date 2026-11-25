import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { CardModel } from './types';
import { CardShell } from './CardShell';

interface TableCardProps {
  card: CardModel;
  visibleChars?: number;
  isComplete: boolean;
}

export const TableCard: React.FC<TableCardProps> = ({ card, visibleChars, isComplete }) => {
  const content = card.rawTableMarkdown || '';

  return (
    <CardShell card={card} isComplete={isComplete}>
      {({ isFullText }) => {
        const textToDisplay = isFullText || visibleChars === undefined
          ? content
          : content.slice(0, Math.max(0, visibleChars));

        return (
          <div style={{ overflowX: 'auto', width: '100%', margin: '0.25rem 0' }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <table
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: '0.84rem',
                      textAlign: 'left',
                      fontFamily: 'var(--font-results, inherit)',
                    }}
                  >
                    {children}
                  </table>
                ),
                th: ({ children }) => (
                  <th
                    style={{
                      padding: '0.6rem 0.85rem',
                      backgroundColor: 'var(--bg-dark)',
                      borderBottom: '2px solid var(--border-color)',
                      fontWeight: 700,
                      color: 'var(--text-main)',
                      fontSize: '0.75rem',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td
                    style={{
                      padding: '0.55rem 0.85rem',
                      borderBottom: '1px solid var(--border-color)',
                      color: 'var(--text-main)',
                    }}
                  >
                    {children}
                  </td>
                ),
              }}
            >
              {textToDisplay}
            </ReactMarkdown>
          </div>
        );
      }}
    </CardShell>
  );
};
