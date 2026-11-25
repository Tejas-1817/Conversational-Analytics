import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { CardModel } from './types';
import { CardShell } from './CardShell';

interface ListCardProps {
  card: CardModel;
  visibleChars?: number;
  isComplete: boolean;
}

export const ListCard: React.FC<ListCardProps> = ({ card, visibleChars, isComplete }) => {
  const isOrdered = card.kind === 'ordered_list';
  const items = card.listItems || [];

  return (
    <CardShell card={card} isComplete={isComplete}>
      {({ isFullText }) => {
        let remainingBudget = isFullText || visibleChars === undefined ? Infinity : visibleChars;

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            {items.map((item, idx) => {
              const itemLen = item.length;
              if (!isFullText && remainingBudget <= 0) {
                return null;
              }

              const displayedItem = isFullText ? item : item.slice(0, remainingBudget);
              if (!isFullText) {
                remainingBudget = Math.max(0, remainingBudget - itemLen);
              }

              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.65rem',
                    fontSize: '0.88rem',
                    lineHeight: 1.55,
                    color: 'var(--text-main)',
                  }}
                >
                  {isOrdered ? (
                    <div
                      style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--primary-light)',
                        color: 'var(--primary)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        flexShrink: 0,
                        marginTop: '0.15rem',
                      }}
                      aria-hidden="true"
                    >
                      {idx + 1}
                    </div>
                  ) : (
                    <div
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--text-muted)',
                        flexShrink: 0,
                        marginTop: '0.55rem',
                        marginLeft: '0.4rem',
                        marginRight: '0.2rem',
                      }}
                      aria-hidden="true"
                    />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <span style={{ margin: 0 }}>{children}</span>,
                        strong: ({ children }) => (
                          <strong style={{ fontWeight: 600, color: 'var(--text-main)' }}>{children}</strong>
                        ),
                        code: ({ children }) => (
                          <code
                            style={{
                              backgroundColor: 'var(--bg-dark)',
                              padding: '0.1rem 0.35rem',
                              borderRadius: 'var(--radius-sm, 4px)',
                              fontFamily: 'var(--font-mono, monospace)',
                              fontSize: '0.82rem',
                            }}
                          >
                            {children}
                          </code>
                        ),
                      }}
                    >
                      {displayedItem}
                    </ReactMarkdown>
                  </div>
                </div>
              );
            })}
          </div>
        );
      }}
    </CardShell>
  );
};
