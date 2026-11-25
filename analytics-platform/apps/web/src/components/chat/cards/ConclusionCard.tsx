import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { CardModel } from './types';
import { CardShell } from './CardShell';

interface ConclusionCardProps {
  card: CardModel;
  visibleChars?: number;
  isComplete: boolean;
}

export const ConclusionCard: React.FC<ConclusionCardProps> = ({ card, visibleChars, isComplete }) => {
  const content = card.leadParagraph || '';

  return (
    <CardShell card={card} isComplete={isComplete}>
      {({ isFullText }) => {
        const textToDisplay = isFullText || visibleChars === undefined
          ? content
          : content.slice(0, Math.max(0, visibleChars));

        return (
          <div
            style={{
              fontSize: '0.91rem',
              lineHeight: 1.65,
              color: 'var(--text-main)',
              fontFamily: 'var(--font-results, inherit)',
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p style={{ margin: 0 }}>{children}</p>,
                strong: ({ children }) => (
                  <strong style={{ fontWeight: 700, color: 'var(--text-main)' }}>{children}</strong>
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
