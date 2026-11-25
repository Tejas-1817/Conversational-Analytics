import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { CardModel } from './types';
import { CardShell } from './CardShell';
import { LabeledField } from './LabeledField';

interface PointCardProps {
  card: CardModel;
  visibleChars?: number;
  isComplete: boolean;
}

export const PointCard: React.FC<PointCardProps> = ({ card, visibleChars, isComplete }) => {
  return (
    <CardShell card={card} isComplete={isComplete}>
      {({ isFullText }) => {
        let remainingBudget = isFullText || visibleChars === undefined ? Infinity : visibleChars;

        // 1. Lead paragraph budget
        let displayedLead = '';
        if (card.leadParagraph) {
          if (remainingBudget >= card.leadParagraph.length) {
            displayedLead = card.leadParagraph;
            remainingBudget -= card.leadParagraph.length;
          } else {
            displayedLead = card.leadParagraph.slice(0, remainingBudget);
            remainingBudget = 0;
          }
        }

        return (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {displayedLead && (
              <div
                style={{
                  fontSize: '0.88rem',
                  lineHeight: 1.6,
                  color: 'var(--text-main)',
                  marginBottom: card.fields?.length ? '0.75rem' : '0',
                }}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p style={{ margin: 0 }}>{children}</p>,
                    strong: ({ children }) => (
                      <strong style={{ fontWeight: 600, color: 'var(--text-main)' }}>{children}</strong>
                    ),
                  }}
                >
                  {displayedLead}
                </ReactMarkdown>
              </div>
            )}

            {/* Bullet List Items */}
            {card.listItems && card.listItems.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', marginTop: card.fields?.length || displayedLead ? '0.75rem' : '0' }}>
                {card.listItems.map((item, idx) => {
                  const itemLength = item.length;
                  if (!isFullText && remainingBudget <= 0) {
                    return null;
                  }

                  const displayedItem = isFullText ? item : item.slice(0, remainingBudget);
                  if (!isFullText) {
                    remainingBudget = Math.max(0, remainingBudget - itemLength);
                  }

                  return (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '0.5rem',
                        fontSize: '0.87rem',
                        lineHeight: 1.6,
                      }}
                    >
                      <span
                        style={{
                          color: 'var(--text-muted)',
                          fontSize: '1rem',
                          lineHeight: 1.2,
                          flexShrink: 0,
                        }}
                        aria-hidden="true"
                      >
                        •
                      </span>
                      <div style={{ flex: 1, minWidth: 0, color: 'var(--text-main)' }}>
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
                                  backgroundColor: 'transparent',
                                  color: 'var(--text-main)',
                                  fontSize: '0.82rem',
                                  fontFamily: 'var(--font-mono, monospace)',
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
            )}

            {/* Labeled fields */}
            {card.fields && card.fields.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: card.listItems?.length || displayedLead ? '0.65rem' : 'auto' }}>
                {card.fields.map((field, idx) => {
                  const fieldLength = field.contentMarkdown.length;
                  const fieldChars = isFullText ? fieldLength : Math.min(fieldLength, remainingBudget);
                  if (!isFullText) {
                    remainingBudget = Math.max(0, remainingBudget - fieldLength);
                  }

                  return (
                    <LabeledField
                      key={idx}
                      label={field.label}
                      contentMarkdown={field.contentMarkdown}
                      visibleChars={fieldChars}
                      isFullText={isFullText}
                    />
                  );
                })}
              </div>
            )}
          </div>
        );
      }}
    </CardShell>
  );
};
