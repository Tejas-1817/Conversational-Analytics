import React from 'react';
import type { CardModel } from './types';
import { IconBadge } from './IconBadge';
import { TONE_TOKEN_MAP } from './cardToneConfig';

interface CardShellProps {
  card: CardModel;
  isComplete: boolean;
  children: (props: { isFullText: boolean }) => React.ReactNode;
}

export const CardShell: React.FC<CardShellProps> = ({ card, isComplete, children }) => {
  const tokens = TONE_TOKEN_MAP[card.tone] || TONE_TOKEN_MAP.primary;

  return (
    <article
      aria-labelledby={`card-title-${card.id}`}
      style={{
        backgroundColor: 'var(--bg-card)',
        border: 'none',
        borderRadius: 'var(--radius-lg, 12px)',
        padding: '1.4rem 1.35rem',
        boxShadow: '0 2px 8px rgba(16, 24, 40, 0.08), 0 1px 3px rgba(16, 24, 40, 0.04)',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
        width: '100%',
        minWidth: 0,
        minHeight: card.kind === 'point' ? '300px' : undefined,
        position: 'relative',
        gridColumn: card.isFullWidth ? '1 / -1' : 'auto',
      }}
    >
      {/* Header: Icon Badge & Title */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          marginBottom: '0.85rem',
        }}
      >
        {card.kind !== 'ordered_list' && card.kind !== 'bullet_list' && (
          <IconBadge kind={card.kind} tone={card.tone} />
        )}
        <h3
          id={`card-title-${card.id}`}
          style={{
            margin: 0,
            fontSize: '0.98rem',
            fontWeight: 700,
            color: tokens.textColor,
            letterSpacing: '-0.01em',
            fontFamily: 'var(--font-results, inherit)',
          }}
        >
          {card.title}
        </h3>
      </header>

      {/* Body Area with Height Reservation */}
      <div style={{ position: 'relative', flex: 1, minWidth: 0 }}>
        {!isComplete ? (
          <>
            {/* Invisible sizer layer: reserves exact final height with zero layout shifts */}
            <div
              style={{
                visibility: 'hidden',
                userSelect: 'none',
                pointerEvents: 'none',
              }}
              aria-hidden="true"
            >
              {children({ isFullText: true })}
            </div>
            {/* Revealing overlay */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                overflow: 'hidden',
              }}
            >
              {children({ isFullText: false })}
            </div>
          </>
        ) : (
          <div>{children({ isFullText: true })}</div>
        )}
      </div>
    </article>
  );
};
